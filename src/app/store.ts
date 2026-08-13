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

export type CADMode = "foam" | "gridfinity";

export interface CADParams {
  mode: CADMode;
  // Foam 参数
  length_mm: number;
  width_mm: number;
  height_mm: number;
  fillet_radius: number;
  // Gridfinity 参数
  units_x: number;
  units_y: number;
  height_u: number;
  has_magnet_holes: boolean;
  // 通用参数
  embed_depth: number;
  tool_offset: number;
}

export interface CADResult {
  stl_base64: string | null;
  summary: {
    vertices: number;
    faces: number;
    volume_mm3: number;
    bounds: { x: number[]; y: number[]; z: number[] };
  } | null;
}

const defaultCADParams: CADParams = {
  mode: "foam",
  length_mm: 200,
  width_mm: 150,
  height_mm: 20,
  fillet_radius: 5,
  units_x: 3,
  units_y: 2,
  height_u: 3,
  has_magnet_holes: true,
  embed_depth: 15,
  tool_offset: 1.0,
};

interface AppState {
  step: Step;
  setStep: (step: Step) => void;

  imageUrl: string | null;
  setImageUrl: (url: string) => void;

  primitives: Primitive[];
  setPrimitives: (p: Primitive[]) => void;

  cadParams: CADParams;
  setCADParams: (p: Partial<CADParams>) => void;
  resetCADParams: () => void;

  cadResult: CADResult;
  setCADResult: (r: CADResult) => void;

  isGenerating: boolean;
  setIsGenerating: (v: boolean) => void;
}

export const useStore = create<AppState>((set) => ({
  step: "upload",
  setStep: (step) => set({ step }),

  imageUrl: null,
  setImageUrl: (imageUrl) => set({ imageUrl }),

  primitives: [],
  setPrimitives: (primitives) => set({ primitives }),

  cadParams: { ...defaultCADParams },
  setCADParams: (p) => set((s) => ({ cadParams: { ...s.cadParams, ...p } })),
  resetCADParams: () => set({ cadParams: { ...defaultCADParams } }),

  cadResult: { stl_base64: null, summary: null },
  setCADResult: (cadResult) => set({ cadResult }),

  isGenerating: false,
  setIsGenerating: (isGenerating) => set({ isGenerating }),
}));
