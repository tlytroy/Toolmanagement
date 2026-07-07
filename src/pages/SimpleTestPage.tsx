import { useState, useRef, useEffect } from "react";
import { SimplePaperDetector } from "@/utils/simplePaperDetector";

export function SimpleTestPage() {
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState<string>("");
  const [corners, setCorners] = useState<any[]>([]);
  const imageRef = useRef<HTMLImageElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const detectorRef = useRef<SimplePaperDetector | null>(null);

  useEffect(() => {
    detectorRef.current = new SimplePaperDetector();
  }, []);

  const handleTest = async () => {
    if (!imageRef.current) {
      setResult("请先加载图像");
      return;
    }

    setIsProcessing(true);
    setResult("处理中...");

    try {
      const points = await detectorRef.current!.detectPaperCorners(imageRef.current);

      if (points.length === 4) {
        setCorners(points);
        setResult(`✅ 检测成功！找到 ${points.length} 个角点`);

        // 在canvas上绘制结果
        if (canvasRef.current) {
          const canvas = canvasRef.current;
          const ctx = canvas.getContext('2d');
          if (ctx) {
            // 设置canvas尺寸
            canvas.width = imageRef.current.width;
            canvas.height = imageRef.current.height;

            // 绘制图像
            ctx.drawImage(imageRef.current, 0, 0);

            // 绘制检测到的四边形
            ctx.beginPath();
            ctx.moveTo(points[0].x, points[0].y);
            for (let i = 1; i < points.length; i++) {
              ctx.lineTo(points[i].x, points[i].y);
            }
            ctx.closePath();
            ctx.strokeStyle = 'green';
            ctx.lineWidth = 3;
            ctx.stroke();

            // 绘制角点
            points.forEach((point, index) => {
              ctx.beginPath();
              ctx.arc(point.x, point.y, 5, 0, 2 * Math.PI);
              ctx.fillStyle = 'red';
              ctx.fill();
              ctx.strokeStyle = 'white';
              ctx.lineWidth = 2;
              ctx.stroke();

              // 添加标签
              ctx.fillStyle = 'white';
              ctx.font = '12px Arial';
              ctx.fillText(`${index + 1}`, point.x + 8, point.y - 8);
            });
          }
        }
      } else {
        setResult(`❌ 未检测到纸张四角 (找到 ${points.length} 个点)`);
      }
    } catch (error) {
      setResult(`❌ 处理失败: ${error instanceof Error ? error.message : String(error)}`);
      console.error(error);
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">简化纸张检测测试</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <h2 className="text-lg font-semibold mb-2">测试图像</h2>
          <img
            ref={imageRef}
            src="/testpic.jpg"
            alt="Test"
            className="max-w-full h-auto border rounded"
            onLoad={() => console.log("Image loaded")}
          />
          <button
            onClick={handleTest}
            disabled={isProcessing}
            className="mt-4 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:bg-gray-400"
          >
            {isProcessing ? "处理中..." : "检测纸张"}
          </button>
        </div>

        <div>
          <h2 className="text-lg font-semibold mb-2">检测结果</h2>
          <div className="p-4 bg-gray-100 rounded">
            <p className={result.includes("✅") ? "text-green-600" : result.includes("❌") ? "text-red-600" : ""}>
              {result}
            </p>

            {corners.length > 0 && (
              <div className="mt-4">
                <h3 className="font-medium">检测到的角点:</h3>
                <ul className="mt-2">
                  {corners.map((point, index) => (
                    <li key={index} className="text-sm">
                      点 {index + 1}: ({Math.round(point.x)}, {Math.round(point.y)})
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          <h2 className="text-lg font-semibold mt-4 mb-2">标注结果</h2>
          <canvas
            ref={canvasRef}
            className="max-w-full h-auto border rounded"
          />
        </div>
      </div>
    </div>
  );
}