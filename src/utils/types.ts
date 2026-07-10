// 类型定义文件
export interface Point {
  x: number;
  y: number;
}

export interface PaperDetectionResult {
  corners: Point[];
  success: boolean;
}

export interface CalibrationData {
  pixelRatio: number;
  paperFormat: string;
  corners: Point[];
}

// ── 轮廓基元化（abstract primitives）────────────────
// 将工具轮廓分解为 直线 / 圆弧 / 折线 三类基元的集合

export type PrimitiveType = "line" | "arc" | "polyline";

export interface LinePrimitive {
  type: "line";
  p0: Point; // 段起点（DP 拐点）
  p1: Point; // 段终点（DP 拐点）
}

export interface ArcPrimitive {
  type: "arc";
  p0: Point; // 段起点（拟合圆弧的起端点）
  p1: Point; // 段终点（拟合圆弧的止端点）
  center: Point; // 圆心（像素坐标）
  radius: number; // 半径（像素）
  /** 起止角度（度，逆时针；已按短弧方向修正，避免画成优弧） */
  startAngle: number;
  endAngle: number;
  /** 重采样后的圆弧点列（落在拟合圆上，用于精确叠加绘制） */
  points?: Point[];
}

export interface PolylinePrimitive {
  type: "polyline";
  /** 大半径缓弯退化而成的细分折线点列 */
  points: Point[];
}

export type Primitive = LinePrimitive | ArcPrimitive | PolylinePrimitive;

/**
 * 基元化参数（与离线 contour_simplify.py / batch_process.py 对齐）
 * 采用 DP 抽稀 + 逐段拟合：DP(ε=0.004) 取拐点 → 相邻拐点间稠密点段上
 * 拟合 直线(cv2.fitLine 等价总最小二乘) / 圆弧(代数最小二乘圆拟合)，取误差小者。
 * 圆拟合用代数最小二乘（区别于 cv2.minEnclosingCircle，后者对 <180° 弧
 * 会退化为弦直径圆、半径塌缩到 ~0.707R）。
 */
export interface AbstractOptions {
  /** DP 抽稀系数，相对轮廓周长（arcLength）的比例。默认 0.004（对齐 Python EPS_DP） */
  dpEpsilon?: number;
  /** 直线均方误差容忍（px）。默认 4.0（对齐 Python LIN_TOL） */
  linTol?: number;
  /** 圆弧径向误差容忍（px）。默认 4.0（对齐 Python ARC_TOL） */
  arcTol?: number;
  /** 半径超过此值视为"缓弯"，退化为折线（段内细粒度 DP）。默认 55（对齐 Python MAX_ARC_R） */
  maxArcRadius?: number;
}