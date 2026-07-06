import { useStore } from "@/app/store";

export function SegmentationPage() {
  const setStep = useStore((s) => s.setStep);
  const imageUrl = useStore((s) => s.imageUrl);

  // 模拟 AI 分割功能
  const handleSegmentation = () => {
    alert("执行 AI 分割（模拟）");
    // 实际实现中这里会集成 SAM（Segment Anything）ONNX 模型
  };

  const handlePointClick = () => {
    alert("点击工具区域生成掩码（模拟）");
    // 实际实现中这里会根据用户点击位置生成分割掩码
  };

  const handleNext = () => {
    setStep("editor");
  };

  return (
    <div className="p-8">
      <h2 className="text-xl mb-4">AI 工具轮廓提取</h2>

      <div className="mb-6">
        <div className="relative inline-block">
          <img
            src={imageUrl || ""}
            alt="Calibrated image"
            className="max-w-full h-auto border rounded cursor-crosshair"
            style={{ maxHeight: "400px" }}
            onClick={handlePointClick}
          />
          {/* 模拟工具轮廓覆盖层 */}
          <svg
            className="absolute top-0 left-0 w-full h-full pointer-events-none"
            viewBox="0 0 800 600"
          >
            {/* 这里会在实际实现中动态生成轮廓路径 */}
            <path
              d="M 200 150 L 400 150 L 450 300 L 150 300 Z"
              fill="rgba(0,150,255,0.3)"
              stroke="blue"
              strokeWidth="2"
            />
          </svg>
        </div>
        <p className="mt-2 text-sm text-gray-600">
          点击工具区域，AI 将自动提取轮廓（模拟效果）
        </p>
      </div>

      <div className="mb-6 p-4 bg-gray-100 rounded">
        <h3 className="font-bold mb-2">AI 分割选项</h3>
        <div className="flex gap-2 mb-4">
          <button
            onClick={handleSegmentation}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            一键 AI 分割
          </button>

          <button className="px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600">
            清除所有轮廓
          </button>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block mb-1">模型精度</label>
            <select className="w-full p-2 border rounded">
              <option>快速（较小模型）</option>
              <option>标准（平衡）</option>
              <option>精确（较大模型）</option>
            </select>
          </div>

          <div>
            <label className="block mb-1">置信度阈值</label>
            <input
              type="range"
              min="0"
              max="100"
              defaultValue="80"
              className="w-full"
            />
          </div>
        </div>
      </div>

      <div className="flex justify-between">
        <button
          onClick={() => setStep("calibration")}
          className="px-4 py-2 bg-gray-300 rounded hover:bg-gray-400"
        >
          上一步
        </button>

        <button
          onClick={handleNext}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          下一步：轮廓编辑
        </button>
      </div>
    </div>
  );
}