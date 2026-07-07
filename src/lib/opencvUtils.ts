import type { OpenCV } from "@/types/opencv";
import type { Point } from "@/utils/types";

/**
 * 纸张检测结果（detectPaperCorners 的返回结构）。
 */
export interface SkewInfo {
  /** 四边形内角相对 90° 的最大偏离（度）。越小越接近正对拍摄。 */
  maxAngleDev: number;
  level: "ok" | "mild" | "severe";
  /** 角度偏斜提醒；ok 时为 null。severe 表示抠图会明显变形。 */
  message: string | null;
}

export interface PaperDetection {
  /** 排序后的四角坐标 [左上, 右上, 右下, 左下] */
  corners: Point[];
  /**
   * 置信度 0~1：
   *  - 早期强命中（首轮 Otsu 即判定为干净纸张）→ 1.0
   *  - 多方法族共识融合 → 0.85~1.0（独立方法族越多越高）
   *  - 单方法族 / 单候选兜底 → 0.4
   */
  confidence: number;
  /** 参与最终结论的独立方法族数（otsu / canny / adaptive），0~3 */
  methodCount: number;
  skew: SkewInfo;
  /** 判定模式：strong = 单方法强命中（含早期退出）；fused = 多候选/多族共识 */
  mode: "strong" | "fused";
  /** true = 低置信度（仅单方法族甚至单候选），建议用户确认或重拍 */
  lowConfidence?: boolean;
}

/**
 * 自动检测纸张四角（无需手动调参，横竖屏通用）。
 *
 * 判定流程（兼顾「傻瓜上传」的鲁棒性与多数好照片的速度）：
 *
 *  ① 首轮强命中早退：先用 Otsu + 高斯平滑(5) 跑一次，若四边形「干净」
 *     （四角明显在图内、角度近似矩形、面积合理）即直接返回，
 *     —— 好照片（绝大多数情况）只花 1 次 findContours，无需后续计算。
 *
 *  ② 三方法族多参数电池：首轮不干净才展开。每族放若干参数变体，
 *     覆盖光线/阴影/背景差异，避免「固定一组参数全失败」：
 *       · otsu 族：Otsu + 高斯(5/9) / 中值(5/7) 四种平滑
 *       · canny 族：Canny(30,90)/(50,150)/(80,200) + 膨胀闭合
 *       · adaptive 族：自适应阈值 GAUSSIAN/MEAN × block 11/21（应对光照不均）
 *
 *  ③ 按「方法族」加权共识落点：所有候选按角点距离聚类，优先取
 *     ≥2 个独立方法族一致的簇（族越多置信越高），对一致角点取平均。
 *     仅单族一致（多个参数变体碰巧一致）也接受为中置信；
 *     全无共识则拒绝并返回 null（提示重拍），优于误判。
 *
 * @param cv OpenCV实例（由 useOpenCV 注入，禁止 import 该包）
 * @param imgElement 已加载完成的 HTMLImageElement
 * @returns 检测结果；未确认返回 null
 */
export const detectPaperCorners = (
  cv: OpenCV,
  imgElement: HTMLImageElement,
): PaperDetection | null => {
  if (!cv || typeof cv.imread !== "function" || !imgElement) {
    throw new Error("OpenCV 未初始化或图片元素无效");
  }

  // 内部统一用 any，避免 OpenCV.js 动态 API 与 .d.ts 不完全对齐带来的类型摩擦
  const c: any = cv;

  const src = c.imread(imgElement);
  const gray = new c.Mat();
  c.cvtColor(src, gray, c.COLOR_RGBA2GRAY);

  // 预生成多种平滑结果，供三方法族复用（统一在 finally 释放）
  const g5 = new c.Mat();
  c.GaussianBlur(gray, g5, new c.Size(5, 5), 0);
  const g9 = new c.Mat();
  c.GaussianBlur(gray, g9, new c.Size(9, 9), 0);
  const m5 = new c.Mat();
  c.medianBlur(gray, m5, 5);
  const m7 = new c.Mat();
  c.medianBlur(gray, m7, 7);

  const cols = src.cols;
  const rows = src.rows;
  const imgArea = cols * rows;
  const minArea = imgArea * 0.12; // 纸张至少占图 12%
  const maxArea = imgArea * 0.98; // 排除"整张图的边框矩形"（占满全图）
  const margin = Math.max(4, Math.round(0.008 * Math.min(cols, rows))); // 基础边距，排除贴边框溢出

  type Cand = { pts: Point[]; family: "otsu" | "canny" | "adaptive" };

  try {
    // —— ① 首轮强命中早退 ——
    const primary = otsuQuad(c, g5, minArea, maxArea, cols, rows, margin);
    if (primary && isStrong(primary, cols, rows)) {
      const skew = skewOf(primary);
      console.info("[detectPaperCorners] 首轮 Otsu 强命中，早退");
      return { corners: primary, confidence: 1, methodCount: 1, skew, mode: "strong" };
    }

    // —— ② 三方法族多参数电池 ——
    const cands: Cand[] = [];

    // otsu 族：四种平滑变体
    for (const sm of [g5, g9, m5, m7]) {
      const q = otsuQuad(c, sm, minArea, maxArea, cols, rows, margin);
      if (q) cands.push({ pts: q, family: "otsu" });
    }

    // canny 族：三档阈值 + 膨胀闭合断裂纸边
    const cannyCfg: [number, number, number][] = [
      [30, 90, 3],
      [50, 150, 5],
      [80, 200, 7],
    ];
    for (const [lo, hi, ks] of cannyCfg) {
      const ed = new c.Mat();
      c.Canny(gray, ed, lo, hi);
      const k = c.getStructuringElement(c.MORPH_RECT, new c.Size(ks, ks));
      c.dilate(ed, ed, k);
      k.delete();
      const q = findLargestQuad(c, ed, minArea, maxArea, cols, rows, margin);
      ed.delete();
      if (q) cands.push({ pts: q, family: "canny" });
    }

    // adaptive 族：GAUSSIAN/MEAN × block 11/21，应对光照不均/阴影
    const adMethods = [c.ADAPTIVE_THRESH_GAUSSIAN_C, c.ADAPTIVE_THRESH_MEAN_C];
    for (const method of adMethods) {
      for (const bs of [11, 21]) {
        const ad = new c.Mat();
        c.adaptiveThreshold(g5, ad, 255, method, c.THRESH_BINARY, bs, 4);
        const q = findLargestQuad(c, ad, minArea, maxArea, cols, rows, margin);
        ad.delete();
        if (q) cands.push({ pts: q, family: "adaptive" });
      }
    }

    if (cands.length === 0) {
      console.warn("[detectPaperCorners] 全参数电池均未检出纸张");
      return null;
    }

    // —— ③ 按方法族加权共识落点 ——
    const diagonal = Math.hypot(cols, rows);
    const tol = 0.16 * diagonal; // 角点平均距离容忍阈值

    // 贪心聚类：距离 ≤ tol 的候选归入同一簇
    const clusters: Cand[][] = [];
    for (const cd of cands) {
      const hit = clusters.find((cl) => quadDist(cl[0].pts, cd.pts) <= tol);
      if (hit) hit.push(cd);
      else clusters.push([cd]);
    }
    clusters.sort((a, b) => b.length - a.length);

    const best = clusters[0];
    const families = new Set(best.map((x) => x.family));

    // 优先：≥2 独立方法族一致 → 高置信融合
    if (families.size >= 2) {
      const fused = averageQuads(best.map((x) => x.pts));
      const skew = skewOf(fused);
      const confidence = Math.min(1, 0.6 + 0.2 * families.size);
      console.info(
        `[detectPaperCorners] 多族共识（${families.size} 族 / ${best.length} 候选），融合落点`,
      );
      return {
        corners: fused,
        confidence,
        methodCount: families.size,
        skew,
        mode: "fused",
      };
    }

    // 次选：单族多候选一致（多个参数变体碰巧一致）→ 中置信
    if (best.length >= 2) {
      const fused = averageQuads(best.map((x) => x.pts));
      const skew = skewOf(fused);
      console.warn(
        `[detectPaperCorners] 仅单方法族一致（${best.length} 变体），中置信接受`,
      );
      return {
        corners: fused,
        confidence: 0.6,
        methodCount: 1,
        skew,
        mode: "fused",
        lowConfidence: true,
      };
    }

    // 兜底：单候选但足够干净 → 低置信接受（优于直接拒绝）
    if (isStrong(best[0].pts, cols, rows)) {
      const skew = skewOf(best[0].pts);
      console.warn("[detectPaperCorners] 仅单候选命中，低置信度接受");
      return {
        corners: best[0].pts,
        confidence: 0.4,
        methodCount: 1,
        skew,
        mode: "strong",
        lowConfidence: true,
      };
    }

    console.warn("[detectPaperCorners] 共识不足，判定为干扰/误检");
    return null;
  } finally {
    // 兜底释放，防止任何路径下内存泄漏
    src.delete();
    gray.delete();
    g5.delete();
    g9.delete();
    m5.delete();
    m7.delete();
  }
};

/** Otsu 二值化取最大四边形（白纸为亮前景）。 */
const otsuQuad = (
  c: any,
  sm: any,
  minArea: number,
  maxArea: number,
  cols: number,
  rows: number,
  margin: number,
): Point[] | null => {
  const th = new c.Mat();
  c.threshold(sm, th, 0, 255, c.THRESH_BINARY + c.THRESH_OTSU);
  const q = findLargestQuad(c, th, minArea, maxArea, cols, rows, margin);
  th.delete();
  return q;
};

/**
 * 强命中判定：四边形「干净」到可以信任——四角明显在图内、近似矩形、面积不过界。
 * 用于首轮早退与单候选兜底，避免把贴边框的伪轮廓当真。
 */
const isStrong = (pts: Point[], cols: number, rows: number): boolean => {
  const m = Math.max(4, Math.round(0.025 * Math.min(cols, rows))); // 比基础 margin 更严格
  return inBounds(pts, cols, rows, m) && anglesValid(pts, 75, 105);
};

/**
 * 从二值/边缘图中查找最大的合法四边形轮廓。
 * 要求：面积在 [minArea, maxArea]、approxPolyDP 可逼近为 4 点、凸、内角合理、四角在图内。
 */
const findLargestQuad = (
  c: any,
  bin: any,
  minArea: number,
  maxArea: number,
  cols: number,
  rows: number,
  margin: number,
): Point[] | null => {
  const contours = new c.MatVector();
  const hierarchy = new c.Mat();
  c.findContours(bin, contours, hierarchy, c.RETR_EXTERNAL, c.CHAIN_APPROX_SIMPLE);

  let best: { pts: Point[]; area: number } | null = null;

  for (let i = 0; i < contours.size(); i++) {
    const cnt = contours.get(i);
    const area = c.contourArea(cnt);
    if (area < minArea || area > maxArea) {
      cnt.delete();
      continue;
    }

    const peri = c.arcLength(cnt, true);
    let foundPts: Point[] | null = null;

    // 多 epsilon 逼近，提高四边形识别率（扩展到 0.06 以覆盖 Canny 圆角/缺口）
    for (const eps of [0.01, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05, 0.06]) {
      const approx = new c.Mat();
      c.approxPolyDP(cnt, approx, eps * peri, true);
      const nPts = approx.rows === 1 ? approx.cols : approx.rows;
      if (nPts === 4) {
        const pts = ptsFromMat(approx);
        if (
          c.isContourConvex(approx) &&
          anglesValid(pts, 40, 140) &&
          inBounds(pts, cols, rows, margin)
        ) {
          foundPts = sortPoints(pts);
          approx.delete();
          break;
        }
      }
      approx.delete();
    }

    if (foundPts) {
      if (!best || area > best.area) best = { pts: foundPts, area };
    }
    cnt.delete();
  }

  contours.delete();
  hierarchy.delete();
  return best ? best.pts : null;
};

/**
 * 读取 approx(CV_32SC2, 4×1) 的四角坐标。
 * ⚠️ 坑：本构建（@techstark/opencv-js 5.0）下 `approx.ptr(i, 0)` 读 CV_32SC2 会错位
 *    （y 恒为 0），导致所有点塌到图像顶边、inBounds 全拒。务必用 data32S 或 intPtr。
 * 已用 Node 最小复现验证：data32S=[x0,y0,x1,y1,...] 与 intPtr(i)=[x,y] 均正确，ptr 错误。
 */
const ptsFromMat = (approx: any): Point[] => {
  const pts: Point[] = [];
  const s = approx.data32S as Int32Array;
  for (let i = 0; i < 4; i++) {
    pts.push({ x: s[i * 2], y: s[i * 2 + 1] });
  }
  return pts;
};

/** 四边形四角是否都在图像边界内（排除贴边框的溢出轮廓）。 */
const inBounds = (pts: Point[], cols: number, rows: number, margin: number): boolean =>
  pts.every((p) => p.x >= margin && p.x <= cols - margin && p.y >= margin && p.y <= rows - margin);

/** 校验四边形内角是否在 [minAngle, maxAngle] 区间内。 */
const anglesValid = (pts: Point[], minAngle: number, maxAngle: number): boolean => {
  for (let i = 0; i < 4; i++) {
    const p1 = pts[i];
    const p2 = pts[(i + 1) % 4];
    const p3 = pts[(i + 2) % 4];
    const v1 = { x: p1.x - p2.x, y: p1.y - p2.y };
    const v2 = { x: p3.x - p2.x, y: p3.y - p2.y };
    const m1 = Math.hypot(v1.x, v1.y);
    const m2 = Math.hypot(v2.x, v2.y);
    if (m1 === 0 || m2 === 0) continue;
    const cos = (v1.x * v2.x + v1.y * v2.y) / (m1 * m2);
    const ang = (Math.acos(Math.max(-1, Math.min(1, cos))) * 180) / Math.PI;
    if (ang < minAngle || ang > maxAngle) return false;
  }
  return true;
};

/** 计算四边形四个内角（度），顺序对应 pts 的顶点顺序。 */
const interiorAngles = (pts: Point[]): number[] => {
  const angs: number[] = [];
  for (let i = 0; i < 4; i++) {
    const p1 = pts[i];
    const p2 = pts[(i + 1) % 4];
    const p3 = pts[(i + 2) % 4];
    const v1 = { x: p1.x - p2.x, y: p1.y - p2.y };
    const v2 = { x: p3.x - p2.x, y: p3.y - p2.y };
    const m1 = Math.hypot(v1.x, v1.y);
    const m2 = Math.hypot(v2.x, v2.y);
    const cos = m1 === 0 || m2 === 0 ? 1 : (v1.x * v2.x + v1.y * v2.y) / (m1 * m2);
    angs.push((Math.acos(Math.max(-1, Math.min(1, cos))) * 180) / Math.PI);
  }
  return angs;
};

/**
 * 角度偏斜评估：内角偏离 90° 越多，说明拍摄视角越倾斜。
 * 视角过偏时透视校正仍会引入明显变形，工具抠图会出问题，故需提醒用户。
 */
const skewOf = (quad: Point[]): SkewInfo => {
  const angs = interiorAngles(quad);
  const maxDev = Math.max(...angs.map((a) => Math.abs(a - 90)));
  const dev = Math.round(maxDev * 10) / 10;
  if (maxDev > 25) {
    return {
      maxAngleDev: dev,
      level: "severe",
      message:
        "⚠️ 角度过偏：受拍摄视角影响，透视校正后工具抠图会出现明显变形。请尽量正对纸张俯拍后重试。",
    };
  }
  if (maxDev > 12) {
    return {
      maxAngleDev: dev,
      level: "mild",
      message:
        "⚠️ 角度略偏：透视校正后纸张边缘可能有轻微变形，如结果不理想请正对纸张重新拍摄。",
    };
  }
  return { maxAngleDev: dev, level: "ok", message: null };
};

/** 两组四边形（同为 [TL,TR,BR,BL] 顺序）的角点平均距离。 */
const quadDist = (a: Point[], b: Point[]): number => {
  let sum = 0;
  for (let i = 0; i < 4; i++) sum += Math.hypot(a[i].x - b[i].x, a[i].y - b[i].y);
  return sum / 4;
};

/** 对多组四边形（同顺序）的角点逐点取平均，得到精化结果。 */
const averageQuads = (group: Point[][]): Point[] => {
  const out: Point[] = [];
  for (let i = 0; i < 4; i++) {
    let x = 0;
    let y = 0;
    for (const q of group) {
      x += q[i].x;
      y += q[i].y;
    }
    out.push({ x: Math.round(x / group.length), y: Math.round(y / group.length) });
  }
  return out;
};

// 四角排序算法：左上→右上→右下→左下
function sortPoints(points: Point[]): Point[] {
  points.sort((a, b) => a.y - b.y);
  const top = points.slice(0, 2).sort((a, b) => a.x - b.x);
  const bottom = points.slice(2, 4).sort((a, b) => a.x - b.x);
  return [top[0], top[1], bottom[1], bottom[0]];
}

/**
 * 透视校正（横竖屏自适应）
 * @param cv OpenCV实例
 * @param imgElement 校正前的原始图片
 * @param corners 纸张四角坐标（顺序：左上、右上、右下、左下）
 * @returns 校正后的图像 dataURL、像素→毫米换算 scale、输出尺寸
 */
export const perspectiveWarp = (
  cv: OpenCV,
  imgElement: HTMLImageElement,
  corners: Point[],
) => {
  const c: any = cv;
  const src = c.imread(imgElement);

  try {
    const d = (a: Point, b: Point) => Math.hypot(a.x - b.x, a.y - b.y);
    const wTop = d(corners[0], corners[1]);
    const wBot = d(corners[3], corners[2]);
    const hLeft = d(corners[0], corners[3]);
    const hRight = d(corners[1], corners[2]);
    const W = (wTop + wBot) / 2;
    const H = (hLeft + hRight) / 2;

    // 保持 A4 比例（297×210 ≈ 1.414 → 1131×800），并跟随检测到的横/竖方向
    const LONG = 1131;
    const SHORT = 800;
    const dstW = W >= H ? LONG : SHORT;
    const dstH = W >= H ? SHORT : LONG;
    const dstSize = new c.Size(dstW, dstH);

    // 像素 → 毫米：A4 长边 = 297mm
    const scaleMmPerPx = 297 / LONG;

    const dstPoints = c.matFromArray(4, 1, c.CV_32FC2, [
      0,
      0,
      dstW - 1,
      0,
      dstW - 1,
      dstH - 1,
      0,
      dstH - 1,
    ]);

    const srcPoints = c.matFromArray(4, 1, c.CV_32FC2, [
      corners[0].x,
      corners[0].y,
      corners[1].x,
      corners[1].y,
      corners[2].x,
      corners[2].y,
      corners[3].x,
      corners[3].y,
    ]);

    const M = c.getPerspectiveTransform(srcPoints, dstPoints);
    const dst = new c.Mat();

    c.warpPerspective(
      src,
      dst,
      M,
      dstSize,
      c.INTER_LINEAR,
      c.BORDER_CONSTANT,
      new c.Scalar(0, 0, 0, 0),
    );

    const canvas = document.createElement("canvas");
    c.imshow(canvas, dst);
    const warpedUrl = canvas.toDataURL();

    return { warpedUrl, scaleMmPerPx, widthPx: dstW, heightPx: dstH };
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
      const c: any = cv;
      const src = c.imread(img);
      const gray = new c.Mat();
      const thresh = new c.Mat();
      const contours = new c.MatVector();
      const hierarchy = new c.Mat();

      try {
        // 预处理
        c.cvtColor(src, gray, c.COLOR_RGBA2GRAY, 0);
        c.threshold(gray, thresh, 0, 255, c.THRESH_BINARY_INV + c.THRESH_OTSU);

        // 寻找轮廓
        c.findContours(thresh, contours, hierarchy, c.RETR_EXTERNAL, c.CHAIN_APPROX_SIMPLE);

        // 过滤小轮廓
        const filteredContours = [];
        for (let i = 0; i < contours.size(); i++) {
          const contour = contours.get(i);
          const area = c.contourArea(contour);
          if (area >= minArea) {
            filteredContours.push(contour);
          } else {
            contour.delete();
          }
        }

        // 绘制轮廓到调试图像
        const debugImg = src.clone();
        c.drawContours(debugImg, contours, -1, new c.Scalar(0, 255, 0, 255), 2);

        // 转换为Data URL
        const canvas = document.createElement("canvas");
        c.imshow(canvas, debugImg);
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
