import type { Point } from "./types";

// 动态导入OpenCV.js
let cv: any = null;

async function getCV() {
  if (cv) return cv;

  try {
    const cvModule = await import("@techstark/opencv-js");
    cv = cvModule.default || cvModule;
    console.log("[OptimizedPaperDetector] OpenCV.js loaded successfully");
    return cv;
  } catch (error) {
    console.error("[OptimizedPaperDetector] Failed to load OpenCV.js:", error);
    throw new Error(
      `Failed to load OpenCV.js: ${error instanceof Error ? error.message : String(error)}`,
    );
  }
}

export class OptimizedPaperDetector {
  private initializationPromise: Promise<void> | null = null;

  constructor() {
    // 自动开始初始化
    this.initialize();
  }

  private async initialize() {
    if (this.initializationPromise) return this.initializationPromise;

    this.initializationPromise = this.performInitialization();
    return this.initializationPromise;
  }

  private async performInitialization() {
    cv = await getCV();

    // 等待OpenCV完全初始化
    await new Promise(resolve => {
      const check = () => {
        if (cv && cv.Mat) {
          resolve(true);
        } else {
          setTimeout(check, 100);
        }
      };
      check();
    });
  }

  private async ensureInitialized() {
    // 确保初始化已完成
    if (this.initializationPromise) {
      await this.initializationPromise;
    } else {
      // 如果还没有开始初始化，则立即开始
      await this.initialize();
    }

    if (!cv || !cv.Mat) {
      throw new Error("OpenCV.js failed to initialize properly");
    }
  }

  /**
   * 简化版纸张检测 - 针对白纸+深色背景的场景优化
   * @param imageElement HTMLImageElement
   * @returns 纸张四角坐标
   */
  async detectPaperCorners(
    imageElement: HTMLImageElement,
  ): Promise<Point[] | null> {
    await this.ensureInitialized();

    if (!cv) {
      throw new Error("OpenCV.js not initialized");
    }

    try {
      console.log(
        "[OptimizedPaperDetector] Starting detection for image:",
        imageElement.src,
      );

      // 读取图像
      const src = cv.imread(imageElement);
      console.log("[OptimizedPaperDetector] Image size:", src.cols, "x", src.rows);

      // 转换为灰度图
      const gray = new cv.Mat();
      cv.cvtColor(src, gray, cv.COLOR_RGBA2GRAY);

      // 高斯模糊降噪（针对木纹背景）
      const blurred = new cv.Mat();
      cv.GaussianBlur(gray, blurred, new cv.Size(7, 7), 0);

      // Canny边缘检测（针对高对比度图像）
      const edges = new cv.Mat();
      cv.Canny(blurred, edges, 80, 220);

      // 膨胀操作让边缘连接
      const kernel = cv.Mat.ones(5, 5, cv.CV_8U);
      const dilated = new cv.Mat();
      cv.dilate(edges, dilated, kernel);

      // 查找轮廓
      const contours = new cv.MatVector();
      const hierarchy = new cv.Mat();
      cv.findContours(dilated, contours, hierarchy, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE);

      console.log('[OptimizedPaperDetector] 找到轮廓数量:', contours.size());

      // 寻找最大的四边形轮廓
      let bestContour = null;
      let maxArea = 0;

      for (let i = 0; i < contours.size(); i++) {
        const contour = contours.get(i);
        const area = cv.contourArea(contour);

        // 只考虑足够大的轮廓（至少占图像的5%）
        if (area > src.cols * src.rows * 0.05) {
          // 多epsilon尝试近似为多边形
          const epsilons = [0.01, 0.015, 0.02, 0.025, 0.03];

          for (const epsilon of epsilons) {
            const approx = new cv.Mat();
            const perimeter = cv.arcLength(contour, true);
            cv.approxPolyDP(contour, approx, epsilon * perimeter, true);

            // 如果是四边形
            if (approx.rows === 4) {
              // 检查角度是否合理（60°-120°）
              if (this.areAnglesValid(approx, 60, 120)) {
                if (area > maxArea) {
                  maxArea = area;
                  if (bestContour) bestContour.delete();
                  bestContour = approx.clone();
                } else {
                  approx.delete();
                }
                break;
              } else {
                approx.delete();
              }
            } else {
              approx.delete();
            }
          }
        }
        contour.delete();
      }

      // 清理
      src.delete();
      gray.delete();
      blurred.delete();
      edges.delete();
      dilated.delete();
      kernel.delete();
      contours.delete();
      hierarchy.delete();

      if (bestContour) {
        // 提取四角坐标
        const corners: Point[] = [];
        for (let i = 0; i < bestContour.rows; i++) {
          const point = bestContour.ptr(i, 0);
          corners.push({ x: point[0], y: point[1] });
        }
        bestContour.delete();

        // 排序角点
        const sortedCorners = this.sortCorners(corners);
        console.log('[OptimizedPaperDetector] 检测成功，角点坐标:', sortedCorners);
        return sortedCorners;
      } else {
        console.log('[OptimizedPaperDetector] 未能检测到纸张四角');
        return null;
      }
    } catch (error) {
      console.error('[OptimizedPaperDetector] 检测失败:', error);
      return null;
    }
  }

  /**
   * 检查四边形角度是否有效
   * @param approx 近似多边形
   * @param minAngle 最小角度
   * @param maxAngle 最大角度
   * @returns 是否有效
   */
  private areAnglesValid(approx: any, minAngle: number, maxAngle: number): boolean {
    const points = [];
    for (let i = 0; i < 4; i++) {
      const point = approx.ptr(i, 0);
      points.push({ x: point[0], y: point[1] });
    }

    // 计算四个角的角度
    for (let i = 0; i < 4; i++) {
      const p1 = points[i];
      const p2 = points[(i + 1) % 4];
      const p3 = points[(i + 2) % 4];

      // 计算向量
      const v1 = { x: p1.x - p2.x, y: p1.y - p2.y };
      const v2 = { x: p3.x - p2.x, y: p3.y - p2.y };

      // 计算夹角（弧度转角度）
      const dotProduct = v1.x * v2.x + v1.y * v2.y;
      const mag1 = Math.sqrt(v1.x ** 2 + v1.y ** 2);
      const mag2 = Math.sqrt(v2.x ** 2 + v2.y ** 2);

      if (mag1 === 0 || mag2 === 0) continue;

      const cosTheta = dotProduct / (mag1 * mag2);
      const angle = Math.acos(Math.max(-1, Math.min(1, cosTheta))) * (180 / Math.PI);

      // 角度应该在指定范围内
      if (angle < minAngle || angle > maxAngle) {
        return false;
      }
    }

    return true;
  }

  /**
   * 排序角点：左上→右上→右下→左下
   * @param corners 未排序的角点
   * @returns 排序后的角点
   */
  private sortCorners(corners: Point[]): Point[] {
    if (corners.length !== 4) return corners;

    // 计算中心点
    const centerX = corners.reduce((sum, p) => sum + p.x, 0) / 4;
    const centerY = corners.reduce((sum, p) => sum + p.y, 0) / 4;

    // 按象限排序：左上→右上→右下→左下
    return [...corners].sort((a, b) => {
      // 判断象限
      const quadA = a.x < centerX ? (a.y < centerY ? 1 : 4) : (a.y < centerY ? 2 : 3);
      const quadB = b.x < centerX ? (b.y < centerY ? 1 : 4) : (b.y < centerY ? 2 : 3);

      if (quadA !== quadB) {
        return quadA - quadB;
      }

      // 同一象限内按角度排序
      const angleA = Math.atan2(a.y - centerY, a.x - centerX);
      const angleB = Math.atan2(b.y - centerY, b.x - centerX);
      return angleA - angleB;
    });
  }

  /**
   * 应用透视校正
   * @param imageElement 原始图像
   * @param corners 纸张四角坐标
   * @returns 校正后的图像 dataURL
   */
  async applyPerspectiveCorrection(
    imageElement: HTMLImageElement,
    corners: Point[],
  ): Promise<string> {
    await this.ensureInitialized();

    if (!cv) {
      throw new Error("OpenCV.js not initialized");
    }

    try {
      const src = cv.imread(imageElement);

      // 输出尺寸：宽度 800px，高度按A4比例
      const outputWidth = 800;
      const outputHeight = Math.round(outputWidth * (297 / 210));

      // 源角点
      const srcPts = new cv.Mat(4, 1, cv.CV_32FC2);
      srcPts.data32F[0] = corners[0].x;
      srcPts.data32F[1] = corners[0].y;
      srcPts.data32F[2] = corners[1].x;
      srcPts.data32F[3] = corners[1].y;
      srcPts.data32F[4] = corners[2].x;
      srcPts.data32F[5] = corners[2].y;
      srcPts.data32F[6] = corners[3].x;
      srcPts.data32F[7] = corners[3].y;

      // 目标角点
      const dstPts = new cv.Mat(4, 1, cv.CV_32FC2);
      dstPts.data32F[0] = 0;
      dstPts.data32F[1] = 0;
      dstPts.data32F[2] = outputWidth;
      dstPts.data32F[3] = 0;
      dstPts.data32F[4] = outputWidth;
      dstPts.data32F[5] = outputHeight;
      dstPts.data32F[6] = 0;
      dstPts.data32F[7] = outputHeight;

      // 透视变换
      const M = cv.getPerspectiveTransform(srcPts, dstPts);
      const dst = new cv.Mat();
      cv.warpPerspective(
        src,
        dst,
        M,
        new cv.Size(outputWidth, outputHeight),
        cv.INTER_LINEAR,
        cv.BORDER_CONSTANT,
        new cv.Scalar(),
      );

      // 转换为data URL
      const canvas = document.createElement("canvas");
      canvas.width = outputWidth;
      canvas.height = outputHeight;
      cv.imshow(canvas, dst);
      const dataUrl = canvas.toDataURL("image/jpeg", 0.92);

      // 清理
      src.delete();
      dst.delete();
      srcPts.delete();
      dstPts.delete();
      M.delete();
      canvas.remove();

      return dataUrl;
    } catch (error) {
      console.error('[OptimizedPaperDetector] 透视校正失败:', error);
      throw error;
    }
  }
}