import { useStore } from "@/app/store";

export function CalibrationPage() {
  const setStep = useStore((s) => s.setStep);
  const imageUrl = useStore((s) => s.imageUrl);

  // 模拟纸张检测结果
  const handleAutoDetect = () => {
    alert("自动检测纸张四角（模拟）");
    // 实际实现中这里会使用 OpenCV.js 进行边缘检测和四边形拟合
  };

  const handleManualAdjust = () => {
    alert("手动调整纸张四角（模拟）");
    // 实际实现中这里会允许用户拖拽四个角点
  };

  const handleNext = () => {
    setStep("segmentation");
  };

  return (
    <div className="p-8">
      <h2 className="text-xl mb-4">纸张检测与标定</h2>

      <div className="mb-6">
        <img
          src={imageUrl || ""}
          alt="Uploaded tool"
          className="max-w-full h-auto border rounded"
          style={{ maxHeight: "400px" }}
        />
      </div>

      <div className="mb-6 p-4 bg-gray-100 rounded">
        <h3 className="font-bold mb-2">纸张检测</h3>
        <p className="mb-4 text-sm text-gray-600">
          系统将自动检测纸张四角并进行透视校正。如果自动检测不准确，您可以手动调整。
        </p>

        <div className="flex gap-2">
          <button
            onClick={handleAutoDetect}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            自动检测纸张
          </button>

          <button
            onClick={handleManualAdjust}
            className="px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600"
          >
            手动调整
          </button>
        </div>
      </div>

      <div className="mb-6 p-4 bg-gray-100 rounded">
        <h3 className="font-bold mb-2">纸张规格</h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block mb-1">纸张格式</label>
            <select className="w-full p-2 border rounded">
              <option>A4 (210×297mm)</option>
              <option>Letter (215.9×279.4mm)</option>
              <option>A5 (148×210mm)</option>
            </select>
          </div>

          <div>
            <label className="block mb-1">单位</label>
            <select className="w-full p-2 border rounded">
              <option>毫米 (mm)</option>
              <option>英寸 (in)</option>
            </select>
          </div>
        </div>
      </div>

      <div className="flex justify-between">
        <button
          onClick={() => setStep("upload")}
          className="px-4 py-2 bg-gray-300 rounded hover:bg-gray-400"
        >
          上一步
        </button>

        <button
          onClick={handleNext}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          下一步：AI 工具轮廓提取
        </button>
      </div>
    </div>
  );
}