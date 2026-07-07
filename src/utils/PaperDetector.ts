// 纸张检测功能实现 — 重写版
// 算法思路参考 CamScanner / document scanner 类应用：
// 1. 预处理（灰度 + 模糊）
// 2. 多策略分割（Otsu / adaptiveThreshold / Canny）
// 3. 轮廓查找 → 凸四边形拟合（不要求矩形，只要求凸+角度合理）
// 4. 选最佳候选（面积大 + 形状规则）
// 5. 角点排序 + 透视校正
import type { Point } from './types';

// 动态导入OpenCV.js，因为它可能作为Promise返回
let cv: any = null;

async function getCV() {
  if (cv) return cv;

  try {
    const cvModule = await import('@techstark/opencv-js');
    // 处理可能的Promise情况
    cv = cvModule.default || cvModule;

    // 等待OpenCV初始化完成
    if (cv.onRuntimeInitialized) {
      await new Promise(resolve => {
        if (typeof cv.onRuntimeInitialized === 'function') {
          const originalCallback = cv.onRuntimeInitialized;
          cv.onRuntimeInitialized = () => {
            originalCallback();
            resolve(undefined);
          };
        } else {
          resolve(undefined);
        }
      });
    }

    console.log('[PaperDetector] OpenCV.js loaded successfully');
    return cv;
  } catch (error) {
    console.error('[PaperDetector] Failed to load OpenCV.js:', error);
    throw new Error(`Failed to load OpenCV.js: ${error instanceof Error ? error.message : String(error)}`);
  }
}

export interface DetectionDebugInfo {
  strategy: string;
  thresholdImage?: string;  // dataURL of thresholded/edge image
  candidateCount: number;
  reason?: string;          // why detection failed
}

export class PaperDetector {
  private initialized = false;

  constructor() {
    // 初始化在首次使用时进行
  }

  private async ensureInitialized() {
    if (this.initialized) return;

    try {
      cv = await getCV();
      this.initialized = true;
      console.log('[PaperDetector] OpenCV.js ready');
    } catch (error) {
      console.error('[PaperDetector] Failed to initialize OpenCV.js:', error);
      throw error;
    }
  }

  /**
   * 检测纸张四角
   * @param imageElement HTMLImageElement
   * @param debug 是否输出调试信息
   * @returns 纸张四角坐标 + 调试信息
   */
  async detectPaperCorners(
    imageElement: HTMLImageElement,
    debug = false
  ): Promise<{ corners: Point[] | null; debugInfo: DetectionDebugInfo[] }> {
    await this.ensureInitialized();

    if (!this.initialized || !cv) {
      throw new Error('OpenCV.js not initialized');
    }

    const debugInfos: DetectionDebugInfo[] = [];

    try {
      const src = cv.imread(imageElement);
      const originalWidth = src.cols;
      const originalHeight = src.rows;

      // 缩放处理 — 提速 + 减噪
      let processedSrc = src;
      let scale = 1;
      const maxSize = 800;
      if (Math.max(originalWidth, originalHeight) > maxSize) {
        scale = maxSize / Math.max(originalWidth, originalHeight);
        const newSize = new cv.Size(
          Math.round(originalWidth * scale),
          Math.round(originalHeight * scale)
        );
        processedSrc = new cv.Mat();
        cv.resize(src, processedSrc, newSize, 0, 0, cv.INTER_AREA);
      }

      // 灰度
      const gray = new cv.Mat();
      cv.cvtColor(processedSrc, gray, cv.COLOR_RGBA2GRAY);

      // 模糊降噪
      const blurred = new cv.Mat();
      cv.GaussianBlur(gray, blurred, new cv.Size(5, 5), 0);

      // ——— 多策略分割 ———
      const strategies: Array<{
        name: string;
        apply: (blurred: any) => any;
      }> = [
        {
          name: 'Otsu阈值',
          apply: (b) => {
            const binary = new cv.Mat();
            cv.threshold(b, binary, 0, 255, cv.THRESH_BINARY + cv.THRESH_OTSU);
            // 纸是白的，背景是暗的 → invert 让纸变黑（轮廓包围纸）
            const inv = new cv.Mat();
            cv.bitwise_not(binary, inv);
            binary.delete();
            return inv;
          }
        },
        {
          name: '自适应阈值(GAUSSIAN)',
          apply: (b) => {
            const binary = new cv.Mat();
            cv.adaptiveThreshold(b, binary, 255, cv.ADAPTIVE_THRESH_GAUSSIAN_C, cv.THRESH_BINARY, 15, 5);
            const inv = new cv.Mat();
            cv.bitwise_not(binary, inv);
            binary.delete();
            return inv;
          }
        },
        {
          name: '自适应阈值(MEAN)',
          apply: (b) => {
            const binary = new cv.Mat();
            cv.adaptiveThreshold(b, binary, 255, cv.ADAPTIVE_THRESH_MEAN_C, cv.THRESH_BINARY, 31, 10);
            const inv = new cv.Mat();
            cv.bitwise_not(binary, inv);
            binary.delete();
            return inv;
          }
        },
        {
          name: 'Canny边缘(低阈值)',
          apply: (b) => {
            const edges = new cv.Mat();
            cv.Canny(b, edges, 30, 100);
            const kernel = cv.Mat.ones(7, 7, cv.CV_8UC1);
            const closed = new cv.Mat();
            cv.morphologyEx(edges, closed, cv.MORPH_CLOSE, kernel);
            edges.delete();
            kernel.delete();
            return closed;
          }
        },
        {
          name: 'Canny边缘(中阈值)',
          apply: (b) => {
            const edges = new cv.Mat();
            cv.Canny(b, edges, 50, 150);
            const kernel = cv.Mat.ones(5, 5, cv.CV_8UC1);
            const closed = new cv.Mat();
            cv.morphologyEx(edges, closed, cv.MORPH_CLOSE, kernel);
            edges.delete();
            kernel.delete();
            return closed;
          }
        },
        {
          name: 'CLAHE+自适应阈值',
          apply: (b) => {
            const clahe = new cv.CLAHE();
            clahe.setClipLimit(3.0);
            clahe.setTilesGridSize(new cv.Size(8, 8));
            const enhanced = new cv.Mat();
            clahe.apply(b, enhanced);
            const binary = new cv.Mat();
            cv.adaptiveThreshold(enhanced, binary, 255, cv.ADAPTIVE_THRESH_GAUSSIAN_C, cv.THRESH_BINARY, 21, 8);
            const inv = new cv.Mat();
            cv.bitwise_not(binary, inv);
            binary.delete();
            enhanced.delete();
            return inv;
          }
        }
      ];

      const totalArea = processedSrc.rows * processedSrc.cols;
      // 纸张至少占画面 10%
      const minAreaRatio = 0.10;
      const minArea = totalArea * minAreaRatio;

      let bestCorners: Point[] | null = null;
      let bestScore = 0;

      for (const strategy of strategies) {
        const info: DetectionDebugInfo = {
          strategy: strategy.name,
          candidateCount: 0,
        };

        const mask = strategy.apply(blurred);

        // 调试：保存中间图像
        if (debug) {
          info.thresholdImage = this.matToDataUrl(mask, processedSrc.cols, processedSrc.rows);
        }

        // 查找轮廓
        const contours = new cv.MatVector();
        const hierarchy = new cv.Mat();
        cv.findContours(mask, contours, hierarchy, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE);

        // 按面积降序排列，只看前 10 个最大的
        const candidates: Array<{ contourIdx: number; area: number }> = [];
        for (let i = 0; i < contours.size(); i++) {
          const contour = contours.get(i);
          const area = cv.contourArea(contour);
          if (area > minArea) {
            candidates.push({ contourIdx: i, area });
          }
        }
        candidates.sort((a, b) => b.area - a.area);

        info.candidateCount = candidates.length;

        // 对每个候选轮廓，尝试多种 epsilon 逼近到 4 点
        for (const cand of candidates.slice(0, 10)) {
          const contour = contours.get(cand.contourIdx);
          const perimeter = cv.arcLength(contour, true);

          // 从小 epsilon 开始尝试，逐步放宽直到得到 4 点
          // epsilon = 近似精度，越小越贴合原始轮廓
          const epsilons = [0.01, 0.02, 0.03, 0.04, 0.05];

          for (const eps of epsilons) {
            const approx = new cv.Mat();
            cv.approxPolyDP(contour, approx, eps * perimeter, true);

            if (approx.rows === 4) {
              // ——— 关键改进：不要求矩形，只要求凸四边形 + 合理角度 ———
              const points = this.extractPoints(approx);
              const isConvex = this.isConvexQuadrilateral(points);
              const angles = this.getAngles(points);
              const minAngle = Math.min(...angles);
              const maxAngle = Math.max(...angles);

              // 角度在 40°~140° 之间（允许透视变形）
              const angleOk = minAngle > 40 && maxAngle < 140;

              if (isConvex && angleOk) {
                const score = cand.area * this.shapeRegularity(points);
                if (score > bestScore) {
                  bestScore = score;
                  bestCorners = this.sortCorners(
                    points.map(p => ({ x: p.x / scale, y: p.y / scale }))
                  );
                }
              }
            }

            // 如果 > 4 点，尝试更宽 epsilon
            // 如果 < 4 点，这个 epsilon 太宽了，跳过
            if (approx.rows < 4) {
              approx.delete();
              break; // epsilon 已经过大
            }
            approx.delete();
          }
        }

        // 清理本轮
        mask.delete();
        contours.delete();
        hierarchy.delete();

        debugInfos.push(info);

        // 如果已经找到好的结果，后续策略可以跳过
        if (bestCorners && bestScore > minArea * 0.5) {
          break;
        }
      }

      // 如果全部策略都失败
      if (!bestCorners) {
        const lastInfo: DetectionDebugInfo = {
          strategy: '汇总',
          candidateCount: 0,
          reason: this.diagnoseFailure(debugInfos, minArea, totalArea),
        };
        debugInfos.push(lastInfo);
      }

      // 清理
      src.delete();
      if (processedSrc !== src) processedSrc.delete();
      gray.delete();
      blurred.delete();

      return { corners: bestCorners, debugInfo: debugInfos };
    } catch (error) {
      console.error('[PaperDetector] Detection failed:', error);
      return {
        corners: null,
        debugInfo: [{
          strategy: '异常',
          candidateCount: 0,
          reason: `检测出错: ${error instanceof Error ? error.message : String(error)}`,
        }],
      };
    }
  }

  // ——— 辅助方法 ———

  /** 从 approxPolyDP 结果 Mat 中提取点 */
  private extractPoints(approx: any): Point[] {
    const points: Point[] = [];
    for (let i = 0; i < approx.rows; i++) {
      const ptr = approx.ptr(i, 0);
      points.push({ x: ptr[0], y: ptr[1] });
    }
    return points;
  }

  /** 判断四边形是否为凸四边形 */
  private isConvexQuadrilateral(points: Point[]): boolean {
    if (points.length !== 4) return false;

    // 用叉积判断：所有相邻边叉积符号一致 = 凸
    const crossProducts: number[] = [];
    for (let i = 0; i < 4; i++) {
      const p0 = points[i];
      const p1 = points[(i + 1) % 4];
      const p2 = points[(i + 2) % 4];

      const dx1 = p1.x - p0.x;
      const dy1 = p1.y - p0.y;
      const dx2 = p2.x - p1.x;
      const dy2 = p2.y - p1.y;

      crossProducts.push(dx1 * dy2 - dy1 * dx2);
    }

    // 所有叉积同号 → 凸
    const allPositive = crossProducts.every(cp => cp > 0);
    const allNegative = crossProducts.every(cp => cp < 0);
    return allPositive || allNegative;
  }

  /** 计算四边形四个内角（度数） */
  private getAngles(points: Point[]): number[] {
    const angles: number[] = [];
    for (let i = 0; i < 4; i++) {
      const p0 = points[(i + 3) % 4];
      const p1 = points[i];
      const p2 = points[(i + 1) % 4];

      const v1 = { x: p0.x - p1.x, y: p0.y - p1.y };
      const v2 = { x: p2.x - p1.x, y: p2.y - p1.y };

      const dot = v1.x * v2.x + v1.y * v2.y;
      const mag1 = Math.sqrt(v1.x * v1.x + v1.y * v1.y);
      const mag2 = Math.sqrt(v2.x * v2.x + v2.y * v2.y);

      if (mag1 === 0 || mag2 === 0) {
        angles.push(90);
        continue;
      }

      const cosA = Math.max(-1, Math.min(1, dot / (mag1 * mag2)));
      angles.push(Math.acos(cosA) * 180 / Math.PI);
    }
    return angles;
  }

  /** 形状规则性得分（0~1）：越接近矩形越高 */
  private shapeRegularity(points: Point[]): number {
    // 角度接近 90° → 高分
    const angles = this.getAngles(points);
    const angleDeviation = angles.reduce((sum, a) => sum + Math.pow(a - 90, 2), 0);
    const angleScore = 1 / (1 + angleDeviation / 100);

    // 边长方差小 → 高分
    const sides: number[] = [];
    for (let i = 0; i < 4; i++) {
      const p1 = points[i];
      const p2 = points[(i + 1) % 4];
      sides.push(Math.sqrt((p2.x - p1.x) ** 2 + (p2.y - p1.y) ** 2));
    }
    const avgSide = sides.reduce((a, b) => a + b, 0) / 4;
    const sideVariance = sides.reduce((s, d) => s + (d - avgSide) ** 2, 0) / 4;
    const sideScore = 1 / (1 + sideVariance / (avgSide * avgSide));

    return (angleScore * 0.7 + sideScore * 0.3); // 角度更重要
  }

  /** 角点排序：左上 → 右上 → 右下 → 左下 */
  private sortCorners(corners: Point[]): Point[] {
    if (corners.length !== 4) return corners;

    // 按中心点计算
    const cx = corners.reduce((s, p) => s + p.x, 0) / 4;
    const cy = corners.reduce((s, p) => s + p.y, 0) / 4;

    // 相对中心的角度排序
    const sorted = [...corners].sort((a, b) => {
      const angleA = Math.atan2(a.y - cy, a.x - cx);
      const angleB = Math.atan2(b.y - cy, b.x - cx);
      return angleA - angleB;
    });

    // atan2 从 -PI 到 PI，排序后顺序是：右上 → 右下 → 左下 → 左上
    // 我们要：左上 → 右上 → 右下 → 左下
    return [sorted[3], sorted[0], sorted[1], sorted[2]];
  }

  /** Mat → dataURL（用于 debug 显示） */
  private matToDataUrl(mat: any, width: number, height: number): string {
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    cv.imshow(canvas, mat);
    const url = canvas.toDataURL('image/jpeg', 0.7);
    canvas.remove();
    return url;
  }

  /** 诊断失败原因 */
  private diagnoseFailure(
    infos: DetectionDebugInfo[],
    _minArea: number,
    _totalArea: number
  ): string {
    const noCandidates = infos.every(i => i.candidateCount === 0);
    if (noCandidates) {
      return '所有策略都没找到面积足够大的轮廓。可能原因：1) 纸张占画面太小（建议纸张至少占画面10%）2) 光照太暗或太亮 3) 纸张和背景颜色接近无法区分';
    }

    const hasCandidates = infos.some(i => i.candidateCount > 0);
    if (hasCandidates) {
      return '找到了大轮廓但无法拟合为凸四边形。可能原因：1) 纸张边缘被遮挡或弯曲 2) 轮廓不够平滑（有毛刺或内凹）3) 实际不是四边形形状';
    }

    return '未知原因，建议使用手动模式标记角点';
  }

  /**
   * 应用透视校正
   * @param imageElement 原始图像
   * @param corners 纸张四角坐标
   * @param paperFormat 纸张格式
   * @returns 校正后的图像 dataURL
   */
  async applyPerspectiveCorrection(
    imageElement: HTMLImageElement,
    corners: Point[],
    paperFormat = 'A4'
  ): Promise<string> {
    await this.ensureInitialized();

    if (!this.initialized || !cv) {
      throw new Error('OpenCV.js not initialized');
    }

    try {
      const src = cv.imread(imageElement);

      const paperSizes: Record<string, { width: number; height: number }> = {
        A4: { width: 210, height: 297 },
        Letter: { width: 215.9, height: 279.4 },
        A5: { width: 148, height: 210 },
      };

      const size = paperSizes[paperFormat] || paperSizes.A4;

      // 输出尺寸：宽度 800px，高度按纸张比例
      const outputWidth = 800;
      const outputHeight = Math.round(outputWidth * (size.height / size.width));

      // 源角点
      const srcPts = new cv.Mat(4, 1, cv.CV_32FC2);
      srcPts.data32F[0] = corners[0].x; srcPts.data32F[1] = corners[0].y;
      srcPts.data32F[2] = corners[1].x; srcPts.data32F[3] = corners[1].y;
      srcPts.data32F[4] = corners[2].x; srcPts.data32F[5] = corners[2].y;
      srcPts.data32F[6] = corners[3].x; srcPts.data32F[7] = corners[3].y;

      // 目标角点（标准矩形）
      const dstPts = new cv.Mat(4, 1, cv.CV_32FC2);
      dstPts.data32F[0] = 0;           dstPts.data32F[1] = 0;
      dstPts.data32F[2] = outputWidth;  dstPts.data32F[3] = 0;
      dstPts.data32F[4] = outputWidth;  dstPts.data32F[5] = outputHeight;
      dstPts.data32F[6] = 0;           dstPts.data32F[7] = outputHeight;

      // 透视变换矩阵
      const M = cv.getPerspectiveTransform(srcPts, dstPts);

      // 应用变换
      const dst = new cv.Mat();
      cv.warpPerspective(
        src, dst, M,
        new cv.Size(outputWidth, outputHeight),
        cv.INTER_LINEAR,
        cv.BORDER_CONSTANT,
        new cv.Scalar()
      );

      // 输出 dataURL
      const canvas = document.createElement('canvas');
      canvas.width = outputWidth;
      canvas.height = outputHeight;
      cv.imshow(canvas, dst);
      const dataUrl = canvas.toDataURL('image/jpeg', 0.92);

      // 清理
      src.delete(); dst.delete();
      srcPts.delete(); dstPts.delete();
      M.delete();
      canvas.remove();

      return dataUrl;
    } catch (error) {
      console.error('[PaperDetector] Perspective correction failed:', error);
      throw error;
    }
  }

  /**
   * 计算像素到毫米的比例
   * @param paperFormat 纸张格式
   * @returns pixels per mm
   */
  calculatePixelRatio(paperFormat: string): number {
    const paperSizes: Record<string, { width: number; height: number }> = {
      A4: { width: 210, height: 297 },
      Letter: { width: 215.9, height: 279.4 },
      A5: { width: 148, height: 210 },
    };
    const size = paperSizes[paperFormat] || paperSizes.A4;
    return 800 / size.width;
  }
}
