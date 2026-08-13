import { useState, useCallback, useEffect, useRef } from "react";
import { useStore } from "@/app/store";
import type { Primitive } from "@/utils/types";
import { detectPaper, extractToolMask, extractContours } from "@/api/toolProcessor";
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
  const [primitiveDebugUrl, setPrimitiveDebugUrl] = useState<string | undefined>();
  const [processing, setProcessing] = useState(false);
  const [processError, setProcessError] = useState<string | null>(null);

  const [maskUrl, setMaskUrl] = useState<string | undefined>();
  const [simplifiedPrimitives, setSimplifiedPrimitives] = useState<Primitive[]>([]);
  const [currentPrimitives, setCurrentPrimitives] = useState<Primitive[]>([]);

  // 纸张检测结果状态
  const [paperDetectionResult, setPaperDetectionResult] = useState<PaperDetectionResult | null>(null);

  // 轮廓检测失败状态（用于显示重新上传/手动绘制选项）
  const [detectionFailed, setDetectionFailed] = useState(false);

  const [railCollapsed, setRailCollapsed] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [showGrid, setShowGrid] = useState(true);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // store 中的图片 URL 变化时同步本地状态并清空旧结果
  useEffect(() => {
    if (imageUrl) {
      setImgUrl(imageUrl);
      setPrimitiveDebugUrl(undefined);
      setProcessError(null);
      setZoom(1);
    }
  }, [imageUrl]);

  // 处理图片（纸张检测）
  const processPaperDetection = useCallback(async (file: File) => {
    if (!file) return;
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

  // 创建空白蒙版（用于后端完全不可用时兜底）
  const createBlankMask = useCallback(async (imageUrl: string): Promise<string> => {
    const img = new Image();
    img.src = imageUrl;
    await new Promise<void>((resolve) => { img.onload = () => resolve(); });
    const canvas = document.createElement('canvas');
    canvas.width = img.width;
    canvas.height = img.height;
    const ctx = canvas.getContext('2d');
    if (ctx) {
      ctx.fillStyle = '#000000';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
    }
    return canvas.toDataURL('image/jpeg');
  }, []);

  // 处理轮廓提取（两步法：先提取蒙版，再简化）
  const processContourExtraction = useCallback(async () => {
    if (!warpedUrl) {
      setProcessError("没有可用的校正图像，请先完成纸张检测");
      return;
    }
    setProcessing(true);
    setProcessError(null);

    try {
      // 从warpedUrl创建File对象（warpedUrl 是 data URL，fetch 安全）
      let fileToProcess: File;
      try {
        const response = await fetch(warpedUrl);
        const blob = await response.blob();
        fileToProcess = new File([blob], "warped_image.jpg", { type: blob.type });
      } catch (fetchErr) {
        console.error("[Workspace] 无法从 warpedUrl 创建 File:", fetchErr);
        setProcessError("无法处理校正图像，请重新上传");
        setProcessing(false);
        return;
      }

      let detectionFailed = false;

      // 第一步：提取工具轮廓（包括调试图像）
      const contourResult = await extractContours(fileToProcess);

      if (!contourResult.success) {
        detectionFailed = true;
      } else {
        // 设置调试图像（如果有）
        if (contourResult.debug_image) {
          setPrimitiveDebugUrl(contourResult.debug_image);
        }
        setPrimitives(contourResult.primitives || []);
        detectionFailed = !contourResult.primitives || contourResult.primitives.length === 0;
      }

      // 第二步：提取工具蒙版（后端现在总是返回蒙版，检测失败时返回空白蒙版）
      let finalMaskUrl: string | undefined;
      try {
        const maskResult = await extractToolMask(fileToProcess);
        if (maskResult.success && maskResult.mask_image) {
          finalMaskUrl = maskResult.mask_image;
        } else {
          setProcessError("蒙版提取失败，将进入手动编辑模式");
          finalMaskUrl = await createBlankMask(warpedUrl);
        }
      } catch (maskErr) {
        console.error("[Workspace] extractToolMask threw:", maskErr);
        setProcessError("蒙版提取失败，将进入手动编辑模式");
        finalMaskUrl = await createBlankMask(warpedUrl);
      }

      if (finalMaskUrl) {
        setMaskUrl(finalMaskUrl);
      }

      if (detectionFailed) {
        // 检测失败：显示选项面板，让用户选择手动绘制或重新上传
        setDetectionFailed(true);
        setProcessError("未检测到工具轮廓，请选择下一步操作");
        setProcessing(false);
        return;
      }

      // 检测成功，清除失败标记
      setDetectionFailed(false);

      // 第三步：初始显示使用原始轮廓（不抽稀），用户可后续手动点击「抽稀基元化」
      const rawPrimitives = contourResult.primitives || [];
      setSimplifiedPrimitives([]);  // 尚未抽稀
      setCurrentPrimitives(rawPrimitives);

      // 自动跳转到编辑器步骤
      setStep("editor");
    } catch (err: any) {
      console.error("[Workspace] extractContours threw:", err);
      setProcessError(err?.message || "轮廓提取失败");
    } finally {
      setProcessing(false);
    }
  }, [setPrimitives, warpedUrl, setStep, createBlankMask]);

  // 用户选择「手动绘制」：用空白蒙版直接进入编辑器
  const handleManualDraw = useCallback(async () => {
    setDetectionFailed(false);
    if (warpedUrl) {
      const blankMask = await createBlankMask(warpedUrl);
      setMaskUrl(blankMask);
    }
    setStep("editor");
  }, [warpedUrl, setStep, createBlankMask]);

  // 用户选择「重新上传」：回到上传步骤
  const handleReupload = useCallback(() => {
    setDetectionFailed(false);
    setWarpedUrl(undefined);
    setMaskUrl(undefined);
    setPrimitiveDebugUrl(undefined);
    setSimplifiedPrimitives([]);
    setCurrentPrimitives([]);
    setProcessError(null);
    setPaperDetectionResult(null);
    setStep("upload");
  }, [setStep]);

  // 用户点击「更新轮廓」（仅预览，不抽稀）
  const handleUpdateContour = useCallback((primitives: Primitive[]) => {
    // 仅更新 currentPrimitives（用于 Viewport 预览），不更新 simplifiedPrimitives
    setCurrentPrimitives(primitives);
  }, []);

  const handleFile = useCallback(
    (file: File | undefined) => {
      if (!file || !file.type.startsWith("image/")) return;
      const url = URL.createObjectURL(file);
      setImageUrl(url);
      // processPaperDetection 内部会设置步骤（成功→segmentation，失败→calibration）
      processPaperDetection(file);
    },
    [setImageUrl, processPaperDetection],
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
        <aside className={`absolute right-4 top-4 bottom-4 shrink-0 z-10 transition-all duration-300 ${step === 'editor' ? 'w-[28rem]' : 'w-80'}`}>
          <div className={`glass-panel rounded-2xl h-full overflow-y-auto canvas-scroll p-4 animate-slide-in-right ${step === 'editor' ? 'flex flex-col' : ''}`}>
            <PlanningPanel
              step={step}
              onUpload={() => fileInputRef.current?.click()}
              onExtract={() => {}}
              extracting={false}
              extractError={null}
              debugUrl={!!warpedUrl}
               primitives={currentPrimitives}
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
              warpedUrl={warpedUrl}
              detectionFailed={detectionFailed}
              onManualDraw={handleManualDraw}
              onReupload={handleReupload}
              onUpdateContour={handleUpdateContour}
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
            // handleFile 内部已调用 processPaperDetection，无需重复调用
          }
        }}
      />
    </div>
  );
}
