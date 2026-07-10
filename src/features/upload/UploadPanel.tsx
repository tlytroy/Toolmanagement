import { Icon } from "@/components/ui/icons";
import { Button } from "@/components/ui/Button";

interface UploadPanelProps {
  onUpload: () => void;
}

export function UploadPanel({ onUpload }: UploadPanelProps) {
  const tips = [
    "白色 / 浅色 A4 纸作背景",
    "正俯视、相机与纸平行",
    "均匀漫射光、避免浓重阴影",
    "工具间距 ≥ 5mm",
  ];

  return (
    <div>
      <div className="flex items-center gap-2 mb-1">
        <span className="w-7 h-7 rounded-lg bg-brand-600/20 text-brand-300 flex items-center justify-center">
          <Icon name="upload" size={15} />
        </span>
        <h2 className="text-sm font-semibold text-zinc-100">开始使用</h2>
      </div>
      <p className="text-sm text-zinc-400 mb-4">
        拖入或选择一张工具俯拍照片，系统会自动识别 A4 纸并提取轮廓。
      </p>
      <Button className="w-full" onClick={onUpload}>
        <Icon name="upload" size={16} /> 选择照片
      </Button>
      <ul className="mt-5 space-y-2.5">
        {tips.map((t) => (
          <li key={t} className="flex items-start gap-2 text-[13px] text-zinc-400">
            <Icon
              name="check"
              size={15}
              className="text-emerald-400 mt-0.5 shrink-0"
              strokeWidth={2.5}
            />
            <span>{t}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}