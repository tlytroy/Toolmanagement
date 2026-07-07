// OpenCV.js 类型定义
export interface Mat {
  rows: number;
  cols: number;
  type(): number;
  clone(): Mat;
  delete(): void;
  ptr(row: number, col: number): Uint8Array;
  data32S: Int32Array;
  data32F: Float32Array;
}

export interface Size {
  new (width: number, height: number): Size;
}

export interface Scalar {
  new (v0: number, v1: number, v2: number, v3: number): Scalar;
}

export interface Point {
  new (x: number, y: number): Point;
}

export interface MatVector {
  new (): MatVector;
  size(): number;
  get(index: number): Mat;
  delete(): void;
}

export interface OpenCV {
  // 图像读取
  imread(image: HTMLImageElement): Mat;

  // 颜色空间转换
  cvtColor(src: Mat, dst: Mat, code: number, dtype?: number): void;
  COLOR_RGBA2GRAY: number;

  // 模糊处理
  GaussianBlur(src: Mat, dst: Mat, ksize: Size, sigmaX: number, sigmaY?: number): void;
  Size: Size;

  // 边缘检测
  Canny(image: Mat, edges: Mat, threshold1: number, threshold2: number): void;

  // 轮廓查找
  findContours(
    image: Mat,
    contours: MatVector,
    hierarchy: Mat,
    mode: number,
    method: number
  ): void;
  RETR_EXTERNAL: number;
  CHAIN_APPROX_SIMPLE: number;

  // 轮廓操作
  contourArea(contour: Mat): number;
  arcLength(curve: Mat, closed: boolean): number;
  approxPolyDP(curve: Mat, approxCurve: Mat, epsilon: number, closed: boolean): void;
  isContourConvex(contour: Mat): boolean;

  // 点操作
  Point: Point;

  // 矩阵操作
  matFromArray(
    rows: number,
    cols: number,
    type: number,
    array: number[]
  ): Mat;
  getPerspectiveTransform(src: Mat, dst: Mat): Mat;
  warpPerspective(
    src: Mat,
    dst: Mat,
    M: Mat,
    dsize: Size,
    flags?: number,
    borderMode?: number,
    borderValue?: Scalar
  ): void;
  INTER_LINEAR: number;
  BORDER_CONSTANT: number;

  // 阈值处理
  threshold(
    src: Mat,
    dst: Mat,
    thresh: number,
    maxval: number,
    type: number
  ): void;
  THRESH_BINARY: number;
  THRESH_BINARY_INV: number;
  THRESH_OTSU: number;
  adaptiveThreshold(
    src: Mat,
    dst: Mat,
    maxValue: number,
    adaptiveMethod: number,
    thresholdType: number,
    blockSize: number,
    C: number
  ): void;
  ADAPTIVE_THRESH_GAUSSIAN_C: number;
  ADAPTIVE_THRESH_MEAN_C: number;

  // 轮廓绘制
  drawContours(
    image: Mat,
    contours: MatVector,
    contourIdx: number,
    color: Scalar,
    thickness: number
  ): void;

  // 其他常量
  CV_32FC2: number;
  LINE_8: number;
}

export default OpenCV;