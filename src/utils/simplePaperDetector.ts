// 简化版纸张检测器，专为testpic.jpg设计
import * as cv from '@techstark/opencv-js';

export class SimplePaperDetector {
  private isCVReady = false;

  constructor() {
    this.waitForCV();
  }

  private waitForCV(): Promise<void> {
    return new Promise((resolve) => {
      const check = () => {
        if (cv.Mat && typeof cv.Mat === 'function') {
          this.isCVReady = true;
          resolve();
        } else {
          setTimeout(check, 100);
        }
      };
      check();
    });
  }

  async detectPaperCorners(imageElement: HTMLImageElement): Promise<any[]> {
    if (!this.isCVReady) {
      await this.waitForCV();
    }

    try {
      // 读取图像
      const src = cv.imread(imageElement);
      console.log('Image loaded:', src.cols, 'x', src.rows);

      // 转换为灰度图
      const gray = new cv.Mat();
      cv.cvtColor(src, gray, cv.COLOR_RGBA2GRAY);

      // 高斯模糊降噪
      const blurred = new cv.Mat();
      cv.GaussianBlur(gray, blurred, new cv.Size(5, 5), 0);

      // 自适应阈值分割
      const thresh = new cv.Mat();
      cv.adaptiveThreshold(blurred, thresh, 255, cv.ADAPTIVE_THRESH_GAUSSIAN_C, cv.THRESH_BINARY, 11, 2);

      // 反转（让纸张变为白色）
      const inverted = new cv.Mat();
      cv.bitwise_not(thresh, inverted);

      // 查找轮廓
      const contours = new cv.MatVector();
      const hierarchy = new cv.Mat();
      cv.findContours(inverted, contours, hierarchy, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE);

      console.log('Found', contours.size(), 'contours');

      // 寻找最大的四边形轮廓
      let largestQuad = null;
      let maxArea = 0;

      for (let i = 0; i < contours.size(); i++) {
        const contour = contours.get(i);
        const area = cv.contourArea(contour);

        // 只考虑足够大的轮廓
        if (area > src.cols * src.rows * 0.1) { // 至少占图像的10%
          // 近似为多边形
          const perimeter = cv.arcLength(contour, true);
          const approx = new cv.Mat();
          cv.approxPolyDP(contour, approx, 0.02 * perimeter, true);

          // 如果是四边形
          if (approx.rows === 4) {
            if (area > maxArea) {
              maxArea = area;
              largestQuad = {
                contour: approx,
                area: area,
                points: this.extractPoints(approx)
              };
            } else {
              approx.delete();
            }
          } else {
            approx.delete();
          }
        }
        contour.delete();
      }

      // 清理
      src.delete();
      gray.delete();
      blurred.delete();
      thresh.delete();
      inverted.delete();
      contours.delete();
      hierarchy.delete();

      if (largestQuad) {
        console.log('Paper detected with', largestQuad.points.length, 'points');
        const points = largestQuad.points;
        largestQuad.contour.delete();
        return points;
      } else {
        console.log('No paper detected');
        return [];
      }

    } catch (error) {
      console.error('Paper detection failed:', error);
      throw error;
    }
  }

  private extractPoints(approx: any): any[] {
    const points: any[] = [];
    for (let i = 0; i < approx.rows; i++) {
      const point = approx.ptr(i, 0);
      points.push({ x: point[0], y: point[1] });
    }
    return points;
  }
}