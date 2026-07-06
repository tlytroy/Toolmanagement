import { useState, useRef, useEffect } from "react";
import { useStore } from "@/app/store";
import { PaperDetector } from "@/utils/PaperDetector";

export function CalibrationPage() {
  const setStep = useStore((s) => s.setStep);
  const imageUrl = useStore((s) => s.imageUrl);
  const calibratedImageUrl = useStore((s) => s.calibratedImageUrl);
  const setCalibratedImageUrl = useStore((s) => s.setCalibratedImageUrl);

  const [isProcessing, setIsProcessing] = useState(false);
  const [detectionResult, setDetectionResult] = useState(null);
  const [paperFormat, setPaperFormat] = useState("A4");
  const [pixelRatio, setPixelRatio] = useState(0);
  const imageRef = useRef<HTMLImageElement>(null);
  const detectorRef = useRef<PaperDetector | null>(null);

  // 初始化 PaperDetector
  useEffect(() => {
    detectorRef.current = new PaperDetector();
  }, []);

  // 实际纸张检测功能
  const handleAutoDetect = async () => {
    if (!imageUrl) {
      alert("请先上传图片");
      return;
    }

    if (!imageRef.current) {
      alert("图片未加载完成，请稍后重试");
      return;
    }

    setIsProcessing(true);
    try {
      // 使用真实的 OpenCV.js 纸张检测功能
      const corners = await detectorRef.current!.detectPaperCorners(imageRef.current);

      if (corners && corners.length === 4) {
        setDetectionResult({ corners, success: true });

        // 应用透视校正
        const correctedImageUrl = await detectorRef.current!.applyPerspectiveCorrection(
          imageRef.current,
          corners
        );

        setCalibratedImageUrl(correctedImageUrl);

        // 计算像素比例
        const ratio = detectorRef.current!.calculatePixelRatio(paperFormat);
        setPixelRatio(ratio);

        alert(`纸张检测完成！\n检测到纸张四角并完成透视校正。\n像素比例: ${ratio.toFixed(2)} pixels/mm`);
      } else {
        alert("未能检测到完整的纸张轮廓，请手动调整或上传新的图片。");
      }
    } catch (error) {
      console.error("纸张检测失败:", error);
      alert("纸张检测失败：" + (error as Error).message + "\n请重试或手动调整。");
    } finally {
      setIsProcessing(false);
    }
  };

  const handleManualAdjust = () => {
    alert("进入手动调整模式\n实际实现中将允许您拖拽四个角点来调整纸张边界。");
  };

  const handleNext = () => {
    setStep("segmentation");
  };

  return (
    <div className="p-8">
      <h2 className="text-xl mb-4">纸张检测与标定</h2>

      <div className="mb-6">
        {imageUrl ? (
          <div className="relative">
            <img
              ref={imageRef}
              src={calibratedImageUrl || imageUrl}
              alt="Uploaded tool"
              className="max-w-full h-auto border rounded"
              style={{ maxHeight: "400px" }}
              onLoad={() => console.log("Image loaded")}
            />
            {/* 如果有检测结果，显示角点标记 */}
            {detectionResult && detectionResult.corners && (
              <div className="absolute inset-0 pointer-events-none">
                {detectionResult.corners.map((point, index) => (
                  <div
                    key={index}
                    className="absolute w-4 h-4 bg-red-500 rounded-full border-2 border-white transform -translate-x-1/2 -translate-y-1/2"
                    style={{
                      left: `${point.x}px`,
                      top: `${point.y}px`,
                    }}
                  />
                ))}
                {/* 连接角点形成边框 */}
                <svg
                  className="absolute top-0 left-0 w-full h-full pointer-events-none"
                  style={{ zIndex: 10 }}
                >
                  {detectionResult.corners.length === 4 && (
                    <polygon
                      points={`${detectionResult.corners[0].x},${detectionResult.corners[0].y}
                              ${detectionResult.corners[1].x},${detectionResult.corners[1].y}
                              ${detectionResult.corners[2].x},${detectionResult.corners[2].y}
                              ${detectionResult.corners[3].x},${detectionResult.corners[3].y}`}
                      fill="none"
                      stroke="red"
                      strokeWidth="2"
                    />
                  )}
                </svg>
              </div>
            )}
          </div>
        ) : (
          <div className="h-64 bg-gray-200 rounded flex items-center justify-center">
            <p>未找到上传的图片</p>
          </div>
        )}
      </div>

      <div className="mb-6 p-4 bg-gray-100 rounded">
        <h3 className="font-bold mb-2">纸张检测</h3>
        <p className="mb-4 text-sm text-gray-600">
          系统将自动检测纸张四角并进行透视校正。如果自动检测不准确，您可以手动调整。
        </p>

        <div className="flex gap-2">
          <button
            onClick={handleAutoDetect}
            disabled={isProcessing}
            className={`px-4 py-2 rounded hover:bg-blue-600 text-white ${
              isProcessing ? "bg-gray-400" : "bg-blue-500"
            }`}
          >
            {isProcessing ? "检测中..." : "自动检测纸张"}
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
            <select
              className="w-full p-2 border rounded"
              value={paperFormat}
              onChange={(e) => setPaperFormat(e.target.value)}
            >
              <option value="A4">A4 (210×297mm)</option>
              <option value="Letter">Letter (215.9×279.4mm)</option>
              <option value="A5">A5 (148×210mm)</option>
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

        {pixelRatio > 0 && (
          <div className="mt-4 p-2 bg-blue-50 rounded">
            <p className="text-sm">
              <strong>标定信息:</strong> 1mm = {pixelRatio.toFixed(2)} pixels
            </p>
          </div>
        )}
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
          disabled={!calibratedImageUrl}
          className={`px-4 py-2 rounded text-white ${
            calibratedImageUrl
              ? "bg-blue-500 hover:bg-blue-600"
              : "bg-gray-400 cursor-not-allowed"
          }`}
        >
          下一步：AI 工具轮廓提取
        </button>
      </div>
    </div>
  );
}