// 简化版纸张检测器，专为testpic.jpg设计
import * as cv from "@techstark/opencv-js";
import type { Point } from "./types";

export class SimplePaperDetector {
  private isCVReady = false;

  constructor() {
    this.waitForCV();
  }

  private waitForCV(): Promise<void> {
    return new Promise((resolve) => {
      const check = () => {
        if (cv.Mat && typeof cv.Mat === "function") {
          this.isCVReady = true;
          resolve();
        } else {
          setTimeout(check, 100);
        }
      };
      check();
    });
  }

  async detectPaperCorners(
    imageElement: HTMLImageElement,
  ): Promise<Point[] | null> {
    if (!this.isCVReady) {
      await this.waitForCV();
    }

    try {
      // 读取图像
      const src = cv.imread(imageElement);
      console.log("Image loaded:", src.cols, "x", src.rows);

      // 转换为灰度图
      const gray = new cv.Mat();
      cv.cvtColor(src, gray, cv.COLOR_RGBA2GRAY);

      // 高斯模糊降噪（针对木纹背景优化）
      const blurred = new cv.Mat();
      cv.GaussianBlur(gray, blurred, new cv.Size(7, 7), 0);

      // Canny边缘检测（针对高对比度图像）
      const edges = new cv.Mat();
      cv.Canny(blurred, edges, 50, 150);

      // 膨胀操作让边缘连接更紧密
      const kernel = cv.Mat.ones(5, 5, cv.CV_8U);
      const dilated = new cv.Mat();
      cv.dilate(edges, dilated, kernel);

      // 查找轮廓
      const contours = new cv.MatVector();
      const hierarchy = new cv.Mat();
      cv.findContours(
        dilated,
        contours,
        hierarchy,
        cv.RETR_EXTERNAL,
        cv.CHAIN_APPROX_SIMPLE,
      );

      console.log("Found", contours.size(), "contours");

      // 寻找最大的四边形轮廓
      let largestQuad = null;
      let maxArea = 0;

      for (let i = 0; i < contours.size(); i++) {
        const contour = contours.get(i);
        const area = cv.contourArea(contour);

        // 只考虑足够大的轮廓
        if (area > src.cols * src.rows * 0.05) {
          // 至少占图像的5%
          // 多epsilon尝试近似为多边形（提高检测成功率）
          const epsilons = [0.01, 0.015, 0.02, 0.025, 0.03];

          for (const epsilon of epsilons) {
            const approx = new cv.Mat();
            const perimeter = cv.arcLength(contour, true);
            cv.approxPolyDP(contour, approx, epsilon * perimeter, true);

            // 如果是四边形
            if (approx.rows === 4) {
              if (area > maxArea) {
                maxArea = area;
                if (largestQuad) largestQuad.contour.delete();
                largestQuad = {
                  contour: approx.clone(),
                  area: area,
                  points: this.extractPoints(approx),
                };
              } else {
                approx.delete();
              }
              break;
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
      contours.delete();
      hierarchy.delete();

      if (largestQuad) {
        console.log(
          "✅ Paper detected with",
          largestQuad.points.length,
          "points",
        );
        const points = largestQuad.points;
        largestQuad.contour.delete();
        return points as Point[];
      } else {
        console.log("❌ No paper detected");
        return null;
      }
    } catch (error) {
      console.error("Paper detection failed:", error);
      throw error;
    }
  }

  private extractPoints(approx: cv.Mat): { x: number; y: number }[] {
    const points: { x: number; y: number }[] = [];
    for (let i = 0; i < approx.rows; i++) {
      const point = approx.ptr(i, 0);
      points.push({ x: point[0], y: point[1] });
    }

    // 对四角进行排序：左上、右上、右下、左下
    return this.sortPoints(points);
  }

  private sortPoints(
    points: { x: number; y: number }[],
  ): { x: number; y: number }[] {
    if (points.length !== 4) return points;

    // 按y坐标排序，y小的在上
    points.sort((a, b) => a.y - b.y);

    // 顶部两个点按x排序，左小右大
    const topPoints = points.slice(0, 2).sort((a, b) => a.x - b.x);
    // 底部两个点按x排序，左小右大
    const bottomPoints = points.slice(2, 4).sort((a, b) => a.x - b.x);

    return [
      topPoints[0], // 左上
      topPoints[1], // 右上
      bottomPoints[1], // 右下
      bottomPoints[0], // 左下
    ];
  }
}
