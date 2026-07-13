import { Icon } from "@/components/ui/icons";
import { useEffect } from "react";

interface ViewportProps {
  imgUrl?: string;
  warpedUrl?: string;
  maskUrl?: string;
  showGrid: boolean;
  zoom: number;
  onFile: (file: File | undefined) => void;
  hasImage: boolean;
  stage: 0 | 1 | 2;
  detecting: boolean;
  extracting: boolean;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onFit: () => void;
  onToggleGrid: () => void;
  step?: string;
  primitives?: any[]; // 基元数据用于显示轮廓
}

function ViewportToolBtn({
  icon,
  title,
  active,
  onClick,
}: {
  icon: any;
  title: string;
  active?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      title={title}
      onClick={onClick}
      className={`w-8 h-8 rounded-lg flex items-center justify-center transition-colors ${
        active
          ? "bg-white/10 text-zinc-100"
          : "text-zinc-400 hover:text-zinc-200 hover:bg-white/5"
      }`}
    >
      <Icon name={icon} size={16} />
    </button>
  );
}

export function Viewport({
  imgUrl,
  warpedUrl,
  maskUrl,
  showGrid,
  zoom,
  onFile,
  hasImage,
  stage,
  detecting,
  extracting,
  onZoomIn,
  onZoomOut,
  onFit,
  onToggleGrid,
  step,
  primitives,
}: ViewportProps) {
  // 当 primitives 变化时，在左侧轮廓预览画布上绘制红色轮廓线
  useEffect(() => {
    if (step !== "editor" || !primitives || primitives.length === 0) return;

    const canvas = document.getElementById('editor-contour-canvas') as HTMLCanvasElement;
    const warpImg = document.getElementById('editor-warp-img') as HTMLImageElement;
    if (!canvas || !warpImg) return;

    // 等 warp 图完全加载后匹配尺寸
    const setupAndDraw = () => {
      if (!warpImg.naturalWidth) {
        // 图片还没加载完，延迟重试
        setTimeout(setupAndDraw, 50);
        return;
      }
      canvas.width = warpImg.naturalWidth;
      canvas.height = warpImg.naturalHeight;
      canvas.style.width = warpImg.clientWidth + 'px';
      canvas.style.height = warpImg.clientHeight + 'px';

      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // 红色轮廓线
      ctx.strokeStyle = '#ef4444';
      ctx.lineWidth = 2.5;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.shadowColor = 'rgba(239, 68, 68, 0.5)';
      ctx.shadowBlur = 3;

      // Helper: backend may return [x, y] arrays instead of {x, y} objects
      const toPt = (v: any) =>
        Array.isArray(v) ? { x: v[0], y: v[1] } : v;

      primitives.forEach((primitive: any) => {
        if (primitive.type === 'line') {
          const p0 = toPt(primitive.p0);
          const p1 = toPt(primitive.p1);
          if (p0 && p1) {
            ctx.beginPath();
            ctx.moveTo(p0.x, p0.y);
            ctx.lineTo(p1.x, p1.y);
            ctx.stroke();
          }
        } else if (primitive.type === 'arc') {
          const c = toPt(primitive.center);
          if (c && primitive.radius && primitive.seg_pts && primitive.seg_pts.length > 0) {
            const seg = primitive.seg_pts;
            // 计算 seg_pts 中每个点相对于中心的角度
            const angles = seg.map((pt: any) => {
              const x = typeof pt.x === 'number' ? pt.x : pt[0];
              const y = typeof pt.y === 'number' ? pt.y : pt[1];
              return Math.atan2(y - c.y, x - c.x);
            });
            // unwrap 角度消除 2π 跳变
            for (let i = 1; i < angles.length; i++) {
              while (angles[i] - angles[i - 1] > Math.PI) angles[i] -= 2 * Math.PI;
              while (angles[i] - angles[i - 1] < -Math.PI) angles[i] += 2 * Math.PI;
            }
            const a0 = angles[0];
            const a1 = angles[angles.length - 1];
            ctx.beginPath();
            ctx.arc(c.x, c.y, primitive.radius, a0, a1, a1 > a0);
            ctx.stroke();
          }
        } else if (primitive.type === 'polyline' && primitive.points) {
          const pts = primitive.points.map(toPt);
          if (pts.length > 1) {
            ctx.beginPath();
            ctx.moveTo(pts[0].x, pts[0].y);
            for (let i = 1; i < pts.length; i++) {
              ctx.lineTo(pts[i].x, pts[i].y);
            }
            ctx.stroke();
          }
        }
      });

      // Reset shadow
      ctx.shadowBlur = 0;
    };

    // Delay to let the canvas render in DOM
    requestAnimationFrame(setupAndDraw);
  }, [primitives, step, warpedUrl]);
  return (
    <main
      className={`relative flex-1 min-w-0 canvas-scroll overflow-auto ${
        showGrid ? "canvas-grid" : "bg-canvas-950"
      }`}
    >
      {!hasImage ? (
        <label className="absolute inset-0 flex items-center justify-center cursor-pointer group">
          <div className="flex flex-col items-center gap-4 p-12 rounded-3xl border-2 border-dashed border-canvas-600 hover:border-brand-500 transition-colors duration-300 text-center">
            <span className="w-16 h-16 rounded-2xl bg-canvas-800 text-brand-400 flex items-center justify-center group-hover:bg-canvas-700 transition-colors">
              <Icon name="upload" size={30} />
            </span>
            <div>
              <p className="text-lg font-medium text-zinc-200">拖放工具照片到此处</p>
              <p className="text-sm text-zinc-500 mt-1">
                或点击选择文件 · 支持 JPG / PNG / WebP
              </p>
            </div>
          </div>
          <input
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => onFile(e.target.files?.[0])}
          />
        </label>
      ) : step === "editor" ? (
        // 编辑器模式：左侧轮廓预览 — warped 图 + 红色轮廓线
        <div className="min-h-full flex items-center justify-center p-8">
          <div
            className="relative"
            style={{
              transform: `scale(${zoom})`,
              transformOrigin: "center",
              transition: "transform 0.15s ease-out",
            }}
          >
            {/* 校正后的实物图 */}
            {warpedUrl && (
              <img
                src={warpedUrl}
                alt="工具校正图"
                className="max-w-full max-h-[78vh] rounded-xl shadow-2xl ring-1 ring-white/10"
                id="editor-warp-img"
              />
            )}
            {/* 红色轮廓叠加层 */}
            <canvas
              id="editor-contour-canvas"
              className="absolute inset-0 max-w-full max-h-[78vh] rounded-xl pointer-events-none"
              style={{ display: 'block' }}
            />
          </div>
        </div>
      ) : (
        // 其他模式：居中显示单张大图
        <div className="min-h-full flex items-center justify-center p-8">
          <div
            className="relative"
            style={{
              transform: `scale(${zoom})`,
              transformOrigin: "center",
              transition: "transform 0.15s ease-out",
            }}
          >
            {(warpedUrl || imgUrl) && (
              <img
                src={warpedUrl || imgUrl}
                alt="工作图"
                className="max-w-full max-h-[78vh] rounded-xl shadow-2xl ring-1 ring-white/10"
              />
            )}
            {maskUrl && (
              <img
                src={maskUrl}
                alt="工具蒙版"
                className="absolute inset-0 max-w-full max-h-[78vh] rounded-xl opacity-70 mix-blend-overlay"
                style={{
                  filter: 'contrast(1.2) brightness(1.1)',
                  mixBlendMode: 'multiply'
                }}
              />
            )}
          </div>
        </div>
      )}

      {/* 左上：阶段指示 */}
      {hasImage && (
        <div className="absolute top-4 left-4 glass-bar rounded-full px-3 py-1.5 flex items-center gap-2 text-xs text-zinc-300">
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              stage === 2
                ? "bg-emerald-400"
                : stage === 1
                  ? "bg-amber-400"
                  : "bg-brand-400"
            }`}
          />
          {stage === 0 ? "已导入照片" : stage === 1 ? "已识别纸张 · 待校正" : "轮廓已提取"}
          {(detecting || extracting) && (
            <Icon name="loader" size={13} className="animate-spin text-brand-300" />
          )}
        </div>
      )}

      {/* 底部居中：画布工具条 */}
      {hasImage && (
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 glass-bar rounded-full px-2 py-1.5 flex items-center gap-1 text-zinc-300">
          <ViewportToolBtn icon="pointer" active title="选择" />
          <ViewportToolBtn icon="image" title="平移" />
          <div className="w-px h-5 bg-canvas-600 mx-1" />
          <ViewportToolBtn icon="zoomOut" title="缩小" onClick={onZoomOut} />
          <span className="text-xs tabular-nums w-10 text-center">{Math.round(zoom * 100)}%</span>
          <ViewportToolBtn icon="zoomIn" title="放大" onClick={onZoomIn} />
          <ViewportToolBtn icon="maximize" title="适应窗口" onClick={onFit} />
          <div className="w-px h-5 bg-canvas-600 mx-1" />
          <ViewportToolBtn icon="grid" title="网格" active={showGrid} onClick={onToggleGrid} />
        </div>
      )}

      {/* 左下：3D 预览占位（诚实标记为待接入） */}
      {hasImage && (
        <div className="absolute bottom-4 left-4 glass-bar rounded-xl px-3 py-2 flex items-center gap-2 text-xs">
          <Icon name="box" size={15} className="text-zinc-400" />
          <div className="leading-tight">
            <p className="text-zinc-300 font-medium">3D 预览区</p>
            <p className="text-zinc-500 text-[11px]">后端几何待接入</p>
          </div>
        </div>
      )}
    </main>
  );
}