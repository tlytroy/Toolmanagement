// 纸张检测功能实现
import * as cv from '@techstark/opencv-js';

export class PaperDetector {
  private cv: any = null;

  constructor() {
    this.init();
  }

  private async init() {
    try {
      // 初始化 OpenCV.js
      this.cv = cv;
      console.log("OpenCV.js initialized successfully");
    } catch (error) {
      console.error("Failed to initialize OpenCV.js:", error);
    }
  }

  /**
   * 检测纸张四角
   * @param imageElement HTMLImageElement
   * @returns 纸张四角坐标
   */
  async detectPaperCorners(imageElement: HTMLImageElement): Promise<{x: number, y: number}[] | null> {
    if (!this.cv) {
      throw new Error("OpenCV.js not initialized");
    }

    try {
      // 创建源图像矩阵
      const src = this.cv.imread(imageElement);

      // 保存原始尺寸
      const originalWidth = src.cols;
      const originalHeight = src.rows;

      // 为了提高处理速度，调整图像大小
      let processedSrc = src;
      let scale = 1;

      // 如果图像太大，缩小处理
      const maxSize = 800;
      if (Math.max(originalWidth, originalHeight) > maxSize) {
        scale = maxSize / Math.max(originalWidth, originalHeight);
        const newSize = new this.cv.Size(
          Math.round(originalWidth * scale),
          Math.round(originalHeight * scale)
        );
        processedSrc = new this.cv.Mat();
        this.cv.resize(src, processedSrc, newSize, 0, 0, this.cv.INTER_AREA);
      }

      // 转换为灰度图
      const gray = new this.cv.Mat();
      this.cv.cvtColor(processedSrc, gray, this.cv.COLOR_RGBA2GRAY);

      // 应用自适应直方图均衡化来改善对比度
      const clahe = new this.cv.CLAHE();
      const enhanced = new this.cv.Mat();
      clahe.apply(gray, enhanced);

      // 多种阈值方法尝试检测纸张
      const methods = [
        { low: 50, high: 150 },
        { low: 30, high: 100 },
        { low: 70, high: 200 },
        { low: 40, high: 120 }  // 新增一种中间阈值
      ];

      let bestCorners: {x: number, y: number}[] | null = null;
      let bestScore = 0;

      for (const method of methods) {
        // 高斯模糊
        const blurred = new this.cv.Mat();
        this.cv.GaussianBlur(enhanced, blurred, new this.cv.Size(5, 5), 0);

        // 边缘检测
        const edges = new this.cv.Mat();
        this.cv.Canny(blurred, edges, method.low, method.high);

        // 形态学操作 - 闭运算连接边缘
        const kernel = this.cv.Mat.ones(5, 5, this.cv.CV_8UC1);
        const closed = new this.cv.Mat();
        this.cv.morphologyEx(edges, closed, this.cv.MORPH_CLOSE, kernel);

        // 查找轮廓
        const contours = new this.cv.MatVector();
        const hierarchy = new this.cv.Mat();
        this.cv.findContours(closed, contours, hierarchy, this.cv.RETR_EXTERNAL, this.cv.CHAIN_APPROX_SIMPLE);

        // 寻找最佳的四边形轮廓
        for (let i = 0; i < contours.size(); i++) {
          const contour = contours.get(i);
          const area = this.cv.contourArea(contour);

          // 只考虑面积足够大的轮廓 (至少占图像的3%，降低要求)
          if (area > (processedSrc.rows * processedSrc.cols * 0.03)) {
            // 近似轮廓为多边形
            const epsilon = 0.02 * this.cv.arcLength(contour, true);
            const approx = new this.cv.Mat();
            this.cv.approxPolyDP(contour, approx, epsilon, true);

            // 如果近似后是四边形
            if (approx.rows === 4) {
              // 计算四边形的角度，判断是否接近矩形
              const isRectangle = this.isRectangle(approx);
              if (isRectangle) {
                // 计算得分（基于面积和形状规则性）
                const score = area * this.getShapeRegularityScore(approx);

                if (score > bestScore) {
                  bestScore = score;

                  // 提取四角坐标
                  const corners: {x: number, y: number}[] = [];
                  for (let j = 0; j < approx.rows; j++) {
                    const point = approx.ptr(j, 0);
                    corners.push({
                      x: point[0] / scale, // 恢复原始尺寸比例
                      y: point[1] / scale
                    });
                  }

                  bestCorners = this.sortCorners(corners);
                }
              }

              approx.delete();
            } else {
              approx.delete();
            }
          }
          contour.delete();
        }

        // 清理内存
        blurred.delete();
        edges.delete();
        closed.delete();
        kernel.delete();
        contours.delete();
        hierarchy.delete();
      }

      // 如果还没找到，尝试更宽松的方法
      if (!bestCorners) {
        // 使用更宽松的阈值
        const blurred = new this.cv.Mat();
        this.cv.GaussianBlur(enhanced, blurred, new this.cv.Size(3, 3), 0);

        // 尝试不同的边缘检测参数
        const edges = new this.cv.Mat();
        this.cv.Canny(blurred, edges, 20, 80);

        // 更强的形态学操作
        const kernel = this.cv.Mat.ones(7, 7, this.cv.CV_8UC1);
        const closed = new this.cv.Mat();
        this.cv.morphologyEx(edges, closed, this.cv.MORPH_CLOSE, kernel);
        this.cv.morphologyEx(closed, closed, this.cv.MORPH_OPEN, this.cv.Mat.ones(3, 3, this.cv.CV_8UC1));

        // 查找轮廓
        const contours = new this.cv.MatVector();
        const hierarchy = new this.cv.Mat();
        this.cv.findContours(closed, contours, hierarchy, this.cv.RETR_EXTERNAL, this.cv.CHAIN_APPROX_SIMPLE);

        // 寻找四边形轮廓
        for (let i = 0; i < contours.size(); i++) {
          const contour = contours.get(i);
          const area = this.cv.contourArea(contour);

          // 更宽松的面积要求 (至少占图像的2%)
          if (area > (processedSrc.rows * processedSrc.cols * 0.02)) {
            // 近似轮廓为多边形
            const epsilon = 0.03 * this.cv.arcLength(contour, true);  // 更宽松的近似
            const approx = new this.cv.Mat();
            this.cv.approxPolyDP(contour, approx, epsilon, true);

            // 如果近似后是四边形
            if (approx.rows === 4) {
              // 更宽松的矩形判断
              const isRectangle = this.isRectangleRelaxed(approx);
              if (isRectangle) {
                // 提取四角坐标
                const corners: {x: number, y: number}[] = [];
                for (let j = 0; j < approx.rows; j++) {
                  const point = approx.ptr(j, 0);
                  corners.push({
                    x: point[0] / scale, // 恢复原始尺寸比例
                    y: point[1] / scale
                  });
                }

                bestCorners = this.sortCorners(corners);
                approx.delete();
                contour.delete();
                break;
              }
              approx.delete();
            } else {
              approx.delete();
            }
          }
          contour.delete();
        }

        // 清理内存
        blurred.delete();
        edges.delete();
        closed.delete();
        kernel.delete();
        contours.delete();
        hierarchy.delete();
      }

      // 清理内存
      src.delete();
      if (processedSrc !== src) processedSrc.delete();
      gray.delete();
      enhanced.delete();

      return bestCorners;
    } catch (error) {
      console.error("Paper detection failed:", error);
      return null;
    }
  }

  /**
   * 判断四边形是否接近矩形 (标准版)
   * @param contour 四边形轮廓
   * @returns 是否接近矩形
   */
  private isRectangle(contour: any): boolean {
    if (contour.rows !== 4) return false;

    // 获取四个顶点
    const points: {x: number, y: number}[] = [];
    for (let i = 0; i < contour.rows; i++) {
      const point = contour.ptr(i, 0);
      points.push({x: point[0], y: point[1]});
    }

    // 计算四条边的长度
    const distances: number[] = [];
    for (let i = 0; i < 4; i++) {
      const p1 = points[i];
      const p2 = points[(i + 1) % 4];
      const distance = Math.sqrt(Math.pow(p2.x - p1.x, 2) + Math.pow(p2.y - p1.y, 2));
      distances.push(distance);
    }

    // 计算对角线长度
    const diagonal1 = Math.sqrt(Math.pow(points[2].x - points[0].x, 2) + Math.pow(points[2].y - points[0].y, 2));
    const diagonal2 = Math.sqrt(Math.pow(points[3].x - points[1].x, 2) + Math.pow(points[3].y - points[1].y, 2));

    // 检查对边是否相等（平行四边形）
    const oppositeSidesEqual =
      Math.abs(distances[0] - distances[2]) < Math.min(distances[0], distances[2]) * 0.3 &&
      Math.abs(distances[1] - distances[3]) < Math.min(distances[1], distances[3]) * 0.3;

    // 检查对角线是否相等（矩形）
    const diagonalsEqual = Math.abs(diagonal1 - diagonal2) < Math.max(diagonal1, diagonal2) * 0.1;

    return oppositeSidesEqual && diagonalsEqual;
  }

  /**
   * 判断四边形是否接近矩形 (宽松版)
   * @param contour 四边形轮廓
   * @returns 是否接近矩形
   */
  private isRectangleRelaxed(contour: any): boolean {
    if (contour.rows !== 4) return false;

    // 获取四个顶点
    const points: {x: number, y: number}[] = [];
    for (let i = 0; i < contour.rows; i++) {
      const point = contour.ptr(i, 0);
      points.push({x: point[0], y: point[1]});
    }

    // 计算四条边的长度
    const distances: number[] = [];
    for (let i = 0; i < 4; i++) {
      const p1 = points[i];
      const p2 = points[(i + 1) % 4];
      const distance = Math.sqrt(Math.pow(p2.x - p1.x, 2) + Math.pow(p2.y - p1.y, 2));
      distances.push(distance);
    }

    // 计算对角线长度
    const diagonal1 = Math.sqrt(Math.pow(points[2].x - points[0].x, 2) + Math.pow(points[2].y - points[0].y, 2));
    const diagonal2 = Math.sqrt(Math.pow(points[3].x - points[1].x, 2) + Math.pow(points[3].y - points[1].y, 2));

    // 更宽松的检查对边是否相等
    const oppositeSidesEqual =
      Math.abs(distances[0] - distances[2]) < Math.min(distances[0], distances[2]) * 0.5 &&
      Math.abs(distances[1] - distances[3]) < Math.min(distances[1], distances[3]) * 0.5;

    // 更宽松的检查对角线是否相等
    const diagonalsEqual = Math.abs(diagonal1 - diagonal2) < Math.max(diagonal1, diagonal2) * 0.2;

    return oppositeSidesEqual && diagonalsEqual;
  }

  /**
   * 计算形状规则性得分
   * @param contour 四边形轮廓
   * @returns 规则性得分 (0-1)
   */
  private getShapeRegularityScore(contour: any): number {
    if (contour.rows !== 4) return 0;

    // 获取四个顶点
    const points: {x: number, y: number}[] = [];
    for (let i = 0; i < contour.rows; i++) {
      const point = contour.ptr(i, 0);
      points.push({x: point[0], y: point[1]});
    }

    // 计算四条边的长度
    const distances: number[] = [];
    for (let i = 0; i < 4; i++) {
      const p1 = points[i];
      const p2 = points[(i + 1) % 4];
      const distance = Math.sqrt(Math.pow(p2.x - p1.x, 2) + Math.pow(p2.y - p1.y, 2));
      distances.push(distance);
    }

    // 计算角度
    const angles: number[] = [];
    for (let i = 0; i < 4; i++) {
      const p1 = points[(i + 3) % 4];
      const p2 = points[i];
      const p3 = points[(i + 1) % 4];

      const v1 = {x: p1.x - p2.x, y: p1.y - p2.y};
      const v2 = {x: p3.x - p2.x, y: p3.y - p2.y};

      const dot = v1.x * v2.x + v1.y * v2.y;
      const mag1 = Math.sqrt(v1.x * v1.x + v1.y * v1.y);
      const mag2 = Math.sqrt(v2.x * v2.x + v2.y * v2.y);

      const angle = Math.acos(dot / (mag1 * mag2));
      angles.push(angle);
    }

    // 计算边长变化系数（越接近正方形得分越高）
    const avgDistance = distances.reduce((a, b) => a + b, 0) / distances.length;
    const distanceVariance = distances.reduce((sum, d) => sum + Math.pow(d - avgDistance, 2), 0) / distances.length;
    const distanceScore = 1 / (1 + distanceVariance / (avgDistance * avgDistance));

    // 计算角度接近90度的得分
    const rightAngle = Math.PI / 2;
    const angleDeviation = angles.reduce((sum, angle) => sum + Math.pow(angle - rightAngle, 2), 0);
    const angleScore = 1 / (1 + angleDeviation);

    return (distanceScore + angleScore) / 2;
  }

  /**
   * 对角点进行排序
   * @param corners 四个角点
   * @returns 排序后的角点（左上，右上，右下，左下）
   */
  private sortCorners(corners: {x: number, y: number}[]): {x: number, y: number}[] {
    if (corners.length !== 4) return corners;

    // 更精确的排序方法
    const topLeft = corners.reduce((prev, curr) =>
      (prev.x + prev.y) < (curr.x + curr.y) ? prev : curr
    );

    const topRight = corners.reduce((prev, curr) =>
      (prev.x - prev.y) < (curr.x - curr.y) ? curr : prev
    );

    const bottomRight = corners.reduce((prev, curr) =>
      (prev.x + prev.y) > (curr.x + curr.y) ? prev : curr
    );

    const bottomLeft = corners.reduce((prev, curr) =>
      (prev.x - prev.y) > (curr.x - curr.y) ? prev : curr
    );

    return [topLeft, topRight, bottomRight, bottomLeft];
  }

  /**
   * 应用透视校正
   * @param imageElement 原始图像
   * @param corners 纸张四角坐标
   * @returns 校正后的图像数据URL
   */
  async applyPerspectiveCorrection(
    imageElement: HTMLImageElement,
    corners: {x: number, y: number}[]
  ): Promise<string> {
    if (!this.cv) {
      throw new Error("OpenCV.js not initialized");
    }

    try {
      // 读取图像
      const src = this.cv.imread(imageElement);

      // 定义目标矩形（A4纸比例）
      const width = 800;
      const height = Math.round(width * (297 / 210)); // A4比例

      // 源点（检测到的角点）
      const srcCorners = new this.cv.Mat(4, 1, this.cv.CV_32FC2);
      srcCorners.data32F[0] = corners[0].x;
      srcCorners.data32F[1] = corners[0].y;
      srcCorners.data32F[2] = corners[1].x;
      srcCorners.data32F[3] = corners[1].y;
      srcCorners.data32F[4] = corners[2].x;
      srcCorners.data32F[5] = corners[2].y;
      srcCorners.data32F[6] = corners[3].x;
      srcCorners.data32F[7] = corners[3].y;

      // 目标点（标准矩形）
      const dstCorners = new this.cv.Mat(4, 1, this.cv.CV_32FC2);
      dstCorners.data32F[0] = 0;
      dstCorners.data32F[1] = 0;
      dstCorners.data32F[2] = width;
      dstCorners.data32F[3] = 0;
      dstCorners.data32F[4] = width;
      dstCorners.data32F[5] = height;
      dstCorners.data32F[6] = 0;
      dstCorners.data32F[7] = height;

      // 计算透视变换矩阵
      const perspectiveMatrix = this.cv.getPerspectiveTransform(srcCorners, dstCorners);

      // 应用透视变换
      const dst = new this.cv.Mat();
      this.cv.warpPerspective(
        src,
        dst,
        perspectiveMatrix,
        new this.cv.Size(width, height),
        this.cv.INTER_LINEAR,
        this.cv.BORDER_CONSTANT,
        new this.cv.Scalar()
      );

      // 转换为画布并获取数据URL
      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      this.cv.imshow(canvas, dst);

      // 获取数据URL
      const dataUrl = canvas.toDataURL("image/jpeg", 0.9);

      // 清理内存
      src.delete();
      dst.delete();
      srcCorners.delete();
      dstCorners.delete();
      perspectiveMatrix.delete();
      canvas.remove();

      return dataUrl;
    } catch (error) {
      console.error("Perspective correction failed:", error);
      throw error;
    }
  }

  /**
   * 计算像素到毫米的比例
   * @param paperFormat 纸张格式 ("A4" | "Letter" | "A5")
   * @returns pixels per mm
   */
  calculatePixelRatio(paperFormat: string): number {
    const paperSizes = {
      A4: { width: 210, height: 297 }, // mm
      Letter: { width: 215.9, height: 279.4 }, // mm
      A5: { width: 148, height: 210 } // mm
    };

    const size = paperSizes[paperFormat as keyof typeof paperSizes] || paperSizes.A4;

    // 校正后的图像宽度为800像素
    const imageWidthPixels = 800;
    const paperWidthMM = size.width;

    return imageWidthPixels / paperWidthMM;
  }
}