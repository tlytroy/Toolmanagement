import { useState, useRef } from "react";
import { useStore } from "@/app/store";
import { testSamSegmentation } from "@/utils/samTest";

export function SegmentationPage() {
  const setStep = useStore((s) => s.setStep);
  const imageUrl = useStore((s) => s.imageUrl);
  const calibratedImageUrl = useStore((s) => s.calibratedImageUrl);
  const setContours = useStore((s) => s.setContours);

  const [isProcessing, setIsProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const imageRef = useRef<HTMLImageElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // 使用校准后的图像，如果没有则使用原始图像
  const displayImage = calibratedImageUrl || imageUrl;

  // 初始化SAM模型
  const initializeSam = async () => {
    if (!imageRef.current) return;

    setIsProcessing(true);
    setError(null);
    setProgress(0);

    try {
      setProgress(20);
      console.log("开始初始化SAM模型...");

      setProgress(40);
      const maskData = await testSamSegmentation(imageRef.current);

      setProgress(80);
      console.log("SAM分割完成，处理掩码数据...");

      // 将掩码数据显示在canvas上
      if (canvasRef.current && maskData) {
        const ctx = canvasRef.current.getContext('2d');
        if (ctx) {
          // 创建ImageData对象
          const imageData = new ImageData(maskData.data, maskData.width, maskData.height);
          canvasRef.current.width = maskData.width;
          canvasRef.current.height = maskData.height;
          ctx.putImageData(imageData, 0, 0);

          // 保存轮廓数据到store
          setContours([maskData]);
        }
      }

      setProgress(100);
      console.log("SAM分割处理完成");
    } catch (err) {
      console.error("SAM分割错误:", err);
      setError(err instanceof Error ? err.message : "未知错误");
    } finally {
      setIsProcessing(false);
    }
  };

  // 处理点击事件
  const handlePointClick = (e: React.MouseEvent) => {
    if (!imageRef.current || isProcessing) return;

    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    console.log(`点击位置: (${x}, ${y})`);
    // 这里可以添加更复杂的点击处理逻辑
    initializeSam();
  };

  const handleNext = () => {
    setStep("editor");
  };

  return (
    <div className="p-8">
      <h2 className="text-xl mb-4">AI 工具轮廓提取</h2>

      <div className="mb-6">
        {displayImage ? (
          <div className="relative inline-block">
            <img
              ref={imageRef}
              src={displayImage}
              alt="Calibrated image"
              className="max-w-full h-auto border rounded cursor-crosshair"
              style={{ maxHeight: "400px" }}
              onLoad={() => console.log("图像加载完成")}
              onClick={handlePointClick}
            />
            {/* SAM分割结果覆盖层 */}
            <canvas
              ref={canvasRef}
              className="absolute top-0 left-0 w-full h-full pointer-events-none"
              style={{ opacity: 0.5 }}
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
        ) : (
          <div className="h-64 bg-gray-200 rounded flex items-center justify-center">
            <p>未找到上传的图片</p>
          </div>
        )}
        <p className="mt-2 text-sm text-gray-600">
          {calibratedImageUrl
            ? "点击工具区域，AI 将自动提取轮廓（使用校准图像）"
            : "点击工具区域，AI 将自动提取轮廓（模拟效果）"}
        </p>
      </div>

      {isProcessing && (
        <div className="mb-4 p-4 bg-blue-100 rounded">
          <div className="flex items-center">
            <div className="w-full bg-gray-200 rounded-full h-2.5">
              <div
                className="bg-blue-600 h-2.5 rounded-full"
                style={{ width: `${progress}%` }}
              ></div>
            </div>
            <span className="ml-2 text-sm text-gray-700">{progress}%</span>
          </div>
          <p className="mt-2 text-sm text-gray-700">正在处理中，请稍候...</p>
        </div>
      )}

      {error && (
        <div className="mb-4 p-4 bg-red-100 text-red-700 rounded">
          <p>处理错误: {error}</p>
        </div>
      )}

      <div className="mb-6 p-4 bg-gray-100 rounded">
        <h3 className="font-bold mb-2">AI 分割选项</h3>
        <div className="flex gap-2 mb-4">
          <button
            onClick={initializeSam}
            disabled={isProcessing || !displayImage}
            className={`px-4 py-2 rounded ${
              isProcessing || !displayImage
                ? "bg-gray-400 cursor-not-allowed"
                : "bg-blue-500 text-white hover:bg-blue-600"
            }`}
          >
            {isProcessing ? "处理中..." : "一键 AI 分割"}
          </button>

          <button
            className="px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600"
            disabled={isProcessing}
          >
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