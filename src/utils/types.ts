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