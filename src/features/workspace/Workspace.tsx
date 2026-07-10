import { useState, useCallback, useEffect, useRef } from "react";
import { useStore } from "@/app/store";
import type { Primitive } from "@/utils/types";
import { detectPaper, extractToolMask, simplifyContours, extractContours } from "@/api/toolProcessor";
import { TopBar } from "./TopBar";
import { LeftRail } from "./LeftRail";
import { Viewport } from "./Viewport";
import { PlanningPanel } from "./PlanningPanel";

interface PaperDetectionResult {
  success: boolean;
  error?: string;
  corners?: PaperCorner[];
  warped_image?: string;
  mode?: string;
  methodCount?: number;
  confidence?: number;
  skew?: {
    level: string;
    message: string;
  };
  lowConfidence?: boolean;
}

interface PaperCorner {
  x: number;
  y: number;
}

export default function Workspace() {
  const step = useStore((s) => s.step);
  const setStep = useStore((s) => s.setStep);
  const imageUrl = useStore((s) => s.imageUrl);
  const setImageUrl = useStore((s) => s.setImageUrl);
  const setPrimitives = useStore((s) => s.setPrimitives);

  const [imgUrl, setImgUrl] = useState<string | undefined>(imageUrl ?? undefined);
  const [warpedUrl, setWarpedUrl] = useState<string | undefined>();
  const [primitives, setLocalPrimitives] = useState<Primitive[]>([]);
  const [primitiveDebugUrl, setPrimitiveDebugUrl] = useState<string | undefined>();
  const [processing, setProcessing] = useState(false);
  const [processError, setProcessError] = useState<string | null>(null);

  // 新增状态用于分步处理
  const [maskUrl, setMaskUrl] = useState<string | undefined>();
  const [simplifiedPrimitives, setSimplifiedPrimitives] = useState<Primitive[]>([]);
  const [currentPrimitives, setCurrentPrimitives] = useState<Primitive[]>([]);

  // 纸张检测结果状态
  const [paperDetectionResult, setPaperDetectionResult] = useState<PaperDetectionResult | null>(null);

  const [railCollapsed, setRailCollapsed] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [showGrid, setShowGrid] = useState(true);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // store 中的图片 URL 变化时同步本地状态并清空旧结果
  useEffect(() => {
    if (imageUrl) {
      setImgUrl(imageUrl);
      setLocalPrimitives([]);
      setPrimitiveDebugUrl(undefined);
      setProcessError(null);
      setZoom(1);
    }
  }, [imageUrl]);

  // 处理图片（纸张检测）
  const processPaperDetection = useCallback(async (file: File) => {
    setProcessing(true);
    setProcessError(null);
    setPaperDetectionResult(null);

    try {
      const result = await detectPaper(file);

      if (result.success && result.corners && result.warped_image) {
        setPaperDetectionResult(result);
        setWarpedUrl(result.warped_image);
        setProcessError(null);

        // 自动跳转到下一个步骤
        setStep("segmentation");
      } else {
        setPaperDetectionResult(result);
        setProcessError(result.error || "纸张检测失败");
        // 如果检测失败，保持在当前步骤
        setStep("calibration");
      }
    } catch (err: any) {
      console.error("[Workspace] detectPaper threw:", err);
      setProcessError(err?.message || "纸张检测失败");
      // 如果检测失败，保持在当前步骤
      setStep("calibration");
    } finally {
      setProcessing(false);
    }
  }, [setStep]);

  // 处理轮廓提取（两步法：先提取蒙版，再简化）
  const processContourExtraction = useCallback(async (file: File) => {
    setProcessing(true);
    setProcessError(null);
    
    try {
      // 如果已经有校正后的图像URL，我们需要从中创建一个File对象
      let fileToProcess = file;
      
      if (warpedUrl) {
        // 从warpedUrl创建Blob，然后创建File对象
        const response = await fetch(warpedUrl);
        const blob = await response.blob();
        fileToProcess = new File([blob], "warped_image.jpg", { type: blob.type });
      }
      
      // 第一步：提取工具轮廓（包括调试图像）
      const contourResult = await extractContours(fileToProcess);
      
      if (!contourResult.success || !contourResult.primitives) {
        setProcessError(contourResult.error || "轮廓提取失败");
        return;
      }
      
      // 设置调试图像（如果有）
      if (contourResult.debug_image) {
        setPrimitiveDebugUrl(contourResult.debug_image);
      }
      
      setPrimitives(contourResult.primitives);
      
      // 第二步：提取工具蒙版
      const maskResult = await extractToolMask(fileToProcess);
      
      if (!maskResult.success || !maskResult.mask_image) {
        setProcessError(maskResult.error || "蒙版提取失败");
        return;
      }
      
      setMaskUrl(maskResult.mask_image);
      
      // 第三步：对蒙版进行抽稀基元化处理
      const simplifyResult = await simplifyContours({ mask_image: maskResult.mask_image });
      
      if (simplifyResult.success && simplifyResult.primitives) {
        setSimplifiedPrimitives(simplifyResult.primitives);
        setLocalPrimitives(simplifyResult.primitives);
        setProcessError(null);
        
        // 自动跳转到编辑器步骤
        setStep("editor");
      } else {
        setProcessError(simplifyResult.error || "轮廓简化失败");
      }
    } catch (err: any) {
      console.error("[Workspace] extractContours threw:", err);
      setProcessError(err?.message || "轮廓提取失败");
    } finally {
      setProcessing(false);
    }
  }, [setPrimitives, warpedUrl, setStep]);

  const handleFile = useCallback(
    (file: File | undefined) => {
      if (!file || !file.type.startsWith("image/")) return;
      const url = URL.createObjectURL(file);
      setImageUrl(url);
      setStep("calibration");
      // 自动触发纸张检测
      processPaperDetection(file);
    },
    [setImageUrl, setStep, processPaperDetection],
  );

  const onZoomIn = () => setZoom((z) => Math.min(3, Math.round((z + 0.15) * 100) / 100));
  const onZoomOut = () => setZoom((z) => Math.max(0.3, Math.round((z - 0.15) * 100) / 100));
  const onFit = () => setZoom(1);
  const onToggleGrid = () => setShowGrid((g) => !g);

  const stage: 0 | 1 | 2 = !imgUrl ? 0 : !warpedUrl ? 1 : 2;

  return (
    <div className="h-screen flex flex-col bg-canvas-950 text-zinc-200 overflow-hidden">
      <TopBar hasGeometry={!!warpedUrl} />
      <div className="flex-1 flex min-h-0 relative">
        <LeftRail
          step={step}
          collapsed={railCollapsed}
          onToggleCollapse={() => setRailCollapsed((c) => !c)}
          onSelect={(key) => setStep(key)}
          onUpload={() => fileInputRef.current?.click()}
        />
        <Viewport
          imgUrl={imgUrl}
          warpedUrl={warpedUrl}
          maskUrl={maskUrl}
          showGrid={showGrid}
          zoom={zoom}
          onFile={handleFile}
          hasImage={!!imgUrl}
          stage={stage}
          detecting={processing}
          extracting={false}
          onZoomIn={onZoomIn}
          onZoomOut={onZoomOut}
          onFit={onFit}
          onToggleGrid={onToggleGrid}
          step={step}
          primitives={currentPrimitives}
        />
        <aside className="absolute right-4 top-4 bottom-4 w-80 shrink-0 z-10">
          <div className="glass-panel rounded-2xl h-full overflow-y-auto canvas-scroll p-4 animate-slide-in-right">
            <PlanningPanel
              step={step}
              onUpload={() => fileInputRef.current?.click()}
              onExtract={() => {}}
              extracting={false}
              extractError={null}
              debugUrl={!!warpedUrl}
              primitives={primitives}
              primitiveDebugUrl={primitiveDebugUrl}
              onRedetect={() => {
                // 重新检测，使用当前的图像文件
                if (fileInputRef.current?.files?.[0]) {
                  processPaperDetection(fileInputRef.current.files[0]);
                }
              }}
              onWarp={() => {
                // 这里应该是处理透视校正的逻辑
                // 目前我们已经在processPaperDetection中完成了这个步骤
              }}
              detecting={processing}
              detect={paperDetectionResult}
              detectError={processError}
              imgUrl={!!imgUrl}
              processContourExtraction={processContourExtraction}
              maskUrl={maskUrl}
              onMaskUpdate={setMaskUrl}
              simplifiedPrimitives={simplifiedPrimitives}
              setSimplifiedPrimitives={(primitives) => {
                setSimplifiedPrimitives(primitives);
                setCurrentPrimitives(primitives);
              }}
              originalContour={primitiveDebugUrl}
              warpedUrl={warpedUrl}
            />
          </div>
        </aside>
      </div>
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) {
            handleFile(file);
            processPaperDetection(file);
          }
        }}
      />
    </div>
  );
}
