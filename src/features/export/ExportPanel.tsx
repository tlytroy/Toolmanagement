import { Icon } from "@/components/ui/icons";
import { useStore } from "@/app/store";

export function ExportPanel() {
  const { cadResult, cadParams } = useStore();
  const { stl_base64, summary } = cadResult;

  const handleDownloadSTL = () => {
    if (!stl_base64) return;
    const byteString = atob(stl_base64);
    const bytes = new Uint8Array(byteString.length);
    for (let i = 0; i < byteString.length; i++) {
      bytes[i] = byteString.charCodeAt(i);
    }
    const blob = new Blob([bytes], { type: "application/vnd.ms-pki.stl" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const mode = cadParams.mode === "foam" ? "foam" : "gridfinity";
    a.download = `tool_${mode}.stl`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleDownloadSVG = () => {
    // SVG 导出 — 后续实现
  };

  const handleDownloadPDF = () => {
    // PDF 导出 — 后续实现
  };

  if (!stl_base64) {
    return (
      <div>
        <div className="flex items-center gap-2 mb-1">
          <span className="w-7 h-7 rounded-lg bg-brand-600/20 text-brand-300 flex items-center justify-center">
            <Icon name="download" size={15} />
          </span>
          <h2 className="text-sm font-semibold text-zinc-100">导出文件</h2>
        </div>
        <div className="mt-3 rounded-xl bg-canvas-800 border border-canvas-700 border-dashed p-5 flex flex-col items-center text-center gap-2">
          <span className="w-10 h-10 rounded-xl bg-canvas-700 text-zinc-400 flex items-center justify-center">
            <Icon name="wand" size={20} />
          </span>
          <p className="text-sm font-medium text-zinc-300">规划中</p>
          <p className="text-[12px] text-zinc-500 leading-relaxed">
            导出 STL（3D 打印）、SVG（激光切割）、PDF（校对图纸）与 Gridfinity 工程图。
          </p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <span className="w-7 h-7 rounded-lg bg-brand-600/20 text-brand-300 flex items-center justify-center">
          <Icon name="download" size={15} />
        </span>
        <h2 className="text-sm font-semibold text-zinc-100">导出文件</h2>
      </div>

      {/* 模型摘要 */}
      {summary && (
        <div className="mb-3 rounded-xl bg-canvas-800 border border-canvas-700 p-3 space-y-1">
          <div className="flex justify-between text-[11px]">
            <span className="text-zinc-500">顶点</span>
            <span className="text-zinc-300 tabular-nums">{summary.vertices.toLocaleString()}</span>
          </div>
          <div className="flex justify-between text-[11px]">
            <span className="text-zinc-500">三角面</span>
            <span className="text-zinc-300 tabular-nums">{summary.faces.toLocaleString()}</span>
          </div>
          <div className="flex justify-between text-[11px]">
            <span className="text-zinc-500">体积</span>
            <span className="text-zinc-300 tabular-nums">{summary.volume_mm3.toFixed(0)} mm³</span>
          </div>
          {summary.bounds && (
            <>
              <div className="h-px bg-canvas-700 my-1" />
              <div className="flex justify-between text-[11px]">
                <span className="text-zinc-500">X 范围</span>
                <span className="text-zinc-300 tabular-nums">{summary.bounds.x[0].toFixed(1)} ~ {summary.bounds.x[1].toFixed(1)}</span>
              </div>
              <div className="flex justify-between text-[11px]">
                <span className="text-zinc-500">Y 范围</span>
                <span className="text-zinc-300 tabular-nums">{summary.bounds.y[0].toFixed(1)} ~ {summary.bounds.y[1].toFixed(1)}</span>
              </div>
              <div className="flex justify-between text-[11px]">
                <span className="text-zinc-500">Z 范围</span>
                <span className="text-zinc-300 tabular-nums">{summary.bounds.z[0].toFixed(1)} ~ {summary.bounds.z[1].toFixed(1)}</span>
              </div>
            </>
          )}
        </div>
      )}

      {/* 导出按钮 */}
      <div className="space-y-2">
        <button
          onClick={handleDownloadSTL}
          className="w-full py-2.5 rounded-xl text-sm font-semibold transition-all bg-brand-600 hover:bg-brand-500 text-white flex items-center justify-center gap-2"
        >
          <Icon name="download" size={16} />
          下载 STL（3D 打印）
        </button>
        <button
          onClick={handleDownloadSVG}
          disabled
          className="w-full py-2.5 rounded-xl text-sm font-semibold transition-all bg-canvas-800 text-zinc-500 border border-canvas-700 cursor-not-allowed flex items-center justify-center gap-2"
        >
          <Icon name="download" size={16} />
          下载 SVG（激光切割）
        </button>
        <button
          onClick={handleDownloadPDF}
          disabled
          className="w-full py-2.5 rounded-xl text-sm font-semibold transition-all bg-canvas-800 text-zinc-500 border border-canvas-700 cursor-not-allowed flex items-center justify-center gap-2"
        >
          <Icon name="download" size={16} />
          下载 PDF（校对图纸）
        </button>
      </div>
    </div>
  );
}