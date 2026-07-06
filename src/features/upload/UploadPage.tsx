import { useStore } from "@/app/store";

export function UploadPage() {
  const setImageUrl = useStore((s) => s.setImageUrl);
  const setStep = useStore((s) => s.setStep);

  const onFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImageUrl(URL.createObjectURL(file));
    setStep("calibration"); // 跳到纸张检测步骤
  };

  return (
    <div className="p-8">
      <h2 className="text-xl mb-4">上传工具照片</h2>
      <div className="mb-4">
        <p className="mb-2">请将工具平放在 A4/Letter 纸上俯拍上传</p>
        <ul className="list-disc pl-5 text-sm text-gray-600 mb-4">
          <li>背景使用白色/浅色 A4 或 Letter 纸</li>
          <li>尽量正俯视拍摄，距离远 + 光学变焦</li>
          <li>均匀漫射光，避免工具投下浓重阴影</li>
          <li>工具间留间距 ≥ 5mm，不重叠</li>
        </ul>
      </div>
      <input type="file" accept="image/*" onChange={onFile} />
      <p className="mt-2 text-sm text-gray-500">支持 JPG / PNG / WebP 格式</p>
    </div>
  );
}