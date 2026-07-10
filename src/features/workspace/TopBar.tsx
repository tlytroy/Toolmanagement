import { Icon } from "@/components/ui/icons";
import { Button } from "@/components/ui/Button";

interface TopBarProps {
  hasGeometry: boolean;
}

export function TopBar({ hasGeometry }: TopBarProps) {
  return (
    <header className="h-14 shrink-0 bg-white border-b border-slate-200 flex items-center justify-between px-4 z-20">
      <div className="flex items-center gap-2.5">
        <span className="w-8 h-8 rounded-lg bg-brand-600 text-white flex items-center justify-center shadow-sm">
          <Icon name="box" size={18} />
        </span>
        <div className="leading-tight">
          <p className="font-semibold text-slate-800 text-sm">工具嵌件生成器</p>
          <p className="text-[11px] text-slate-400">照片 → 收纳嵌件</p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <span className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-100 text-slate-600 text-xs font-medium">
          <Icon name="aperture" size={13} /> A4
        </span>
        <span className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-100 text-slate-600 text-xs font-medium">
          <Icon name="ruler" size={13} /> 0.3mm 默认
        </span>
        <div className="w-px h-5 bg-slate-200 mx-1" />
        <Button variant="ghost" size="sm" disabled title="设置（规划中）">
          <Icon name="settings" size={15} /> 设置
        </Button>
        <Button
          size="sm"
          disabled={!hasGeometry}
          title={hasGeometry ? "生成 3D 嵌件" : "需先完成轮廓提取"}
        >
          <Icon name="sparkles" size={15} /> 生成嵌件
        </Button>
      </div>
    </header>
  );
}