/**
 * useWorkflow - 工作流编排 Hook
 * ==============================
 * 封装完整的"图片→纸张检测→轮廓提取→蒙版编辑→抽稀基元化→CAD生成"流水线。
 *
 * 职责：
 *   1. 串联各 API 调用（detectPaper → extractContours → simplifyContours → generateCAD）
 *   2. 管理每一步的 loading/error 状态
 *   3. 自动更新 Zustand store（step / imageUrl / primitives / cadResult 等）
 *   4. 提供高级组合操作（如"一键检测"：检测纸张 + 提取轮廓 + 生成蒙版）
 *
 * 使用方式：
 *   const { calibrate, segment, simplify, generate, isProcessing } = useWorkflow();
 */

import { useState, useCallback } from "react";
import { useStore, type FingerSlot } from "@/app/store";
import type { Primitive } from "@/utils/types";
import {
  detectPaper,
  extractContours,
  extractToolMask,
  simplifyContours,
  updateContour,
  generateCAD,
  generateSTEP,
  autoFingerSlots,
  type SimplifyResult,
} from "@/api/toolProcessor";

// ── 状态类型 ─────────────────────────────────────

export interface WorkflowState {
  /** 是否正在处理中 */
  isProcessing: boolean;
  /** 当前步骤的 loading 状态 */
  stepLoading: {
    calibrate: boolean;
    segment: boolean;
    simplify: boolean;
    generateCAD: boolean;
  };
  /** 当前步骤的错误信息 */
  stepError: {
    calibrate: string | null;
    segment: string | null;
    simplify: string | null;
    generateCAD: string | null;
  };
  /** 蒙版图像 base64（用于编辑器） */
  maskImage: string | null;
  /** CAD 生成进度（0-100） */
  generationProgress: number;
}

// ── 默认状态 ─────────────────────────────────────

const defaultState: WorkflowState = {
  isProcessing: false,
  stepLoading: {
    calibrate: false,
    segment: false,
    simplify: false,
    generateCAD: false,
  },
  stepError: {
    calibrate: null,
    segment: null,
    simplify: null,
    generateCAD: null,
  },
  maskImage: null,
  generationProgress: 0,
};

// ── Hook ─────────────────────────────────────────

export function useWorkflow() {
  const [state, setState] = useState<WorkflowState>(defaultState);

  const setStore = useStore((s) => ({
    setStep: s.setStep,
    setImageUrl: s.setImageUrl,
    setPrimitives: s.setPrimitives,
    setCADParams: s.setCADParams,
    setCADResult: s.setCADResult,
    setIsGenerating: s.setIsGenerating,
    setFingerSlots: s.setFingerSlots,
  }));

  // ── 辅助函数 ─────────────────────────────────

  const updateLoading = useCallback(
    (step: keyof WorkflowState["stepLoading"], value: boolean) => {
      setState((prev) => ({
        ...prev,
        stepLoading: { ...prev.stepLoading, [step]: value },
        isProcessing:
          value ||
          Object.values(prev.stepLoading).some(
            (v, i) =>
              i !==
                Object.keys(prev.stepLoading).indexOf(
                  step as keyof WorkflowState["stepLoading"],
                ) && v,
          ),
      }));
    },
    [],
  );

  const setError = useCallback(
    (step: keyof WorkflowState["stepError"], error: string | null) => {
      setState((prev) => ({
        ...prev,
        stepError: { ...prev.stepError, [step]: error },
      }));
    },
    [],
  );

  // =============================================
  // 1. 纸张检测 + 透视校正
  // =============================================

  const calibrate = useCallback(
    async (file: File): Promise<boolean> => {
      updateLoading("calibrate", true);
      setError("calibrate", null);

      try {
        const result = await detectPaper(file);

        if (!result.success) {
          setError("calibrate", result.error || "纸张检测失败");
          return false;
        }

        // 保存校正后的图像到 store
        if (result.warped_image) {
          setStore.setImageUrl(result.warped_image);
        }

        setStore.setStep("calibration");
        return true;
      } catch (e) {
        setError("calibrate", e instanceof Error ? e.message : "未知错误");
        return false;
      } finally {
        updateLoading("calibrate", false);
      }
    },
    [updateLoading, setError, setStore],
  );

  // =============================================
  // 2. 轮廓提取 + 蒙版生成
  // =============================================

  const segment = useCallback(
    async (file: File): Promise<boolean> => {
      updateLoading("segment", true);
      setError("segment", null);

      try {
        // 2a. 提取轮廓基元
        const contourResult = await extractContours(file);

        if (!contourResult.success) {
          setError("segment", contourResult.error || "轮廓提取失败");
          return false;
        }

        // 保存基元到 store
        if (contourResult.primitives) {
          setStore.setPrimitives(contourResult.primitives);
        }

        // 2b. 生成蒙版
        const maskResult = await extractToolMask(file);

        if (maskResult.success && maskResult.mask_image) {
          setState((prev) => ({ ...prev, maskImage: maskResult.mask_image! }));
        }

        setStore.setStep("segmentation");
        return true;
      } catch (e) {
        setError("segment", e instanceof Error ? e.message : "未知错误");
        return false;
      } finally {
        updateLoading("segment", false);
      }
    },
    [updateLoading, setError, setStore],
  );

  // =============================================
  // 3. 一键检测：纸张检测 + 轮廓提取 + 蒙版生成
  // =============================================

  const detectAll = useCallback(
    async (file: File): Promise<boolean> => {
      updateLoading("calibrate", true);
      updateLoading("segment", true);
      setError("calibrate", null);
      setError("segment", null);

      try {
        // 第一步：纸张检测
        const calibResult = await detectPaper(file);

        if (!calibResult.success) {
          setError("calibrate", calibResult.error || "纸张检测失败");
          return false;
        }

        if (calibResult.warped_image) {
          setStore.setImageUrl(calibResult.warped_image);
        }

        // 将校正后的 base64 转为 File 对象，传给轮廓提取
        const warpedBlob = dataURLToBlob(calibResult.warped_image!);
        const warpedFile = new File([warpedBlob], "warped.jpg", {
          type: "image/jpeg",
        });

        // 第二步：轮廓提取
        const contourResult = await extractContours(warpedFile);

        if (!contourResult.success) {
          setError("segment", contourResult.error || "轮廓提取失败");
          return false;
        }

        if (contourResult.primitives) {
          setStore.setPrimitives(contourResult.primitives);
        }

        // 第三步：生成蒙版
        const maskResult = await extractToolMask(warpedFile);

        if (maskResult.success && maskResult.mask_image) {
          setState((prev) => ({ ...prev, maskImage: maskResult.mask_image! }));
        }

        setStore.setStep("segmentation");
        return true;
      } catch (e) {
        setError("calibrate", e instanceof Error ? e.message : "一键检测失败");
        return false;
      } finally {
        updateLoading("calibrate", false);
        updateLoading("segment", false);
      }
    },
    [updateLoading, setError, setStore],
  );

  // =============================================
  // 4. 抽稀基元化（简化轮廓）
  // =============================================

  const simplify = useCallback(
    async (maskImage?: string): Promise<SimplifyResult | null> => {
      updateLoading("simplify", true);
      setError("simplify", null);

      const mask = maskImage || state.maskImage;
      if (!mask) {
        setError("simplify", "没有可用的蒙版图像");
        return null;
      }

      try {
        const result = await simplifyContours({ mask_image: mask });

        if (result.success && result.primitives) {
          setStore.setPrimitives(result.primitives);
        }

        if (!result.success) {
          setError("simplify", result.error || "抽稀基元化失败");
        }

        return result;
      } catch (e) {
        setError("simplify", e instanceof Error ? e.message : "未知错误");
        return null;
      } finally {
        updateLoading("simplify", false);
      }
    },
    [updateLoading, setError, setStore, state.maskImage],
  );

  // =============================================
  // 5. 更新轮廓（蒙版编辑后预览）
  // =============================================

  const refreshContour = useCallback(
    async (maskImage: string): Promise<Primitive[] | null> => {
      try {
        const result = await updateContour({ mask_image: maskImage });

        if (result.success && result.primitives) {
          // 只更新蒙版，不替换已抽稀的基元
          setState((prev) => ({ ...prev, maskImage }));
          return result.primitives;
        }

        return null;
      } catch (e) {
        console.error("刷新轮廓失败:", e);
        return null;
      }
    },
    [],
  );

  // =============================================
  // 6. 生成 CAD 3D 模型（STL/STEP）
  // =============================================

  const generate = useCallback(
    async ({
      primitives,
      fingerSlots,
    }: {
      primitives?: Primitive[];
      fingerSlots?: FingerSlot[];
    } = {}): Promise<boolean> => {
      updateLoading("generateCAD", true);
      setError("generateCAD", null);
      setStore.setIsGenerating(true);
      setState((prev) => ({ ...prev, generationProgress: 0 }));

      try {
        const storeState = useStore.getState();
        const params = storeState.cadParams;
        const inputPrimitives = primitives || storeState.primitives;
        const inputSlots = fingerSlots || params.finger_slots;

        // 6a. 自动检测手指槽（如果启用）
        let finalSlots = inputSlots;
        if (
          params.finger_slot_auto &&
          (!inputSlots || inputSlots.length === 0)
        ) {
          setState((prev) => ({ ...prev, generationProgress: 20 }));

          const autoResult = await autoFingerSlots({
            mode: params.mode,
            foam: {
              length_mm: params.length_mm,
              width_mm: params.width_mm,
              height_mm: params.height_mm,
            },
            gridfinity: {
              units_x: params.units_x,
              units_y: params.units_y,
              height_u: params.height_u,
            },
            primitives: inputPrimitives,
            tool_offset: params.tool_offset,
            slot_width: params.finger_slot_width,
            slot_depth: params.finger_slot_depth,
            slot_length: params.finger_slot_length,
          });

          if (autoResult.success && autoResult.finger_slots) {
            finalSlots = autoResult.finger_slots.map((s, i) => ({
              id: `auto_${i + 1}`,
              x: s.x,
              y: s.y,
              length: s.length,
              width: s.width,
              depth: s.depth,
              rotation: s.rotation,
            }));
            // 保存自动检测结果到 store
            setStore.setFingerSlots(finalSlots);
          }
        }

        setState((prev) => ({ ...prev, generationProgress: 50 }));

        // 6b. 生成 STL
        const stlResult = await generateCAD(
          { ...params, finger_slots: finalSlots },
          inputPrimitives,
        );

        if (!stlResult.success) {
          setError("generateCAD", stlResult.error || "CAD 生成失败");
          return false;
        }

        setState((prev) => ({ ...prev, generationProgress: 75 }));

        // 6c. 生成 STEP（可选，静默失败不影响主流程）
        const stepResult = await generateSTEP(
          { ...params, finger_slots: finalSlots },
          inputPrimitives,
        );

        setState((prev) => ({ ...prev, generationProgress: 100 }));

        // 6d. 保存结果到 store
        setStore.setCADResult({
          stl_base64: stlResult.stl_base64 || null,
          step_base64: stepResult.step_base64 || null,
          summary: stlResult.summary || null,
        });

        // 如果有堆叠参数，保存到 store
        if (stlResult.summary) {
          const s = stlResult.summary;
          if (s.length_mm) setStore.setCADParams({ length_mm: s.length_mm });
          if (s.width_mm) setStore.setCADParams({ width_mm: s.width_mm });
          if (s.height_mm) setStore.setCADParams({ height_mm: s.height_mm });
          if (s.fillet_radius !== undefined)
            setStore.setCADParams({ fillet_radius: s.fillet_radius });
          if (s.units_x) setStore.setCADParams({ units_x: s.units_x });
          if (s.units_y) setStore.setCADParams({ units_y: s.units_y });
          if (s.height_u) setStore.setCADParams({ height_u: s.height_u });
        }

        setStore.setStep("export");
        return true;
      } catch (e) {
        setError("generateCAD", e instanceof Error ? e.message : "未知错误");
        return false;
      } finally {
        updateLoading("generateCAD", false);
        setStore.setIsGenerating(false);
        setState((prev) => ({ ...prev, generationProgress: 0 }));
      }
    },
    [updateLoading, setError, setStore],
  );

  // =============================================
  // 7. 重置工作流状态
  // =============================================

  const reset = useCallback(() => {
    setState(defaultState);
  }, []);

  // =============================================
  // 返回值
  // =============================================

  return {
    // 状态
    ...state,

    // 操作
    calibrate,
    segment,
    detectAll,
    simplify,
    refreshContour,
    generate,
    reset,

    // 便捷访问
    maskImage: state.maskImage,
  };
}

// ── 工具函数 ─────────────────────────────────────

/**
 * 将 data URL 转换为 Blob
 */
function dataURLToBlob(dataURL: string): Blob {
  const parts = dataURL.split(",");
  const mimeMatch = parts[0]?.match(/:(.*?);/);
  const mime = mimeMatch?.[1] || "image/jpeg";
  const byteStr = atob(parts[1] || "");
  const arr = new Uint8Array(byteStr.length);
  for (let i = 0; i < byteStr.length; i++) {
    arr[i] = byteStr.charCodeAt(i);
  }
  return new Blob([arr], { type: mime });
}
