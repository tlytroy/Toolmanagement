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
  imgElement: HTMLImageElement, // 明确参数类型，杜绝传URL/File的情况
  options?: {
    cannyLow?: number
    cannyHigh?: number
    blurSize?: number
  }
) => {
  const { cannyLow = 80, cannyHigh = 220, blurSize = 7 } = options || {}

  // 防御校验：避免无效调用
  if (!cv || typeof cv.imread !== 'function' || !imgElement) {
    throw new Error('OpenCV未初始化或图片元素无效')
  }

  const src = cv.imread(imgElement) // 现在100%合法
  const gray = new (cv as any).Mat()
  const edges = new (cv as any).Mat()
  const blurred = new (cv as any).Mat()
  let paperCnt: any = null

  try {
    cv.cvtColor(src, gray, cv.COLOR_RGBA2GRAY)
    const size = new cv.Size(blurSize, blurSize);
    cv.GaussianBlur(gray, blurred, size, 0)
    cv.Canny(blurred, edges, cannyLow, cannyHigh)

    const kernel = cv.getStructuringElement(cv.MORPH_RECT, new cv.Size(5, 5))
    cv.dilate(edges, edges, kernel)

    const contours = new (cv as any).MatVector()
    const hierarchy = new (cv as any).Mat()
    cv.findContours(edges, contours, hierarchy, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)

    let maxArea = 0
    for (let i = 0; i < contours.size(); i++) {
      const cnt = contours.get(i)
      const area = cv.contourArea(cnt)
      if (area < 10000) continue

      const peri = cv.arcLength(cnt, true)
      const approx = new (cv as any).Mat()
      cv.approxPolyDP(cnt, approx, 0.02 * peri, true)

      if (approx.rows === 4 && area > maxArea) {
        maxArea = area
        paperCnt = approx.clone()
      }
      approx.delete() // 及时释放临时对象，避免内存泄漏
    }

    // 清理中间对象
    contours.delete()
    hierarchy.delete()
    kernel.delete()

    if (!paperCnt) {
      throw new Error('未检测到A4纸，请调整拍摄角度/光照，或调大Canny阈值')
    }

    // 四点排序（保持原逻辑不变）
    const points = []
    for (let i = 0; i < 4; i++) {
      points.push({
        x: paperCnt.data32S[i * 2],
        y: paperCnt.data32S[i * 2 + 1]
      })
    }
    paperCnt.delete() // 释放paperCnt

    points.sort((a, b) => a.y - b.y)
    const top = [points[0], points[1]].sort((a, b) => a.x - b.x)
    const bottom = [points[2], points[3]].sort((a, b) => a.x - b.x)

    return [top[0], top[1], bottom[1], bottom[0]]
  } finally {
    // 兜底释放：即使报错也不会内存泄漏
    src.delete()
    gray.delete()
    edges.delete()
    blurred.delete()
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
      (dstSize as any).width - 1,
      0,
      (dstSize as any).width - 1,
      (dstSize as any).height - 1,
      0,
      (dstSize as any).height - 1,
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
    const dst = new (cv as any).Mat();

    // 应用透视变换
    cv.warpPerspective(
      src,
      dst,
      M,
      dstSize,
      cv.INTER_LINEAR,
      cv.BORDER_CONSTANT,
      new (cv as any).Scalar(0, 0, 0, 0),
    );

    // 转换为Data URL
    const canvas = document.createElement("canvas");
    (cv as any).imshow(canvas, dst);
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
      const gray = new (cv as any).Mat();
      const thresh = new (cv as any).Mat();
      const contours = new (cv as any).MatVector();
      const hierarchy = new (cv as any).Mat();

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
        (cv as any).drawContours(
          debugImg,
          contours,
          -1,
          new (cv as any).Scalar(0, 255, 0, 255),
          2,
        );

        // 转换为Data URL
        const canvas = document.createElement("canvas");
        (cv as any).imshow(canvas, debugImg);
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