import { Icon } from "@/components/ui/icons";
import type { Step } from "@/app/store";

const TOOLS: { key: Step; label: string; icon: any; hint: string }[] = [
  { key: "upload", label: "上传图片", icon: "upload", hint: "导入工具俯拍照片" },
  { key: "calibration", label: "纸张校准", icon: "scan", hint: "自动识别 A4 并校正透视" },
  { key: "segmentation", label: "轮廓提取", icon: "crop", hint: "Fast+SAM 提取工具轮廓" },
  { key: "editor", label: "矢量编辑", icon: "pencil", hint: "手动微调轮廓节点" },
  { key: "params", label: "参数配置", icon: "sliders", hint: "底板/腔体厚度与偏移" },
  { key: "export", label: "导出文件", icon: "download", hint: "导出 STL / SVG / 工程图" },
];

interface LeftRailProps {
  step: Step;
  collapsed: boolean;
  onToggleCollapse: () => void;
  onSelect: (key: Step) => void;
  onUpload: () => void;
}

export function LeftRail({
  step,
  collapsed,
  onToggleCollapse,
  onSelect,
  onUpload,
}: LeftRailProps) {
  return (
    <aside
      className={`shrink-0 bg-white border-r border-slate-200 flex flex-col transition-all duration-300 ${
        collapsed ? "w-16" : "w-56"
      }`}
    >
      <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
        {TOOLS.map((t) => {
          const active = step === t.key;
          return (
            <button
              key={t.key}
              onClick={() => (t.key === "upload" ? onUpload() : onSelect(t.key))}
              className={`group w-full flex items-center gap-3 px-2.5 py-2.5 rounded-xl text-sm transition-all duration-200 ${
                active ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-50"
              }`}
              title={t.hint}
            >
              <span
                className={`shrink-0 w-9 h-9 rounded-lg flex items-center justify-center transition-colors ${
                  active
                    ? "bg-brand-600 text-white"
                    : "bg-slate-100 text-slate-500 group-hover:bg-slate-200"
                }`}
              >
                <Icon name={t.icon} size={18} />
              </span>
              {!collapsed && (
                <span className="flex-1 text-left min-w-0">
                  <span className="block font-medium leading-tight truncate">{t.label}</span>
                  <span className="block text-[11px] text-slate-400 leading-tight truncate">
                    {t.hint}
                  </span>
                </span>
              )}
              {active && !collapsed && (
                <span className="w-1.5 h-1.5 rounded-full bg-brand-500 shrink-0" />
              )}
            </button>
          );
        })}
      </nav>
      <div className="p-3 border-t border-slate-100">
        <button
          onClick={onToggleCollapse}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl text-slate-500 hover:bg-slate-50 text-sm transition-colors"
        >
          <Icon name="panelLeft" size={16} />
          {!collapsed && <span>收起侧栏</span>}
        </button>
      </div>
    </aside>
  );
}