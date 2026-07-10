import type { Primitive } from "@/utils/types";

export interface PaperCorner {
  x: number;
  y: number;
}

export interface CalibrationResult {
  corners: PaperCorner[];
  warped_image: string; // base64 encoded image
}

export interface ProcessResult {
  success: boolean;
  error?: string;
  calibration?: CalibrationResult;
  primitives: Primitive[];
  debug_image?: string;
  summary?: {
    lines: number;
    polylines: number;
    arcs: number;
  };
}

export interface MaskResult {
  success: boolean;
  error?: string;
  mask_image?: string; // base64 encoded image
}

export interface SimplifyResult {
  success: boolean;
  error?: string;
  primitives?: Primitive[];
  summary?: {
    lines: number;
    polylines: number;
    arcs: number;
  };
}

/**
 * 检测纸张四角
 * @param file 图片文件
 * @returns 纸张检测结果
 */
export const detectPaper = async (
  file: File,
): Promise<{
  success: boolean;
  error?: string;
  corners?: PaperCorner[];
  warped_image?: string;
}> => {
  const formData = new FormData();
  formData.append("file", file);

  try {
    const response = await fetch("http://localhost:8001/detect-paper", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const result = await response.json();
    return result;
  } catch (error) {
    console.error("Error detecting paper:", error);
    return {
      success: false,
      error: error instanceof Error ? error.message : "未知错误",
    };
  }
};

/**
 * 提取工具轮廓
 * @param file 已校正的图像文件
 * @returns 轮廓提取结果
 */
export const extractContours = async (
  file: File,
): Promise<{
  success: boolean;
  error?: string;
  primitives?: Primitive[];
  debug_image?: string;
  summary?: { lines: number; polylines: number; arcs: number };
}> => {
  const formData = new FormData();
  formData.append("file", file);

  try {
    const response = await fetch("http://localhost:8001/extract-contours", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const result = await response.json();
    return result;
  } catch (error) {
    console.error("Error extracting contours:", error);
    return {
      success: false,
      error: error instanceof Error ? error.message : "未知错误",
      primitives: [],
    };
  }
};

/**
 * 生成3D模型（后续实现）
 * @param primitives 基元数据
 * @returns 3D文件blob
 */
export const generate3DModel = async (
  primitives: Primitive[],
): Promise<Blob> => {
  const response = await fetch("http://localhost:8001/generate-3d", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ primitives }),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return await response.blob();
};

/**
 * 提取工具蒙版
 * @param file 已校正的图像文件
 * @returns 蒙版图像
 */
export const extractToolMask = async (file: File): Promise<MaskResult> => {
  const formData = new FormData();
  formData.append("file", file);

  try {
    const response = await fetch("http://localhost:8001/extract-tool-mask", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const result = await response.json();
    return result;
  } catch (error) {
    console.error("Error extracting tool mask:", error);
    return {
      success: false,
      error: error instanceof Error ? error.message : "未知错误",
    };
  }
};

/**
 * 简化轮廓（抽稀基元化）
 * @param maskData 蒙版数据
 * @returns 简化后的基元
 */
export const simplifyContours = async (maskData: {
  mask_image: string;
}): Promise<SimplifyResult> => {
  try {
    const response = await fetch("http://localhost:8001/simplify-contours", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(maskData),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const result = await response.json();
    return result;
  } catch (error) {
    console.error("Error simplifying contours:", error);
    return {
      success: false,
      error: error instanceof Error ? error.message : "未知错误",
    };
  }
};
