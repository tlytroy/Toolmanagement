import { Icon } from "@/components/ui/icons";
import { Button } from "@/components/ui/Button";

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

interface CalibrationPanelProps {
  detecting: boolean;
  detect: PaperDetectionResult | null;
  detectError: string | null;
  imgUrl: boolean;
  onRedetect: () => void;
  onWarp: () => void;
}

export function CalibrationPanel({ 
  detecting, 
  detect, 
  detectError, 
  imgUrl, 
  onRedetect, 
  onWarp 
}: CalibrationPanelProps) {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 mb-1">
        <span className="w-7 h-7 rounded-lg bg-brand-600/20 text-brand-300 flex items-center justify-center">
          <Icon name="scan" size={15} />
        </span>
        <h2 className="text-sm font-semibold text-zinc-100">纸张校准 & 轮廓</h2>
      </div>
      
      {detecting && (
        <div className="flex items-center gap-2 text-sm text-zinc-300">
          <Icon name="loader" size={16} className="animate-spin text-brand-300" /> 正在识别纸张…
        </div>
      )}
      
      {!detecting && detectError && (
        <div className="flex items-start gap-2 rounded-xl bg-red-500/10 border border-red-500/30 p-3">
          <Icon name="alert" size={16} className="text-red-400 mt-0.5 shrink-0" />
          <div>
            <p className="text-red-300 text-sm font-medium">检测失败</p>
            <p className="text-red-300/80 text-[12px] mt-0.5 whitespace-pre-wrap">{detectError}</p>
          </div>
        </div>
      )}
      
      {!detecting && !detectError && detect && detect.success && detect.corners && (
        <div className="rounded-xl bg-canvas-800 border border-canvas-700 p-3">
          <div className="flex items-center gap-2 text-emerald-400 mb-2">
            <Icon name="check" size={16} strokeWidth={2.5} />
            <span className="text-sm font-medium">已识别纸张四角</span>
          </div>
          <div className="grid grid-cols-2 gap-1.5 text-[12px]">
            {(
              [
                ["左上", detect.corners[0]],
                ["右上", detect.corners[1]],
                ["右下", detect.corners[2]],
                ["左下", detect.corners[3]],
              ] as [string, { x: number; y: number }][]
            ).map(([n, c]) => (
              <div
                key={n}
                className="flex justify-between bg-canvas-900 rounded-md px-2 py-1"
              >
                <span className="text-zinc-500">{n}</span>
                <span className="text-zinc-300 font-mono">
                  {Math.round(c.x)},{Math.round(c.y)}
                </span>
              </div>
            ))}
          </div>
          <p className="text-[11px] text-zinc-500 mt-2">
            {detect.mode === "strong"
              ? "首轮强命中"
              : (detect.methodCount ? `${detect.methodCount} 个方法族共识` : "")}
            {detect.confidence !== undefined ? `· 置信度 ${Math.round(detect.confidence * 100)}%` : ""}
          </p>
          {detect.skew?.message && (
            <div
              className={`mt-2 text-[11px] rounded-md px-2 py-1 ${
                detect.skew.level === "severe"
                  ? "bg-red-500/10 text-red-300"
                  : "bg-amber-500/10 text-amber-300"
              }`}
            >
              {detect.skew.message}
            </div>
          )}
          {detect.lowConfidence && (
            <div className="mt-2 text-[11px] bg-amber-500/10 text-amber-300 rounded-md px-2 py-1">
              单方法命中，结果仅供参考，建议重拍确认。
            </div>
          )}
        </div>
      )}
      
      <div className="space-y-2">
        <Button
          variant="secondary"
          className="w-full"
          onClick={onRedetect}
          disabled={!imgUrl || detecting}
        >
          <Icon name="scan" size={16} /> 重新检测
        </Button>
        <Button variant="success" className="w-full" onClick={onWarp} disabled={!detect}>
          <Icon name="scan" size={16} /> 透视校正
        </Button>
      </div>
    </div>
  );
}