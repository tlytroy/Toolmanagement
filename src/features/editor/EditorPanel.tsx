import { Icon } from "@/components/ui/icons";
import { MaskEditor } from "@/features/editor/MaskEditor";
import type { Primitive } from "@/utils/types";
import { useRef } from "react";

interface EditorPanelProps {
  maskUrl?: string;
  onMaskUpdate?: (updatedMask: string) => void;
  simplifiedPrimitives: Primitive[];
  setSimplifiedPrimitives: (primitives: Primitive[]) => void;
  backgroundImage?: string; // warped image for semi-transparent overlay
  onUpdateContour: (primitives: Primitive[]) => void;
}

export function EditorPanel({
  maskUrl,
  onMaskUpdate,
  simplifiedPrimitives,
  setSimplifiedPrimitives,
  backgroundImage,
  onUpdateContour,
}: EditorPanelProps) {
  const maskEditorRef = useRef<{ handleSimplify: () => Promise<void> }>(null);

  if (!maskUrl || !onMaskUpdate) {
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
            需要先在「轮廓提取」步骤中生成工具蒙版
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 mb-3">
        <span className="w-7 h-7 rounded-lg bg-brand-600/20 text-brand-300 flex items-center justify-center">
          <Icon name="pencil" size={15} />
        </span>
        <h2 className="text-sm font-semibold text-zinc-100">蒙版编辑</h2>
        <span className="text-[11px] text-zinc-500 ml-auto">
          {simplifiedPrimitives.length} 个基元
        </span>
      </div>
      <p className="text-xs text-zinc-500 mb-3 leading-relaxed">
        半透明背景为实物图，白色区域为工具蒙版。用画笔扩展蒙版，橡皮擦缩减蒙版。
      </p>
      <div className="flex-1 min-h-0">
        <MaskEditor
          ref={maskEditorRef}
          maskImage={maskUrl}
          onMaskUpdate={onMaskUpdate}
          onSimplifyComplete={(result) => {
            if (result.success && result.primitives) {
              setSimplifiedPrimitives(result.primitives);
            }
          }}
          onUpdateContour={(result) => {
            if (result.success && result.primitives) {
              onUpdateContour(result.primitives);
            }
          }}
          backgroundImage={backgroundImage}
        />
      </div>
    </div>
  );
}
