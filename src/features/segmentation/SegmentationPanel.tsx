import type { Primitive } from "@/utils/types";
import { Icon } from "@/components/ui/icons";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";

interface SegmentationPanelProps {
  onExtract: () => void;
  extracting: boolean;
  extractError: string | null;
  debugUrl: boolean;
  primitives: Primitive[];
  primitiveDebugUrl?: string;
  processContourExtraction?: (file: File) => Promise<void>;
  detectionFailed?: boolean;
  onManualDraw?: () => void;
  onReupload?: () => void;
}

export function SegmentationPanel({
  onExtract,
  extracting,
  extractError,
  debugUrl,
  primitives,
  primitiveDebugUrl,
  processContourExtraction,
  detectionFailed,
  onManualDraw,
  onReupload,
}: SegmentationPanelProps) {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 mb-1">
        <span className="w-7 h-7 rounded-lg bg-brand-600/20 text-brand-300 flex items-center justify-center">
          <Icon name="crop" size={15} />
        </span>
        <h2 className="text-sm font-semibold text-zinc-100">轮廓提取</h2>
      </div>
      
      <div className="text-sm text-zinc-400 mb-4">
        基于 Fast+SAM 的混合检测算法，自动提取工具轮廓并进行基元化处理。
      </div>
      
      <Button 
        className="w-full" 
        onClick={() => {
          // 使用传入的processContourExtraction函数
          if (processContourExtraction) {
            processContourExtraction(new File([], ""));
          } else {
            // 否则使用原来的onExtract回调
            onExtract();
          }
        }}
        disabled={extracting}
      >
        {extracting ? (
          <>
            <Icon name="loader" size={16} className="animate-spin" /> 提取中…
          </>
        ) : (
          <>
            <Icon name="sparkles" size={16} /> 提取工具轮廓
          </>
        )}
      </Button>

      {detectionFailed && (
        <div className="rounded-xl bg-amber-500/10 border border-amber-500/30 p-4 space-y-3">
          <div className="flex items-start gap-2">
            <Icon name="alert" size={16} className="text-amber-400 mt-0.5 shrink-0" />
            <div>
              <p className="text-amber-300 text-sm font-medium">未检测到工具轮廓</p>
              <p className="text-amber-300/70 text-[12px] mt-0.5">
                自动检测未能识别工具，您可以选择手动绘制或重新拍摄。
              </p>
            </div>
          </div>
          <div className="flex gap-2">
            <Button
              variant="primary"
              size="sm"
              className="flex-1"
              onClick={onManualDraw}
            >
              <Icon name="pencil" size={14} />
              手动绘制
            </Button>
            <Button
              variant="secondary"
              size="sm"
              className="flex-1"
              onClick={onReupload}
            >
              <Icon name="arrowLeft" size={14} />
              重新上传
            </Button>
          </div>
        </div>
      )}

      {extractError && !detectionFailed && (
        <div className="flex items-start gap-2 rounded-xl bg-red-500/10 border border-red-500/30 p-3">
          <Icon name="alert" size={16} className="text-red-400 mt-0.5 shrink-0" />
          <div>
            <p className="text-red-300 text-sm font-medium">提取失败</p>
            <p className="text-red-300/80 text-[12px] mt-0.5 whitespace-pre-wrap">{extractError}</p>
          </div>
        </div>
      )}
      
      {debugUrl && (
        <div className="rounded-xl bg-canvas-800 border border-canvas-700 p-3">
          <div className="flex items-center gap-2 mb-2">
            <Icon name="layers" size={15} className="text-brand-300" />
            <span className="text-sm font-medium text-zinc-200">基元化结果</span>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge variant="success">
              直线 {primitives.filter((p) => p.type === "line").length}
            </Badge>
            <Badge variant="warning">
              圆弧 {primitives.filter((p) => p.type === "arc").length}
            </Badge>
            <Badge variant="brand">
              折线 {primitives.filter((p) => p.type === "polyline").length}
            </Badge>
          </div>
          {primitiveDebugUrl && (
            <img
              src={primitiveDebugUrl}
              className="mt-3 w-full rounded-lg ring-1 ring-white/10"
              alt="基元化"
            />
          )}
        </div>
      )}
      
      <div className="rounded-xl bg-canvas-800 border border-canvas-700 p-3">
        <div className="flex items-center gap-2 mb-2">
          <Icon name="file" size={15} className="text-blue-400" />
          <span className="text-sm font-medium text-zinc-200">使用说明</span>
        </div>
        <ul className="text-[12px] text-zinc-400 space-y-1">
          <li>• 点击上方按钮开始轮廓提取</li>
          <li>• 系统将自动识别并分离各个工具</li>
          <li>• 提取结果将以直线/圆弧/折线形式展示</li>
        </ul>
      </div>
    </div>
  );
}