// 工具函数用于测试OpenCV功能
import { SimplePaperDetector } from "./simplePaperDetector";

/**
 * 测试纸张检测功能
 * @param cv OpenCV 实例
 * @param imageUrl 测试图片URL
 * @returns 检测到的四角坐标或null
 */
export async function testPaperDetection(
  cv: any,
  imageUrl: string,
): Promise<{ x: number; y: number }[] | null> {
  console.log("开始测试纸张检测功能...");

  return new Promise((resolve) => {
    const img = new Image();
    img.src = imageUrl;

    img.onload = async () => {
      try {
        const detector = new SimplePaperDetector(cv);
        const corners = await detector.detectPaperCorners(img);

        if (corners) {
          console.log("✅ 成功检测到纸张四角:");
          console.log("左上:", corners[0]);
          console.log("右上:", corners[1]);
          console.log("右下:", corners[2]);
          console.log("左下:", corners[3]);
          resolve(corners);
        } else {
          console.log("❌ 未能检测到纸张");
          resolve(null);
        }
      } catch (error) {
        console.error("❌ 检测过程中出现错误:", error);
        resolve(null);
      }
    };

    img.onerror = () => {
      console.error("❌ 图片加载失败");
      resolve(null);
    };
  });
}

/**
 * 在控制台运行测试
 */
export async function runPaperDetectionTest(cv: any) {
  console.log("🚀 启动纸张检测测试...");
  await testPaperDetection(cv, "/testpic.jpg");
}
