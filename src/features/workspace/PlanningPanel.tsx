import type { Step } from "@/app/store";
import type { Primitive } from "@/utils/types";
import { UploadPanel } from "@/features/upload/UploadPanel";
import { CalibrationPanel } from "@/features/calibration/CalibrationPanel";
import { SegmentationPanel } from "@/features/segmentation/SegmentationPanel";
import { EditorPanel } from "@/features/editor/EditorPanel";
import { ParamsPanel } from "@/features/params/ParamsPanel";
import { ExportPanel } from "@/features/export/ExportPanel";

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

interface PlanningPanelProps {
  step: Step;
  onUpload: () => void;
  onExtract: () => void;
  extracting: boolean;
  extractError: string | null;
  debugUrl: boolean;
  primitives: Primitive[];
  primitiveDebugUrl?: string;
  onRedetect: () => void;
  onWarp: () => void;
  detecting: boolean;
  detect: PaperDetectionResult | null;
  detectError: string | null;
  imgUrl: boolean;
  processContourExtraction?: (file: File) => Promise<void>;
  maskUrl?: string;
  onMaskUpdate?: (updatedMask: string) => void;
  simplifiedPrimitives: Primitive[];
  setSimplifiedPrimitives: (primitives: Primitive[]) => void;
  originalContour?: string; // 原始轮廓图像（红色边框）
  warpedUrl?: string; // 校正后的图像（用于背景叠加）
}

export function PlanningPanel({
  step,
  onUpload,
  onExtract,
  extracting,
  extractError,
  debugUrl,
  primitives,
  primitiveDebugUrl,
  onRedetect,
  onWarp,
  detecting,
  detect,
  detectError,
  imgUrl,
  processContourExtraction,
  maskUrl,
  onMaskUpdate,
  simplifiedPrimitives,
  setSimplifiedPrimitives,
  originalContour,
  warpedUrl
}: PlanningPanelProps) {
  if (step === "upload") {
    return <UploadPanel onUpload={onUpload} />;
  }

  if (step === "calibration") {
    return (
      <CalibrationPanel
        detecting={detecting}
        detect={detect}
        detectError={detectError}
        imgUrl={imgUrl}
        onRedetect={onRedetect}
        onWarp={onWarp}
      />
    );
  }

  if (step === "segmentation") {
    return (
      <SegmentationPanel
        onExtract={onExtract}
        extracting={extracting}
        extractError={extractError}
        debugUrl={debugUrl}
        primitives={primitives}
        primitiveDebugUrl={primitiveDebugUrl}
        processContourExtraction={processContourExtraction}
      />
    );
  }

  if (step === "editor") {
    return (
      <EditorPanel
        maskUrl={maskUrl}
        onMaskUpdate={onMaskUpdate}
        simplifiedPrimitives={simplifiedPrimitives}
        setSimplifiedPrimitives={setSimplifiedPrimitives}
        originalContour={originalContour}
        backgroundImage={warpedUrl}
      />
    );
  }

  if (step === "params") {
    return <ParamsPanel />;
  }

  if (step === "export") {
    return <ExportPanel />;
  }

  return null;
}