// 测试原始PaperDetector是否能正常工作
import { PaperDetector } from "@/utils/PaperDetector";

export async function testOriginalPaperDetector() {
  console.log("Testing original PaperDetector...");

  try {
    // 创建检测器实例
    const detector = new PaperDetector();
    console.log("PaperDetector created successfully");

    // 创建一个测试图像元素
    const img = document.createElement('img');
    img.src = '/testpic.jpg';

    // 等待图像加载
    await new Promise((resolve, reject) => {
      img.onload = resolve;
      img.onerror = reject;
    });

    console.log("Test image loaded successfully");

    // 测试检测功能
    console.log("Starting paper detection...");
    const result = await detector.detectPaperCorners(img, true);

    console.log("Paper detection completed");
    console.log("Result:", result);

    return result;
  } catch (error) {
    console.error("Original PaperDetector test failed:", error);
    throw error;
  }
}