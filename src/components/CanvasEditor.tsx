import { useEffect, useRef } from "react";
import { fabric } from "fabric";
import { useStore } from "@/app/store";

export function CanvasEditor() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imageUrl = useStore((s) => s.imageUrl);
  const setContours = useStore((s) => s.setContours);

  useEffect(() => {
    if (!canvasRef.current || !imageUrl) return;

    const canvas = new fabric.Canvas(canvasRef.current, {
      width: 800,
      height: 600,
      backgroundColor: "#eee",
    });

    // 加载图片
    fabric.Image.fromURL(imageUrl, (img) => {
      img.scaleToWidth(800);
      canvas.add(img);

      // ✅ 假轮廓（模拟 AI 结果）
      const fakePath = new fabric.Path(
        "M 200 150 L 400 150 L 450 300 L 150 300 Z",
        {
          fill: "rgba(0,150,255,0.3)",
          stroke: "blue",
          strokeWidth: 2,
          selectable: true,
        },
      );

      canvas.add(fakePath);
      setContours([fakePath]);
    });

    return () => canvas.dispose();
  }, [imageUrl]);

  return <canvas ref={canvasRef} />;
}