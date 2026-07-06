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

      // 高斯模糊
      const blurred = new this.cv.Mat();
      this.cv.GaussianBlur(gray, blurred, new this.cv.Size(5, 5), 0);

      // 边缘检测
      const edges = new this.cv.Mat();
      this.cv.Canny(blurred, edges, 50, 150);

      // 形态学操作 - 闭运算连接边缘
      const kernel = this.cv.Mat.ones(5, 5, this.cv.CV_8UC1);
      const closed = new this.cv.Mat();
      this.cv.morphologyEx(edges, closed, this.cv.MORPH_CLOSE, kernel);

      // 查找轮廓
      const contours = new this.cv.MatVector();
      const hierarchy = new this.cv.Mat();
      this.cv.findContours(closed, contours, hierarchy, this.cv.RETR_EXTERNAL, this.cv.CHAIN_APPROX_SIMPLE);

      // 寻找最大的四边形轮廓
      let largestContour = null;
      let maxArea = 0;

      for (let i = 0; i < contours.size(); i++) {
        const contour = contours.get(i);
        const area = this.cv.contourArea(contour);

        // 只考虑面积足够大的轮廓 (至少占图像的10%)
        if (area > maxArea && area > (processedSrc.rows * processedSrc.cols * 0.1)) {
          // 近似轮廓为多边形
          const epsilon = 0.02 * this.cv.arcLength(contour, true);
          const approx = new this.cv.Mat();
          this.cv.approxPolyDP(contour, approx, epsilon, true);

          // 如果近似后是四边形
          if (approx.rows === 4) {
            maxArea = area;
            largestContour = approx;
          } else {
            approx.delete();
          }
        }
        contour.delete();
      }

      // 清理内存
      src.delete();
      if (processedSrc !== src) processedSrc.delete();
      gray.delete();
      blurred.delete();
      edges.delete();
      closed.delete();
      kernel.delete();
      contours.delete();
      hierarchy.delete();

      if (largestContour) {
        // 提取四角坐标
        const corners: {x: number, y: number}[] = [];
        for (let i = 0; i < largestContour.rows; i++) {
          const point = largestContour.ptr(i, 0);
          corners.push({
            x: point[0] / scale, // 恢复原始尺寸比例
            y: point[1] / scale
          });
        }

        largestContour.delete();

        // 按顺时针排序角点（左上，右上，右下，左下）
        return this.sortCorners(corners);
      }

      return null;
    } catch (error) {
      console.error("Paper detection failed:", error);
      return null;
    }
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