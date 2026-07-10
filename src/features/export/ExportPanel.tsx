import { Icon } from "@/components/ui/icons";

export function ExportPanel() {
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