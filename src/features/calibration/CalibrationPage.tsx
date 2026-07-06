import { useState, useRef, useEffect } from "react";
import { useStore } from "@/app/store";
import { PaperDetector, DetectionDebugInfo } from "@/utils/PaperDetector";
import type { Point } from "@/utils/types";

export function CalibrationPage() {
  const setStep = useStore((s) => s.setStep);
  const imageUrl = useStore((s) => s.imageUrl);
  const calibratedImageUrl = useStore((s) => s.calibratedImageUrl);
  const setCalibratedImageUrl = useStore((s) => s.setCalibratedImageUrl);

  const [isProcessing, setIsProcessing] = useState(false);
  const [detectionResult, setDetectionResult] = useState<{
    corners: Point[];
    success: boolean;
  } | null>(null);
  const [paperFormat, setPaperFormat] = useState("A4");
  const [pixelRatio, setPixelRatio] = useState(0);
  const [scaleFactor, setScaleFactor] = useState(1);
  const [manualMode, setManualMode] = useState(false);
  const [manualCorners, setManualCorners] = useState<Point[]>([]);
  const [debugImages, setDebugImages] = useState<DetectionDebugInfo[]>([]);
  const [failureReason, setFailureReason] = useState<string | null>(null);
  const [showDebug, setShowDebug] = useState(false);

  const imageRef = useRef<HTMLImageElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const detectorRef = useRef<PaperDetector | null>(null);
  const isDraggingRef = useRef<number | null>(null);

  // 初始化 PaperDetector
  useEffect(() => {
    detectorRef.current = new PaperDetector();
  }, []);

  // 计算缩放因子
  useEffect(() => {
    if (imageUrl && containerRef.current) {
      const img = new Image();
      img.onload = () => {
        if (!containerRef.current) return;
        const containerWidth = containerRef.current.clientWidth;
        const containerHeight = containerRef.current.clientHeight;
        const scale = Math.min(
          containerWidth / img.width,
          containerHeight / img.height,
          1
        );
        setScaleFactor(scale);
      };
      img.src = imageUrl;
    }
  }, [imageUrl]);

  // 初始化手动角点
  useEffect(() => {
    if (manualMode && manualCorners.length === 0 && imageRef.current) {
      const img = imageRef.current;
      setManualCorners([
        { x: img.width * 0.15, y: img.height * 0.15 },
        { x: img.width * 0.85, y: img.height * 0.15 },
        { x: img.width * 0.85, y: img.height * 0.85 },
        { x: img.width * 0.15, y: img.height * 0.85 },
      ]);
    }
  }, [manualMode, manualCorners.length]);

  // 自动检测纸张四角
  const handleAutoDetect = async () => {
    if (!imageUrl) return;
    if (!imageRef.current) return;

    setIsProcessing(true);
    setFailureReason(null);
    setDebugImages([]);

    try {
      const result = await detectorRef.current!.detectPaperCorners(
        imageRef.current,
        true // 启用 debug
      );

      setDebugImages(result.debugInfo);

      if (result.corners && result.corners.length === 4) {
        setDetectionResult({ corners: result.corners, success: true });

        // 应用透视校正
        const correctedImageUrl = await detectorRef.current!.applyPerspectiveCorrection(
          imageRef.current,
          result.corners,
          paperFormat
        );
        setCalibratedImageUrl(correctedImageUrl);

        const ratio = detectorRef.current!.calculatePixelRatio(paperFormat);
        setPixelRatio(ratio);
        setManualMode(false);
      } else {
        setManualMode(true);
        // 显示诊断信息
        const lastInfo = result.debugInfo[result.debugInfo.length - 1];
        if (lastInfo?.reason) {
          setFailureReason(lastInfo.reason);
        }
      }
    } catch (error) {
      console.error("纸张检测失败:", error);
      setManualMode(true);
      setFailureReason(`检测出错: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setIsProcessing(false);
    }
  };

  // 拖拽相关
  const handleMouseDown = (index: number, e: React.MouseEvent) => {
    e.preventDefault();
    isDraggingRef.current = index;
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isDraggingRef.current === null || !imageRef.current) return;
    const container = containerRef.current;
    if (!container) return;

    const rect = container.getBoundingClientRect();
    // 获取鼠标相对于容器的位置
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    // 获取图片在容器中的偏移（居中布局）
    const img = imageRef.current;
    const imgDisplayWidth = img.width * scaleFactor;
    const imgDisplayHeight = img.height * scaleFactor;
    const offsetX = (container.clientWidth - imgDisplayWidth) / 2;
    const offsetY = (container.clientHeight - imgDisplayHeight) / 2;

    // 转换到原始图片坐标
    const x = Math.round((mouseX - offsetX) / scaleFactor);
    const y = Math.round((mouseY - offsetY) / scaleFactor);

    const boundedX = Math.max(0, Math.min(img.width, x));
    const boundedY = Math.max(0, Math.min(img.height, y));

    const newCorners = [...manualCorners];
    newCorners[isDraggingRef.current] = { x: boundedX, y: boundedY };
    setManualCorners(newCorners);
  };

  const handleMouseUp = () => {
    isDraggingRef.current = null;
  };

  // 应用手动调整
  const applyManualAdjustment = async () => {
    if (!imageRef.current || manualCorners.length !== 4) return;

    setIsProcessing(true);
    try {
      const correctedImageUrl = await detectorRef.current!.applyPerspectiveCorrection(
        imageRef.current,
        manualCorners,
        paperFormat
      );
      setCalibratedImageUrl(correctedImageUrl);
      setDetectionResult({ corners: manualCorners, success: true });

      const ratio = detectorRef.current!.calculatePixelRatio(paperFormat);
      setPixelRatio(ratio);
      setManualMode(false);
    } catch (error) {
      console.error("手动调整失败:", error);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleNext = () => {
    setStep("segmentation");
  };

  // 将原始图片坐标转换为显示坐标
  const toDisplayCoords = (point: Point) => {
    const img = imageRef.current;
    if (!img) return { left: 0, top: 0 };

    const imgDisplayWidth = img.width * scaleFactor;
    const imgDisplayHeight = img.height * scaleFactor;
    const offsetX = (containerRef.current?.clientWidth || 0 - imgDisplayWidth) / 2;
    const offsetY = (containerRef.current?.clientHeight || 0 - imgDisplayHeight) / 2;

    return {
      left: offsetX + point.x * scaleFactor,
      top: offsetY + point.y * scaleFactor,
    };
  };

  const paperSizes = {
    A4: { width: 210, height: 297, label: "A4 (210×297mm)" },
    Letter: { width: 215.9, height: 279.4, label: "Letter (215.9×279.4mm)" },
    A5: { width: 148, height: 210, label: "A5 (148×210mm)" },
  };

  const cornersToShow = manualMode ? manualCorners : (detectionResult?.corners ?? []);

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <h2 className="text-2xl font-bold mb-6 text-gray-800">纸张检测与标定</h2>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧：控制面板 */}
        <div className="lg:col-span-1 space-y-4">
          <div className="bg-white rounded-lg shadow p-4">
            <h3 className="text-base font-semibold mb-3 text-gray-700">纸张规格</h3>
            <select
              className="w-full p-2 border rounded text-sm"
              value={paperFormat}
              onChange={(e) => setPaperFormat(e.target.value)}
            >
              <option value="A4">{paperSizes.A4.label}</option>
              <option value="Letter">{paperSizes.Letter.label}</option>
              <option value="A5">{paperSizes.A5.label}</option>
            </select>

            {pixelRatio > 0 && (
              <div className="mt-2 p-2 bg-blue-50 rounded text-xs text-blue-800">
                标定: 1mm = {pixelRatio.toFixed(2)} px
              </div>
            )}
          </div>

          <div className="bg-white rounded-lg shadow p-4 space-y-3">
            <button
              onClick={handleAutoDetect}
              disabled={isProcessing || !imageUrl}
              className={`w-full py-2.5 rounded text-sm font-medium transition ${
                isProcessing || !imageUrl
                  ? "bg-gray-200 text-gray-400"
                  : "bg-blue-600 text-white hover:bg-blue-700"
              }`}
            >
              {isProcessing ? "检测中..." : "自动检测纸张"}
            </button>

            <button
              onClick={() => {
                setManualMode(true);
                setFailureReason(null);
              }}
              disabled={!imageUrl}
              className={`w-full py-2.5 rounded text-sm font-medium transition ${
                !imageUrl
                  ? "bg-gray-200 text-gray-400"
                  : "bg-gray-600 text-white hover:bg-gray-700"
              }`}
            >
              手动标记角点
            </button>

            <button
              onClick={() => setShowDebug(!showDebug)}
              className="w-full py-2 border rounded text-xs text-gray-500 hover:bg-gray-50"
            >
              {showDebug ? "隐藏调试信息" : "显示调试信息"}
            </button>
          </div>

          {/* 失败原因提示 */}
          {failureReason && (
            <div className="bg-red-50 border border-red-200 rounded p-3 text-xs text-red-700">
              <p className="font-medium mb-1">检测失败原因：</p>
              <p>{failureReason}</p>
            </div>
          )}

          {/* 操作提示 */}
          <div className="bg-white rounded-lg shadow p-4 text-xs text-gray-500 space-y-1">
            <p>• 把工具放在白纸上，俯拍照片</p>
            <p>• 纸张应占画面至少 10%</p>
            <p>• 纸张和背景要有明显色差</p>
            <p>• 自动检测失败可手动标记四角</p>
          </div>
        </div>

        {/* 右侧：图片显示区域 */}
        <div className="lg:col-span-2 space-y-4">
          <div className="bg-white rounded-lg shadow p-4">
            <h3 className="text-base font-semibold mb-3 text-gray-700">
              {manualMode ? "手动标记四角" : "纸张检测预览"}
            </h3>

            <div
              ref={containerRef}
              className="relative w-full h-[500px] bg-gray-100 rounded overflow-hidden border flex items-center justify-center"
              onMouseMove={manualMode ? handleMouseMove : undefined}
              onMouseUp={manualMode ? handleMouseUp : undefined}
              onMouseLeave={manualMode ? handleMouseUp : undefined}
            >
              {imageUrl ? (
                <img
                  ref={imageRef}
                  src={calibratedImageUrl || imageUrl}
                  alt="Uploaded"
                  className="max-w-full max-h-full object-contain"
                  style={{ cursor: manualMode ? "crosshair" : "default" }}
                />
              ) : (
                <p className="text-gray-400 text-sm">请先上传图片</p>
              )}

              {/* 角点标记层 */}
              {imageUrl && cornersToShow.length === 4 && imageRef.current && (
                <svg
                  className="absolute inset-0 pointer-events-none"
                  style={{ zIndex: 10 }}
                >
                  <polygon
                    points={cornersToShow
                      .map((p) => toDisplayCoords(p))
                      .map((d) => `${d.left},${d.top}`)
                      .join(" ")}
                    fill="rgba(0,200,0,0.1)"
                    stroke={manualMode ? "#3b82f6" : "#22c55e"}
                    strokeWidth="2"
                    strokeDasharray={manualMode ? "6,3" : "none"}
                  />
                </svg>
              )}

              {/* 角点圆点 */}
              {imageUrl && cornersToShow.length === 4 && imageRef.current && (
                <div className="absolute inset-0" style={{ zIndex: 20 }}>
                  {cornersToShow.map((point, index) => {
                    const d = toDisplayCoords(point);
                    return (
                      <div
                        key={index}
                        className={`absolute w-5 h-5 rounded-full border-2 border-white shadow cursor-pointer
                          ${manualMode ? "bg-blue-500 hover:bg-blue-600" : "bg-green-500"}
                        `}
                        style={{
                          left: d.left - 10,
                          top: d.top - 10,
                          pointerEvents: manualMode ? "auto" : "none",
                        }}
                        onMouseDown={manualMode ? (e) => handleMouseDown(index, e) : undefined}
                      >
                        <span className="absolute -top-5 left-1/2 -translate-x-1/2 text-xs font-bold text-white">
                          {["TL", "TR", "BR", "BL"][index]}
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* 手动模式按钮 */}
            {manualMode && (
              <div className="mt-3 flex justify-end gap-3">
                <button
                  onClick={() => {
                    setManualMode(false);
                    setManualCorners([]);
                  }}
                  className="px-4 py-2 border rounded text-sm text-gray-600 hover:bg-gray-50"
                >
                  取消
                </button>
                <button
                  onClick={applyManualAdjustment}
                  disabled={isProcessing || manualCorners.length !== 4}
                  className={`px-4 py-2 rounded text-sm font-medium ${
                    isProcessing || manualCorners.length !== 4
                      ? "bg-gray-200 text-gray-400"
                      : "bg-blue-600 text-white hover:bg-blue-700"
                  }`}
                >
                  {isProcessing ? "处理中..." : "应用标记"}
                </button>
              </div>
            )}

            {/* 非手动模式下的导航按钮 */}
            {!manualMode && (
              <div className="mt-4 flex justify-between">
                <button
                  onClick={() => setStep("upload")}
                  className="px-4 py-2 border rounded text-sm text-gray-600 hover:bg-gray-50"
                >
                  上一步
                </button>
                <button
                  onClick={handleNext}
                  disabled={!calibratedImageUrl}
                  className={`px-4 py-2 rounded text-sm font-medium ${
                    calibratedImageUrl
                      ? "bg-blue-600 text-white hover:bg-blue-700"
                      : "bg-gray-200 text-gray-400"
                  }`}
                >
                  下一步：AI 工具轮廓提取
                </button>
              </div>
            )}
          </div>

          {/* 调试信息区域 */}
          {showDebug && debugImages.length > 0 && (
            <div className="bg-white rounded-lg shadow p-4">
              <h3 className="text-base font-semibold mb-3 text-gray-700">检测调试信息</h3>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {debugImages
                  .filter((info) => info.thresholdImage)
                  .map((info, index) => (
                    <div key={index} className="text-center">
                      <img
                        src={info.thresholdImage}
                        alt={info.strategy}
                        className="w-full h-auto rounded border"
                      />
                      <p className="mt-1 text-xs text-gray-500">
                        {info.strategy} ({info.candidateCount} 个候选)
                      </p>
                    </div>
                  ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
