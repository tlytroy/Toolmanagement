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

export interface FingerSlot {
  /** 唯一标识 */
  id: string;
  /** 中心位置 X（相对底板中心，mm） */
  x: number;
  /** 中心位置 Y（相对底板中心，mm） */
  y: number;
  /** 胶囊长度（mm） */
  length: number;
  /** 胶囊宽度/直径（mm） */
  width: number;
  /** 深度（mm） */
  depth: number;
  /** 旋转角度（度） */
  rotation: number;
}

export interface CADParams {
  mode: CADMode;
  // Foam 参数
  length_mm: number;
  width_mm: number;
  height_mm: number;
  fillet_radius: number;
  stackable: boolean;
  stack_lip_width: number;
  stack_lip_height: number;
  // Gridfinity 参数
  units_x: number;
  units_y: number;
  height_u: number;
  has_magnet_holes: boolean;
  // 通用参数
  embed_depth: number;
  tool_offset: number;
  // 手指槽参数
  finger_slot_enabled: boolean;
  finger_slots: FingerSlot[];
  finger_slot_width: number;
  finger_slot_depth: number;
  finger_slot_length: number;
  finger_slot_auto: boolean;
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
  stackable: false,
  stack_lip_width: 3.0,
  stack_lip_height: 2.0,
  units_x: 3,
  units_y: 2,
  height_u: 3,
  has_magnet_holes: true,
  embed_depth: 15,
  tool_offset: 1.0,
  finger_slot_enabled: true,
  finger_slots: [],
  finger_slot_width: 12,
  finger_slot_depth: 10,
  finger_slot_length: 25,
  finger_slot_auto: true,
};

let fingerSlotIdCounter = 0;

export function createFingerSlot(
  x: number,
  y: number,
  length: number,
  width: number,
  depth: number,
  rotation: number = 0,
): FingerSlot {
  return {
    id: `slot_${++fingerSlotIdCounter}`,
    x,
    y,
    length,
    width,
    depth,
    rotation,
  };
}

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

  /** 添加/替换自定义手指槽列表 */
  setFingerSlots: (slots: FingerSlot[]) => void;
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

  setFingerSlots: (slots) =>
    set((s) => ({ cadParams: { ...s.cadParams, finger_slots: slots } })),
}));
