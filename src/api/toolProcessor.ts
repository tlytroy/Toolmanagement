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
 * 规范化后端返回的 primitive 数据格式
 * 后端可能返回 [x, y] 数组格式，前端统一转为 {x, y} 对象格式
 */
const toPoint = (v: any) => (Array.isArray(v) ? { x: v[0], y: v[1] } : v);

const normalizePrimitive = (p: any): Primitive => {
  const normal: any = { ...p };
  if (normal.p0) normal.p0 = toPoint(normal.p0);
  if (normal.p1) normal.p1 = toPoint(normal.p1);
  if (normal.center) normal.center = toPoint(normal.center);
  if (normal.points) normal.points = normal.points.map(toPoint);
  return normal as Primitive;
};

const normalizePrimitiveArray = (arr: any[]): Primitive[] =>
  (arr || []).map(normalizePrimitive);

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
    if (result.primitives) {
      result.primitives = normalizePrimitiveArray(result.primitives);
    }
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

import type { CADParams } from "@/app/store";

// ... (keep this import separate in the actual file)

/**
 * 生成 CAD 3D 模型（STL base64）
 * @param params CAD 参数
 * @param primitives 基元数据
 * @returns STL base64 + 统计信息
 */
export const generateCAD = async (
  params: CADParams,
  primitives: Primitive[],
): Promise<{
  success: boolean;
  error?: string;
  stl_base64?: string;
  summary?: {
    vertices: number;
    faces: number;
    volume_mm3: number;
    bounds: { x: number[]; y: number[]; z: number[] };
    length_mm?: number;
    width_mm?: number;
    height_mm?: number;
    fillet_radius?: number;
    units_x?: number;
    units_y?: number;
    height_u?: number;
  };
}> => {
  try {
    const body: any = {
      mode: params.mode,
      primitives,
      embed_depth: params.embed_depth,
      tool_offset: params.tool_offset,
    };

    if (params.mode === "foam") {
      body.foam = {
        length_mm: params.length_mm,
        width_mm: params.width_mm,
        height_mm: params.height_mm,
        fillet_radius: params.fillet_radius,
      };
    } else {
      body.gridfinity = {
        units_x: params.units_x,
        units_y: params.units_y,
        height_u: params.height_u,
        has_magnet_holes: params.has_magnet_holes,
      };
    }

    const response = await fetch("http://localhost:8001/generate-cad", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error("Error generating CAD:", error);
    return {
      success: false,
      error: error instanceof Error ? error.message : "未知错误",
    };
  }
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
 * 仅更新轮廓（不抽稀），返回原始 polyline 用于预览
 * @param maskData 蒙版数据
 * @returns 原始轮廓 polyline
 */
export const updateContour = async (maskData: {
  mask_image: string;
}): Promise<SimplifyResult> => {
  try {
    const response = await fetch("http://localhost:8001/update-contour", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(maskData),
    });
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const result = await response.json();
    if (result.primitives) {
      result.primitives = normalizePrimitiveArray(result.primitives);
    }
    return result;
  } catch (error) {
    console.error("Error updating contour:", error);
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
    if (result.primitives) {
      result.primitives = normalizePrimitiveArray(result.primitives);
    }
    return result;
  } catch (error) {
    console.error("Error simplifying contours:", error);
    return {
      success: false,
      error: error instanceof Error ? error.message : "未知错误",
    };
  }
};
