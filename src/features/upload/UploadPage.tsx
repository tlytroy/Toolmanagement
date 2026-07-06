import { useStore } from "@/app/store";

export function UploadPage() {
  const setImageUrl = useStore((s) => s.setImageUrl);
  const setStep = useStore((s) => s.setStep);

  const onFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImageUrl(URL.createObjectURL(file));
    setStep("editor"); // 暂时跳到 editor
  };

  return (
    <div className="p-8">
      <h2 className="text-xl mb-4">上传工具照片</h2>
      <input type="file" accept="image/*" onChange={onFile} />
    </div>
  );
}