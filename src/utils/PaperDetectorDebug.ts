import type { Point } from "./types";

// 动态导入OpenCV.js
let cv: any = null;

async function getCV() {
  if (cv) return cv;

  try {
    const cvModule = await import("@techstark/opencv-js");
    cv = cvModule.default || cvModule;
    console.log("[PaperDetector] OpenCV.js loaded successfully");
    return cv;
  } catch (error) {
    console.error("[PaperDetector] Failed to load OpenCV.js:", error);
    throw new Error(
      `Failed to load OpenCV.js: ${error instanceof Error ? error.message : String(error)}`,
    );
  }
}

export class PaperDetectorDebug {
  private initialized = false;

  constructor() {}

  private async ensureInitialized() {
    if (this.initialized) return;
    cv = await getCV();
    this.initialized = true;
  }

  /**
   * 寻找最佳四边形轮廓
   * @param contours 轮廓集合
   * @returns 最佳四边形及其面积
   */
  private findBestQuadrilateral(
    contours: any,
  ): { contour: any; area: number } | null {
    console.log(`[PaperDetector] Processing ${contours.size()} contours`);
    let bestContour = null;
    let maxArea = 0;

    for (let i = 0; i < contours.size(); i++) {
      const contour = contours.get(i);
      const area = cv.contourArea(contour);
      console.log(`[PaperDetector] Contour ${i}: area=${area}`);

      // 忽略太小的轮廓（使用相对面积而不是固定值）
      if (area < 100) { // 降低最小面积限制
        console.log(`[PaperDetector] Contour ${i} too small, skipping`);
        contour.delete();
        continue;
      }

      // 多epsilon尝试，提高检测成功率
      const epsilons = [0.01, 0.015, 0.02, 0.025, 0.03, 0.04]; // 增加更多epsilon值

      for (const epsilon of epsilons) {
        const approx = new cv.Mat();
        const arcLength = cv.arcLength(contour, true);
        cv.approxPolyDP(contour, approx, epsilon * arcLength, true);

        // 检查是否为四边形
        if (approx.rows === 4) {
          console.log(`[PaperDetector] Contour ${i} approximated to 4-point polygon with epsilon=${epsilon}`);

          // 检查是否为凸四边形
          const isConvex = cv.isContourConvex(approx);
          console.log(`[PaperDetector] Convex: ${isConvex}`);

          // 放宽角度约束：允许30°-150°之间的角度（更宽松）
          const anglesValid = this.areQuadrilateralAnglesValid(approx, 30, 150);
          console.log(`[PaperDetector] Angles valid: ${anglesValid}`);

          if (isConvex && anglesValid && area > maxArea) {
            console.log(`[PaperDetector] Found better candidate with area=${area}`);
            if (bestContour) {
              bestContour.delete();
            }
            maxArea = area;
            bestContour = approx.clone();
          } else {
            approx.delete();
          }
          break;
        } else {
          console.log(`[PaperDetector] Contour ${i} not a quadrilateral with epsilon=${epsilon} (rows=${approx.rows})`);
          approx.delete();
        }
      }

      contour.delete();
    }

    console.log(`[PaperDetector] Best contour area: ${maxArea}`);
    return bestContour ? { contour: bestContour, area: maxArea } : null;
  }

  /**
   * 检查四边形角度是否有效
   * @param quadrilateral 四边形轮廓
   * @param minAngle 最小角度（默认40°）
   * @param maxAngle 最大角度（默认140°）
   * @returns 是否有效
   */
  private areQuadrilateralAnglesValid(quadrilateral: any, minAngle: number = 40, maxAngle: number = 140): boolean {
    const points = [];
    for (let i = 0; i < 4; i++) {
      const point = quadrilateral.ptr(i, 0);
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
      const angle =
        Math.acos(Math.max(-1, Math.min(1, cosTheta))) * (180 / Math.PI);

      console.log(`[PaperDetector] Angle ${i}: ${angle}° (range: ${minAngle}°-${maxAngle}°)`);

      // 角度应该在指定范围内
      if (angle < minAngle || angle > maxAngle) {
        return false;
      }
    }

    return true;
  }

  /**
   * 排序四边形角点：按顺时针顺序，左上角第一个
   * @param corners 未排序的角点
   * @returns 排序后的角点
   */
  private sortQuadrilateralCorners(corners: Point[]): Point[] {
    if (corners.length !== 4) {
      return corners;
    }

    // 计算中心点
    const center = {
      x: corners.reduce((sum, p) => sum + p.x, 0) / 4,
      y: corners.reduce((sum, p) => sum + p.y, 0) / 4,
    };

    // 按极角排序
    const sorted = [...corners].sort((a, b) => {
      const angleA = Math.atan2(a.y - center.y, a.x - center.x);
      const angleB = Math.atan2(b.y - center.y, b.x - center.x);
      return angleA - angleB;
    });

    // 确保第一个点是左上角
    const topLeft = sorted.reduce((min, p) => {
      return p.x + p.y < min.x + min.y ? p : min;
    });

    // 旋转数组使左上角第一个
    const index = sorted.findIndex((p) => p === topLeft);
    if (index > 0) {
      return [...sorted.slice(index), ...sorted.slice(0, index)];
    }

    return sorted;
  }

  /**
   * 检测纸张四角 - 使用简化的文档扫描算法
   * @param imageElement HTMLImageElement
   * @returns 纸张四角坐标
   */
  async detectPaperCorners(
    imageElement: HTMLImageElement,
  ): Promise<Point[] | null> {
    await this.ensureInitialized();

    if (!this.initialized || !cv) {
      throw new Error("OpenCV.js not initialized");
    }

    try {
      console.log(
        "[PaperDetector] Starting detection for image:",
        imageElement.src,
      );

      // 读取图像
      const src = cv.imread(imageElement);
      console.log("[PaperDetector] Image size:", src.cols, "x", src.rows);

      // 转换为灰度图
      const gray = new cv.Mat();
      cv.cvtColor(src, gray, cv.COLOR_RGBA2GRAY);

      // 高斯模糊降噪
      const blurred = new cv.Mat();
      cv.GaussianBlur(gray, blurred, new cv.Size(5, 5), 0);

      // 多策略图像分割 - 提高不同光照条件下的检测成功率
      let bestContour = null;
      let maxArea = 0;

      // 策略1: Otsu阈值分割
      console.log("[PaperDetector] Trying Otsu threshold strategy");
      {
        const thresh = new cv.Mat();
        cv.threshold(
          blurred,
          thresh,
          0,
          255,
          cv.THRESH_BINARY + cv.THRESH_OTSU,
        );
        const inverted = new cv.Mat();
        cv.bitwise_not(thresh, inverted);

        const contours = new cv.MatVector();
        const hierarchy = new cv.Mat();
        cv.findContours(
          inverted,
          contours,
          hierarchy,
          cv.RETR_EXTERNAL,
          cv.CHAIN_APPROX_SIMPLE,
        );

        console.log(`[PaperDetector] Otsu strategy found ${contours.size()} contours`);
        const result = this.findBestQuadrilateral(contours);
        if (result && result.area > maxArea) {
          maxArea = result.area;
          bestContour = result.contour;
          console.log(`[PaperDetector] Otsu strategy found best contour with area=${maxArea}`);
        }

        thresh.delete();
        inverted.delete();
        contours.delete();
        hierarchy.delete();
      }

      // 策略2: 自适应阈值分割（GAUSSIAN）
      if (!bestContour || maxArea < src.cols * src.rows * 0.1) { // 降低阈值要求
        console.log("[PaperDetector] Trying Adaptive Gaussian threshold strategy");
        const thresh = new cv.Mat();
        cv.adaptiveThreshold(
          blurred,
          thresh,
          255,
          cv.ADAPTIVE_THRESH_GAUSSIAN_C,
          cv.THRESH_BINARY,
          11,
          2,
        );
        const inverted = new cv.Mat();
        cv.bitwise_not(thresh, inverted);

        const contours = new cv.MatVector();
        const hierarchy = new cv.Mat();
        cv.findContours(
          inverted,
          contours,
          hierarchy,
          cv.RETR_EXTERNAL,
          cv.CHAIN_APPROX_SIMPLE,
        );

        console.log(`[PaperDetector] Adaptive Gaussian strategy found ${contours.size()} contours`);
        const result = this.findBestQuadrilateral(contours);
        if (result && result.area > maxArea) {
          maxArea = result.area;
          bestContour = result.contour;
          console.log(`[PaperDetector] Adaptive Gaussian strategy found best contour with area=${maxArea}`);
        }

        thresh.delete();
        inverted.delete();
        contours.delete();
        hierarchy.delete();
      }

      // 策略3: 自适应阈值分割（MEAN）
      if (!bestContour || maxArea < src.cols * src.rows * 0.1) { // 降低阈值要求
        console.log("[PaperDetector] Trying Adaptive Mean threshold strategy");
        const thresh = new cv.Mat();
        cv.adaptiveThreshold(
          blurred,
          thresh,
          255,
          cv.ADAPTIVE_THRESH_MEAN_C,
          cv.THRESH_BINARY,
          11,
          2,
        );
        const inverted = new cv.Mat();
        cv.bitwise_not(thresh, inverted);

        const contours = new cv.MatVector();
        const hierarchy = new cv.Mat();
        cv.findContours(
          inverted,
          contours,
          hierarchy,
          cv.RETR_EXTERNAL,
          cv.CHAIN_APPROX_SIMPLE,
        );

        console.log(`[PaperDetector] Adaptive Mean strategy found ${contours.size()} contours`);
        const result = this.findBestQuadrilateral(contours);
        if (result && result.area > maxArea) {
          maxArea = result.area;
          bestContour = result.contour;
          console.log(`[PaperDetector] Adaptive Mean strategy found best contour with area=${maxArea}`);
        }

        thresh.delete();
        inverted.delete();
        contours.delete();
        hierarchy.delete();
      }

      // 策略4: Canny边缘检测
      if (!bestContour || maxArea < src.cols * src.rows * 0.1) { // 降低阈值要求
        console.log("[PaperDetector] Trying Canny edge detection strategy");
        const edges = new cv.Mat();
        cv.Canny(blurred, edges, 50, 150);

        const contours = new cv.MatVector();
        const hierarchy = new cv.Mat();
        cv.findContours(
          edges,
          contours,
          hierarchy,
          cv.RETR_EXTERNAL,
          cv.CHAIN_APPROX_SIMPLE,
        );

        console.log(`[PaperDetector] Canny strategy found ${contours.size()} contours`);
        const result = this.findBestQuadrilateral(contours);
        if (result && result.area > maxArea) {
          maxArea = result.area;
          bestContour = result.contour;
          console.log(`[PaperDetector] Canny strategy found best contour with area=${maxArea}`);
        }

        edges.delete();
        contours.delete();
        hierarchy.delete();
      }

      // 策略5: CLAHE增强 + 自适应阈值
      if (!bestContour || maxArea < src.cols * src.rows * 0.1) { // 降低阈值要求
        console.log("[PaperDetector] Trying CLAHE enhancement strategy");
        const clahe = cv.createCLAHE(2.0, new cv.Size(8, 8));
        const enhanced = new cv.Mat();
        clahe.apply(blurred, enhanced);

        const thresh = new cv.Mat();
        cv.adaptiveThreshold(
          enhanced,
          thresh,
          255,
          cv.ADAPTIVE_THRESH_GAUSSIAN_C,
          cv.THRESH_BINARY,
          11,
          2,
        );
        const inverted = new cv.Mat();
        cv.bitwise_not(thresh, inverted);

        const contours = new cv.MatVector();
        const hierarchy = new cv.Mat();
        cv.findContours(
          inverted,
          contours,
          hierarchy,
          cv.RETR_EXTERNAL,
          cv.CHAIN_APPROX_SIMPLE,
        );

        console.log(`[PaperDetector] CLAHE strategy found ${contours.size()} contours`);
        const result = this.findBestQuadrilateral(contours);
        if (result && result.area > maxArea) {
          maxArea = result.area;
          bestContour = result.contour;
          console.log(`[PaperDetector] CLAHE strategy found best contour with area=${maxArea}`);
        }

        clahe.delete();
        enhanced.delete();
        thresh.delete();
        inverted.delete();
        contours.delete();
        hierarchy.delete();
      }

      console.log(
        "[PaperDetector] Best contour area:",
        maxArea,
        "image area:",
        src.cols * src.rows,
        "threshold:",
        src.cols * src.rows * 0.1,
      );

      // 清理内存
      src.delete();
      gray.delete();
      blurred.delete();

      if (bestContour) {
        // 提取四角坐标
        const corners: Point[] = [];
        for (let i = 0; i < bestContour.rows; i++) {
          const point = bestContour.ptr(i, 0);
          corners.push({
            x: point[0],
            y: point[1],
          });
        }

        // 角点排序：按顺时针顺序排列，确保第一个点是左上角
        const sortedCorners = this.sortQuadrilateralCorners(corners);

        bestContour.delete();
        console.log("[PaperDetector] Found corners:", sortedCorners);
        return sortedCorners;
      } else {
        console.log("[PaperDetector] No valid quadrilateral found");
        return null;
      }
    } catch (error) {
      console.error("[PaperDetector] Detection failed:", error);
      return null;
    }
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

    if (!this.initialized || !cv) {
      throw new Error("OpenCV.js not initialized");
    }

    try {
      const src = cv.imread(imageElement);

      // 输出尺寸：宽度 800px，高度按A4比例
      const outputWidth = 800;
      const outputHeight = Math.round(outputWidth * (297 / 210)); // A4比例

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

      // 目标角点（标准矩形）
      const dstPts = new cv.Mat(4, 1, cv.CV_32FC2);
      dstPts.data32F[0] = 0;
      dstPts.data32F[1] = 0;
      dstPts.data32F[2] = outputWidth;
      dstPts.data32F[3] = 0;
      dstPts.data32F[4] = outputWidth;
      dstPts.data32F[5] = outputHeight;
      dstPts.data32F[6] = 0;
      dstPts.data32F[7] = outputHeight;

      // 透视变换矩阵
      const M = cv.getPerspectiveTransform(srcPts, dstPts);

      // 应用变换
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

      // 输出 dataURL
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
      console.error("[PaperDetector] Perspective correction failed:", error);
      throw error;
    }
  }

  /**
   * 计算像素比例
   * @param paperFormat 纸张格式
   * @returns 每毫米的像素数
   */
  calculatePixelRatio(paperFormat: string): number {
    // 根据纸张格式计算像素比例
    const paperSizes: Record<string, { width: number; height: number }> = {
      A4: { width: 210, height: 297 },
      Letter: { width: 215.9, height: 279.4 },
      A5: { width: 148, height: 210 },
    };

    const size = paperSizes[paperFormat] || paperSizes.A4;
    // 输出图像宽度固定为800px
    return 800 / size.width;
  }
}