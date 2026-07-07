import type { OpenCV } from "@/types/opencv";
import type { Point } from "@/utils/types";

/**
 * 检测纸张四角 - 支持调试参数
 * @param cv OpenCV实例
 * @param imgElement HTMLImageElement
 * @param options 调试参数选项
 * @returns 纸张四角坐标
 */
export const detectPaperCorners = (
  cv: OpenCV,
  imgElement: HTMLImageElement,
  options?: {
    cannyLow?: number
    cannyHigh?: number
    blurSize?: number
  }
) => {
  const { cannyLow = 80, cannyHigh = 220, blurSize = 7 } = options || {}

  // 初始化OpenCV Mat对象
  const src = cv.imread(imgElement);
  const gray = new cv.Mat();
  const blurred = new cv.Mat();
  const edges = new cv.Mat();
  const contours = new cv.MatVector();
  const hierarchy = new cv.Mat();

  try {
    // 转换为灰度图
    cv.cvtColor(src, gray, cv.COLOR_RGBA2GRAY, 0);

    // 高斯模糊
    cv.GaussianBlur(gray, blurred, new cv.Size(blurSize, blurSize), 0);

    // Canny边缘检测
    cv.Canny(blurred, edges, cannyLow, cannyHigh);

    // 寻找轮廓
    cv.findContours(
      edges,
      contours,
      hierarchy,
      cv.RETR_EXTERNAL,
      cv.CHAIN_APPROX_SIMPLE,
    );

    // 寻找最大的四边形轮廓
    let maxArea = 0;
    let bestQuad: Point[] | null = null;

    for (let i = 0; i < contours.size(); i++) {
      const contour = contours.get(i);
      const area = cv.contourArea(contour);

      // 跳过太小的轮廓
      if (area < 500) continue;

      // 多边形近似
      const perimeter = cv.arcLength(contour, true);
      const approx = new cv.Mat();
      cv.approxPolyDP(contour, approx, 0.02 * perimeter, true);

      // 检查是否是四边形
      if (approx.rows === 4 && area > maxArea) {
        maxArea = area;
        bestQuad = Array.from({ length: 4 }, (_, j) => ({
          x: approx.data32S[j * 2],
          y: approx.data32S[j * 2 + 1],
        }));
      }

      approx.delete();
      contour.delete();
    }

    // 四角排序
    if (bestQuad) {
      bestQuad = sortPoints(bestQuad);
    }

    return bestQuad;
  } finally {
    // 清理资源
    src.delete();
    gray.delete();
    blurred.delete();
    edges.delete();
    contours.delete();
    hierarchy.delete();
  }
};

// 四角排序算法
function sortPoints(points: Point[]): Point[] {
  points.sort((a, b) => a.y - b.y);
  const topPoints = points.slice(0, 2).sort((a, b) => a.x - b.x);
  const bottomPoints = points.slice(2, 4).sort((a, b) => a.x - b.x);
  return [topPoints[0], topPoints[1], bottomPoints[1], bottomPoints[0]];
}

/**
 * 透视校正
 * @param cv OpenCV实例
 * @param imgElement HTMLImageElement
 * @param corners 纸张四角坐标
 * @returns 校正后的图像 dataURL
 */
export const perspectiveWarp = (
  cv: OpenCV,
  imgElement: HTMLImageElement,
  corners: Point[],
) => {
  const src = cv.imread(imgElement);

  try {
    // 目标A4纸张尺寸（800x1131像素，对应210x297mm）
    const dstSize = new cv.Size(800, 1131);
    const dstPoints = cv.matFromArray(4, 1, cv.CV_32FC2, [
      0,
      0,
      dstSize.width - 1,
      0,
      dstSize.width - 1,
      dstSize.height - 1,
      0,
      dstSize.height - 1,
    ]);

    // 源点
    const srcPoints = cv.matFromArray(4, 1, cv.CV_32FC2, [
      corners[0].x,
      corners[0].y,
      corners[1].x,
      corners[1].y,
      corners[2].x,
      corners[2].y,
      corners[3].x,
      corners[3].y,
    ]);

    // 计算透视变换矩阵
    const M = cv.getPerspectiveTransform(srcPoints, dstPoints);
    const dst = new cv.Mat();

    // 应用透视变换
    cv.warpPerspective(
      src,
      dst,
      M,
      dstSize,
      cv.INTER_LINEAR,
      cv.BORDER_CONSTANT,
      new cv.Scalar(0, 0, 0, 0),
    );

    // 转换为Data URL
    const canvas = document.createElement("canvas");
    cv.imshow(canvas, dst);
    const warpedUrl = canvas.toDataURL();

    return { warpedUrl };
  } finally {
    src.delete();
  }
};

/**
 * 提取工具轮廓
 * @param cv OpenCV实例
 * @param imageUrl 校正后的图像URL
 * @param minArea 最小轮廓面积
 * @returns 轮廓和调试图像
 */
export const extractToolContours = async (
  cv: OpenCV,
  imageUrl: string,
  minArea: number,
) => {
  return new Promise((resolve) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
      const src = cv.imread(img);
      const gray = new cv.Mat();
      const thresh = new cv.Mat();
      const contours = new cv.MatVector();
      const hierarchy = new cv.Mat();

      try {
        // 预处理
        cv.cvtColor(src, gray, cv.COLOR_RGBA2GRAY, 0);
        cv.threshold(
          gray,
          thresh,
          0,
          255,
          cv.THRESH_BINARY_INV + cv.THRESH_OTSU,
        );

        // 寻找轮廓
        cv.findContours(
          thresh,
          contours,
          hierarchy,
          cv.RETR_EXTERNAL,
          cv.CHAIN_APPROX_SIMPLE,
        );

        // 过滤小轮廓
        const filteredContours = [];
        for (let i = 0; i < contours.size(); i++) {
          const contour = contours.get(i);
          const area = cv.contourArea(contour);
          if (area >= minArea) {
            filteredContours.push(contour);
          } else {
            contour.delete();
          }
        }

        // 绘制轮廓到调试图像
        const debugImg = src.clone();
        cv.drawContours(
          debugImg,
          contours,
          -1,
          new cv.Scalar(0, 255, 0, 255),
          2,
        );

        // 转换为Data URL
        const canvas = document.createElement("canvas");
        cv.imshow(canvas, debugImg);
        const debugUrl = canvas.toDataURL();

        resolve({ contours: filteredContours, debugUrl });
      } finally {
        src.delete();
        gray.delete();
        thresh.delete();
        contours.delete();
        hierarchy.delete();
      }
    };
    img.src = imageUrl;
  });
};