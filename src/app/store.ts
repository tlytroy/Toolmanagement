import { create } from "zustand";

type Step =
  | "upload"
  | "calibration"
  | "segmentation"
  | "editor"
  | "params"
  | "export";

interface AppState {
  step: Step;
  setStep: (step: Step) => void;

  imageUrl: string | null;
  setImageUrl: (url: string) => void;

  contours: any[]; // 后期替换为真实轮廓类型
  setContours: (c: any[]) => void;
}

export const useStore = create<AppState>((set) => ({
  step: "upload",
  setStep: (step) => set({ step }),

  imageUrl: null,
  setImageUrl: (imageUrl) => set({ imageUrl }),

  contours: [],
  setContours: (contours) => set({ contours }),
}));