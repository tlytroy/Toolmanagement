import { create } from "zustand";
import type { Primitive } from "@/utils/types";

export type Step =
  | "upload"
  | "calibration"
  | "segmentation"
  | "editor"
  | "params"
  | "export"
  | "diagnose";

interface AppState {
  step: Step;
  setStep: (step: Step) => void;

  imageUrl: string | null;
  setImageUrl: (url: string) => void;

  calibratedImageUrl: string | null;
  setCalibratedImageUrl: (url: string) => void;

  contours: any[]; // OpenCV 轮廓 Mat（由 extractToolContours 返回）
  setContours: (c: any[]) => void;

  /** SAM 分割掩膜（二值 Mat 或等价结构，由 SAM 推理产出；传入 extractToolContours 做 Red∪Green 并集） */
  samMask: any | null;
  setSamMask: (m: any | null) => void;

  primitives: Primitive[]; // 基元化结果（直线/圆弧/折线）
  setPrimitives: (p: Primitive[]) => void;
}

export const useStore = create<AppState>((set) => ({
  step: "upload",
  setStep: (step) => set({ step }),

  imageUrl: null,
  setImageUrl: (imageUrl) => set({ imageUrl }),

  calibratedImageUrl: null,
  setCalibratedImageUrl: (calibratedImageUrl) => set({ calibratedImageUrl }),

  contours: [],
  setContours: (contours) => set({ contours }),

  samMask: null,
  setSamMask: (samMask) => set({ samMask }),

  primitives: [],
  setPrimitives: (primitives) => set({ primitives }),
}));