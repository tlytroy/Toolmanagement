import type { Point } from "./types";
import { loadCv } from '@/lib/opencvLoader';

let cv: any = null;

async function getCV() {
  if (!cv) cv = await loadCv();
  return cv;
}

export class PaperDetector {
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
    let bestContour = null;
    let maxArea = 0;
    let bestScore = 0;

    for (let i = 0; i < contours.size(); i++) {
      const contour = contours.get(i);
      const area = cv.contourArea(contour);

      // 忽略太小的轮廓
      if (area < 100) {
        contour.delete();
        continue;
      }

      // 多epsilon尝试，提高检测成功率
      const epsilons = [0.01, 0.015, 0.02, 0.025, 0.03, 0.04];

      for (const epsilon of epsilons) {
        const approx = new cv.Mat();
        const arcLength = cv.arcLength(contour, true);
        cv.approxPolyDP(contour, approx, epsilon * arcLength, true);

        // 检查是否为四边形
        if (approx.rows === 4) {
          // 检查是否为凸四边形
          const isConvex = cv.isContourConvex(approx);

          // 放宽角度约束：允许30°-150°之间的角度
          const anglesValid = this.areQuadrilateralAnglesValid(approx, 30, 150);

          if (isConvex && anglesValid) {
            // 计算综合评分（面积 + 形状规则性）
            const score = this.calculateQuadrilateralScore(approx, area);

            if (score > bestScore) {
              if (bestContour) {
                bestContour.delete();
              }
              maxArea = area;
              bestScore = score;
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

      contour.delete();
    }

    return bestContour ? { contour: bestContour, area: maxArea } : null;
  }

  /**
   * 计算四边形评分（面积 + 形状规则性）
   * @param quadrilateral 四边形轮廓
   * @param area 面积
   * @returns 综合评分
   */
  private calculateQuadrilateralScore(quadrilateral: any, area: number): number {
    // 面积得分（归一化到0-1）
    // 假设理想面积为图像面积的30%-80%
    const idealAreaRatio = 0.5;
    const areaScore = Math.exp(-Math.pow(area / 10000 - idealAreaRatio, 2) * 10);

    // 形状规则性得分（角度接近90°的程度）
    const points = [];
    for (let i = 0; i < 4; i++) {
      const point = quadrilateral.ptr(i, 0);
      points.push({ x: point[0], y: point[1] });
    }

    let angleScore = 0;
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

      // 角度越接近90°得分越高
      const angleDeviation = Math.abs(angle - 90);
      angleScore += Math.max(0, 1 - angleDeviation / 90);
    }
    angleScore /= 4; // 平均角度得分

    // 边长均匀性得分
    let sideScore = 0;
    const sides = [];
    for (let i = 0; i < 4; i++) {
      const p1 = points[i];
      const p2 = points[(i + 1) % 4];
      const sideLength = Math.sqrt(Math.pow(p2.x - p1.x, 2) + Math.pow(p2.y - p1.y, 2));
      sides.push(sideLength);
    }

    // 计算边长的标准差
    const meanSide = sides.reduce((sum, s) => sum + s, 0) / 4;
    const variance = sides.reduce((sum, s) => sum + Math.pow(s - meanSide, 2), 0) / 4;
    const stdDev = Math.sqrt(variance);
    // 标准差越小得分越高
    sideScore = Math.max(0, 1 - stdDev / meanSide);

    // 综合评分
    return areaScore * 0.4 + angleScore * 0.4 + sideScore * 0.2;
  }

  /**
   * 检查四边形角度是否有效
   * @param quadrilateral 四边形轮廓
   * @param minAngle 最小角度
   * @param maxAngle 最大角度
   * @returns 是否有效
   */
  private areQuadrilateralAnglesValid(quadrilateral: any, minAngle: number, maxAngle: number): boolean {
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
      const angle = Math.acos(Math.max(-1, Math.min(1, cosTheta))) * (180 / Math.PI);

      // 角度应该在指定范围内
      if (angle < minAngle || angle > maxAngle) {
        return false;
      }
    }

    return true;
  }

  /**
   * 排序四边形角点：左上→右上→右下→左下
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

    // 按象限排序
    const sorted = [...corners].sort((a, b) => {
      // 计算相对于中心点的象限
      const quadA = a.x < center.x ? (a.y < center.y ? 1 : 4) : (a.y < center.y ? 2 : 3);
      const quadB = b.x < center.x ? (b.y < center.y ? 1 : 4) : (b.y < center.y ? 2 : 3);

      if (quadA !== quadB) {
        return quadA - quadB;
      }

      // 同一象限内按角度排序
      const angleA = Math.atan2(a.y - center.y, a.x - center.x);
      const angleB = Math.atan2(b.y - center.y, b.x - center.x);
      return angleA - angleB;
    });

    // 确保顺序为：左上→右上→右下→左下
    // 左上角应该是x+y最小的点
    const topLeftIndex = sorted.reduce((minIndex, p, i, arr) => {
      return p.x + p.y < arr[minIndex].x + arr[minIndex].y ? i : minIndex;
    }, 0);

    // 重新排列数组，使左上角在第一位
    return [
      sorted[topLeftIndex],
      sorted[(topLeftIndex + 1) % 4],
      sorted[(topLeftIndex + 2) % 4],
      sorted[(topLeftIndex + 3) % 4]
    ];
  }

  /**
   * 检测纸张四角 - 使用多策略文档扫描算法
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
      let bestContour: { contour: any; area: number } | null = null;
      let maxArea = 0;

      // 策略1: Otsu阈值分割
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

        const result = this.findBestQuadrilateral(contours);
        if (result && result.area > maxArea) {
          maxArea = result.area;
          if (bestContour) {
            (bestContour as { contour: any; area: number }).contour.delete();
          }
          bestContour = result;
        }

        thresh.delete();
        inverted.delete();
        contours.delete();
        hierarchy.delete();
      }

      // 策略2: 自适应阈值分割（GAUSSIAN）
      if (!bestContour || maxArea < src.cols * src.rows * 0.05) {
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

        const result = this.findBestQuadrilateral(contours);
        if (result && result.area > maxArea) {
          maxArea = result.area;
          if (bestContour) {
            (bestContour as { contour: any; area: number }).contour.delete();
          }
          bestContour = result;
        }

        thresh.delete();
        inverted.delete();
        contours.delete();
        hierarchy.delete();
      }

      // 策略3: 自适应阈值分割（MEAN）
      if (!bestContour || maxArea < src.cols * src.rows * 0.05) {
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

        const result = this.findBestQuadrilateral(contours);
        if (result && result.area > maxArea) {
          maxArea = result.area;
          if (bestContour) {
            (bestContour as { contour: any; area: number }).contour.delete();
          }
          bestContour = result;
        }

        thresh.delete();
        inverted.delete();
        contours.delete();
        hierarchy.delete();
      }

      // 策略4: Canny边缘检测（低阈值）
      if (!bestContour || maxArea < src.cols * src.rows * 0.05) {
        const edges = new cv.Mat();
        cv.Canny(blurred, edges, 30, 100);

        const contours = new cv.MatVector();
        const hierarchy = new cv.Mat();
        cv.findContours(
          edges,
          contours,
          hierarchy,
          cv.RETR_EXTERNAL,
          cv.CHAIN_APPROX_SIMPLE,
        );

        const result = this.findBestQuadrilateral(contours);
        if (result && result.area > maxArea) {
          maxArea = result.area;
          if (bestContour) {
            (bestContour as { contour: any; area: number }).contour.delete();
          }
          bestContour = result;
        }

        edges.delete();
        contours.delete();
        hierarchy.delete();
      }

      // 策略5: Canny边缘检测（中阈值）
      if (!bestContour || maxArea < src.cols * src.rows * 0.05) {
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

        const result = this.findBestQuadrilateral(contours);
        if (result && result.area > maxArea) {
          maxArea = result.area;
          if (bestContour) {
            (bestContour as { contour: any; area: number }).contour.delete();
          }
          bestContour = result;
        }

        edges.delete();
        contours.delete();
        hierarchy.delete();
      }

      // 策略6: CLAHE增强 + 自适应阈值
      if (!bestContour || maxArea < src.cols * src.rows * 0.05) {
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

        const result = this.findBestQuadrilateral(contours);
        if (result && result.area > maxArea) {
          maxArea = result.area;
          if (bestContour) {
            (bestContour as { contour: any; area: number }).contour.delete();
          }
          bestContour = result;
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
      );

      // 清理内存
      src.delete();
      gray.delete();
      blurred.delete();

      if (bestContour) {
        // 提取四角坐标
        const corners: Point[] = [];
        for (let i = 0; i < bestContour.contour.rows; i++) {
          const point = bestContour.contour.ptr(i, 0);
          corners.push({
            x: point[0],
            y: point[1],
          });
        }

        // 角点排序：按顺时针顺序排列，确保第一个点是左上角
        const sortedCorners = this.sortQuadrilateralCorners(corners);

        bestContour.contour.delete();
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