import { Icon } from "@/components/ui/icons";
import { MaskEditor } from "@/features/editor/MaskEditor";
import type { Primitive } from "@/utils/types";
import { Button } from "@/components/ui/Button";
import { useState, useRef } from "react";

interface EditorPanelProps {
  maskUrl?: string;
  onMaskUpdate?: (updatedMask: string) => void;
  simplifiedPrimitives: Primitive[];
  setSimplifiedPrimitives: (primitives: Primitive[]) => void;
  originalContour?: string; // 原始轮廓图像（红色边框）
  backgroundImage?: string; // 背景图像（用于半透明叠加）
}

export function EditorPanel({
  maskUrl,
  onMaskUpdate,
  simplifiedPrimitives,
  setSimplifiedPrimitives,
  originalContour,
  backgroundImage
}: EditorPanelProps) {
  const [isApplying, setIsApplying] = useState(false);
  const maskEditorRef = useRef<{ handleSimplify: () => Promise<void> }>(null);

  const handleApplyChanges = async () => {
    setIsApplying(true);
    if (maskEditorRef.current) {
      await maskEditorRef.current.handleSimplify();
    }
    setIsApplying(false);
  };
  if (maskUrl && onMaskUpdate) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2 mb-1">
          <span className="w-7 h-7 rounded-lg bg-brand-600/20 text-brand-300 flex items-center justify-center">
            <Icon name="pencil" size={15} />
          </span>
          <h2 className="text-sm font-semibold text-zinc-100">矢量轮廓编辑器</h2>
        </div>
        <div className="text-sm text-zinc-400 mb-4">
          使用画笔工具调整蒙版区域，橡皮擦工具删除不需要的区域。
        </div>
        <MaskEditor
          maskImage={maskUrl}
          onMaskUpdate={onMaskUpdate}
          onSimplifyComplete={(result) => {
            if (result.success && result.primitives) {
              setSimplifiedPrimitives(result.primitives);
            }
          }}
          originalContour={originalContour}
          backgroundImage={backgroundImage}
        />
      </div>
    );
  } else {
    return (
      <div>
        <div className="flex items-center gap-2 mb-1">
          <span className="w-7 h-7 rounded-lg bg-brand-600/20 text-brand-300 flex items-center justify-center">
            <Icon name="pencil" size={15} />
          </span>
          <h2 className="text-sm font-semibold text-zinc-100">矢量轮廓编辑器</h2>
        </div>
        <div className="mt-3 rounded-xl bg-canvas-800 border border-canvas-700 border-dashed p-5 flex flex-col items-center text-center gap-2">
          <span className="w-10 h-10 rounded-xl bg-canvas-700 text-zinc-400 flex items-center justify-center">
            <Icon name="wand" size={20} />
          </span>
          <p className="text-sm font-medium text-zinc-300">请先完成轮廓提取</p>
          <p className="text-[12px] text-zinc-500 leading-relaxed">
            需要先在"轮廓提取"步骤中生成工具蒙版
          </p>
        </div>
      </div>
    );
  }
}