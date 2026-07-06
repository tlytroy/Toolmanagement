import { useState, useRef, useEffect } from "react";
import { useStore } from "@/app/store";
import { PaperDetector } from "@/utils/PaperDetector";

interface Point {
  x: number;
  y: number;
}

export function CalibrationPage() {
  const setStep = useStore((s) => s.setStep);
  const imageUrl = useStore((s) => s.imageUrl);
  const calibratedImageUrl = useStore((s) => s.calibratedImageUrl);
  const setCalibratedImageUrl = useStore((s) => s.setCalibratedImageUrl);

  const [isProcessing, setIsProcessing] = useState(false);
  const [detectionResult, setDetectionResult] = useState<{ corners: Point[]; success: boolean } | null>(null);
  const [paperFormat, setPaperFormat] = useState("A4");
  const [pixelRatio, setPixelRatio] = useState(0);
  const [scaleFactor, setScaleFactor] = useState(1);
  const [manualMode, setManualMode] = useState(false);

  const imageRef = useRef<HTMLImageElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const detectorRef = useRef<PaperDetector | null>(null);

  // 初始化 PaperDetector
  useEffect(() => {
    detectorRef.current = new PaperDetector();
  }, []);

  // 计算缩放因子
  useEffect(() => {
    if (imageUrl && containerRef.current) {
      const img = new Image();
      img.onload = () => {
        const containerWidth = containerRef.current!.clientWidth;
        const containerHeight = containerRef.current!.clientHeight;
        const scale = Math.min(
          containerWidth / img.width,
          containerHeight / img.height,
          1 // 不放大图片
        );
        setScaleFactor(scale);
      };
      img.src = imageUrl;
    }
  }, [imageUrl]);

  // 自动检测纸张四角
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
        setManualMode(true);
        alert("未能自动检测到完整的纸张轮廓，请手动调整纸张边界。");
      }
    } catch (error) {
      console.error("纸张检测失败:", error);
      setManualMode(true);
      alert("自动检测失败，请手动调整纸张边界。");
    } finally {
      setIsProcessing(false);
    }
  };

  // 应用手动调整（简化版本）
  const applyManualAdjustment = async () => {
    if (!imageRef.current) return;

    setIsProcessing(true);
    try {
      // 使用默认的角点进行透视校正
      const defaultCorners = [
        { x: 100, y: 100 },
        { x: 700, y: 100 },
        { x: 700, y: 500 },
        { x: 100, y: 500 }
      ];

      // 应用透视校正
      const correctedImageUrl = await detectorRef.current!.applyPerspectiveCorrection(
        imageRef.current,
        defaultCorners
      );

      setCalibratedImageUrl(correctedImageUrl);

      // 计算像素比例
      const ratio = detectorRef.current!.calculatePixelRatio(paperFormat);
      setPixelRatio(ratio);

      setManualMode(false);
      alert(`手动调整完成！\n透视校正已完成。\n像素比例: ${ratio.toFixed(2)} pixels/mm`);
    } catch (error) {
      console.error("手动调整失败:", error);
      alert("手动调整失败，请重试。");
    } finally {
      setIsProcessing(false);
    }
  };

  const handleNext = () => {
    setStep("segmentation");
  };

  const paperSizes = {
    A4: { width: 210, height: 297, label: "A4 (210×297mm)" },
    Letter: { width: 215.9, height: 279.4, label: "Letter (215.9×279.4mm)" },
    A5: { width: 148, height: 210, label: "A5 (148×210mm)" }
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <h2 className="text-2xl font-bold mb-6 text-gray-800">纸张检测与标定</h2>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧：控制面板 */}
        <div className="lg:col-span-1 space-y-6">
          <div className="bg-white rounded-lg shadow-md p-6">
            <h3 className="text-lg font-semibold mb-4 text-gray-700">纸张规格</h3>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">纸张类型</label>
                <select
                  className="w-full p-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  value={paperFormat}
                  onChange={(e) => setPaperFormat(e.target.value)}
                >
                  <option value="A4">{paperSizes.A4.label}</option>
                  <option value="Letter">{paperSizes.Letter.label}</option>
                  <option value="A5">{paperSizes.A5.label}</option>
                </select>
              </div>

              {pixelRatio > 0 && (
                <div className="p-3 bg-blue-50 rounded-md">
                  <p className="text-sm text-blue-800">
                    <span className="font-medium">标定信息:</span> 1mm = {pixelRatio.toFixed(2)} pixels
                  </p>
                </div>
              )}
            </div>
          </div>

          <div className="bg-white rounded-lg shadow-md p-6">
            <h3 className="text-lg font-semibold mb-4 text-gray-700">检测控制</h3>

            <div className="space-y-4">
              <button
                onClick={handleAutoDetect}
                disabled={isProcessing || !imageUrl}
                className={`w-full py-3 px-4 rounded-md font-medium transition-colors ${
                  isProcessing || !imageUrl
                    ? "bg-gray-300 text-gray-500 cursor-not-allowed"
                    : "bg-blue-600 text-white hover:bg-blue-700"
                }`}
              >
                {isProcessing ? "检测中..." : "自动检测纸张"}
              </button>

              <button
                onClick={() => setManualMode(true)}
                disabled={!imageUrl}
                className={`w-full py-3 px-4 rounded-md font-medium transition-colors ${
                  !imageUrl
                    ? "bg-gray-300 text-gray-500 cursor-not-allowed"
                    : "bg-gray-600 text-white hover:bg-gray-700"
                }`}
              >
                手动调整边界
              </button>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow-md p-6">
            <h3 className="text-lg font-semibold mb-4 text-gray-700">操作指南</h3>
            <ul className="space-y-2 text-sm text-gray-600">
              <li className="flex items-start">
                <span className="text-blue-500 mr-2">•</span>
                <span>系统会自动检测纸张四角并进行透视校正</span>
              </li>
              <li className="flex items-start">
                <span className="text-blue-500 mr-2">•</span>
                <span>如果自动检测失败，可以手动调整边界</span>
              </li>
              <li className="flex items-start">
                <span className="text-blue-500 mr-2">•</span>
                <span>选择正确的纸张类型以获得准确的尺寸标定</span>
              </li>
            </ul>
          </div>
        </div>

        {/* 右侧：图片显示区域 */}
        <div className="lg:col-span-2">
          <div className="bg-white rounded-lg shadow-md p-6">
            <h3 className="text-lg font-semibold mb-4 text-gray-700">
              {manualMode ? "手动调整纸张边界" : "纸张检测预览"}
            </h3>

            <div
              ref={containerRef}
              className="relative w-full h-[500px] bg-gray-100 rounded-lg overflow-hidden border border-gray-300 flex items-center justify-center"
            >
              {imageUrl ? (
                <>
                  <img
                    ref={imageRef}
                    src={calibratedImageUrl || imageUrl}
                    alt="Uploaded tool"
                    className="max-w-full max-h-full object-contain"
                    style={{
                      transform: `scale(${scaleFactor})`,
                      transformOrigin: 'top left'
                    }}
                  />

                  {/* 显示检测到的角点 */}
                  {detectionResult && (
                    <div
                      className="absolute inset-0 pointer-events-none"
                      style={{
                        transform: `scale(${scaleFactor})`,
                        transformOrigin: 'top left'
                      }}
                    >
                      {/* 角点标记 */}
                      {detectionResult.corners.map((point, index) => (
                        <div
                          key={index}
                          className="absolute w-4 h-4 rounded-full border-2 border-white bg-green-500 transform -translate-x-1/2 -translate-y-1/2"
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
                            points={`
                              ${detectionResult.corners[0].x},${detectionResult.corners[0].y}
                              ${detectionResult.corners[1].x},${detectionResult.corners[1].y}
                              ${detectionResult.corners[2].x},${detectionResult.corners[2].y}
                              ${detectionResult.corners[3].x},${detectionResult.corners[3].y}
                            `}
                            fill="none"
                            stroke="green"
                            strokeWidth="2"
                          />
                        )}
                      </svg>
                    </div>
                  )}
                </>
              ) : (
                <div className="text-center text-gray-500">
                  <p>请先上传图片</p>
                </div>
              )}
            </div>

            {/* 手动调整模式下的操作按钮 */}
            {manualMode && (
              <div className="mt-4 flex justify-end space-x-3">
                <button
                  onClick={() => setManualMode(false)}
                  disabled={isProcessing}
                  className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                >
                  取消
                </button>
                <button
                  onClick={applyManualAdjustment}
                  disabled={isProcessing}
                  className={`px-4 py-2 rounded-md font-medium ${
                    isProcessing
                      ? "bg-gray-300 text-gray-500 cursor-not-allowed"
                      : "bg-blue-600 text-white hover:bg-blue-700"
                  }`}
                >
                  {isProcessing ? "处理中..." : "应用默认调整"}
                </button>
              </div>
            )}

            {/* 下一步按钮 */}
            {!manualMode && (
              <div className="mt-6 flex justify-between">
                <button
                  onClick={() => setStep("upload")}
                  className="px-6 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
                >
                  上一步
                </button>

                <button
                  onClick={handleNext}
                  disabled={!calibratedImageUrl}
                  className={`px-6 py-2 rounded-md font-medium ${
                    calibratedImageUrl
                      ? "bg-blue-600 text-white hover:bg-blue-700"
                      : "bg-gray-300 text-gray-500 cursor-not-allowed"
                  }`}
                >
                  下一步：AI 工具轮廓提取
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}