import { Icon } from "@/components/ui/icons";
import { useStore, type CADMode } from "@/app/store";

export function ParamsPanel() {
  const { cadParams, setCADParams, isGenerating } = useStore();
  const p = cadParams;

  const onModeChange = (mode: CADMode) => {
    setCADParams({ mode });
  };

  const onGenerate = async () => {
    const { generateCAD: apiGenerate } = await import("@/api/toolProcessor");
    const { primitives, setCADResult, setIsGenerating } = useStore.getState();
    setIsGenerating(true);
    setCADResult({ stl_base64: null, summary: null });
    const result = await apiGenerate(p, primitives);
    setCADResult({
      stl_base64: result.stl_base64 ?? null,
      summary: result.summary ?? null,
    });
    setIsGenerating(false);
  };

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <span className="w-7 h-7 rounded-lg bg-brand-600/20 text-brand-300 flex items-center justify-center">
          <Icon name="sliders" size={15} />
        </span>
        <h2 className="text-sm font-semibold text-zinc-100">参数配置</h2>
      </div>

      {/* 模式选择 */}
      <div className="mb-3">
        <label className="text-[11px] font-medium text-zinc-400 mb-1.5 block">
          基底模式
        </label>
        <div className="flex gap-2">
          <button
            onClick={() => onModeChange("foam")}
            className={`flex-1 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
              p.mode === "foam"
                ? "bg-brand-600/30 text-brand-300 border border-brand-500/40"
                : "bg-canvas-800 text-zinc-400 border border-canvas-700 hover:border-zinc-600"
            }`}
          >
            <Icon name="box" size={14} className="inline mr-1" />
            Foam
          </button>
          <button
            onClick={() => onModeChange("gridfinity")}
            className={`flex-1 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
              p.mode === "gridfinity"
                ? "bg-brand-600/30 text-brand-300 border border-brand-500/40"
                : "bg-canvas-800 text-zinc-400 border border-canvas-700 hover:border-zinc-600"
            }`}
          >
            <Icon name="grid" size={14} className="inline mr-1" />
            Gridfinity
          </button>
        </div>
      </div>

      {/* Foam 参数 */}
      {p.mode === "foam" && (
        <div className="space-y-2.5 mb-3">
          <ParamRow label="长度 (mm)" value={p.length_mm} onChange={(v) => setCADParams({ length_mm: v })} min={20} max={500} />
          <ParamRow label="宽度 (mm)" value={p.width_mm} onChange={(v) => setCADParams({ width_mm: v })} min={20} max={500} />
          <ParamRow label="高度 (mm)" value={p.height_mm} onChange={(v) => setCADParams({ height_mm: v })} min={5} max={200} />
          <ParamRow label="圆角半径 (mm)" value={p.fillet_radius} onChange={(v) => setCADParams({ fillet_radius: v })} min={0} max={50} />
        </div>
      )}

      {/* Gridfinity 参数 */}
      {p.mode === "gridfinity" && (
        <div className="space-y-2.5 mb-3">
          <ParamRow label="网格 X" value={p.units_x} onChange={(v) => setCADParams({ units_x: v })} min={1} max={10} step={1} />
          <ParamRow label="网格 Y" value={p.units_y} onChange={(v) => setCADParams({ units_y: v })} min={1} max={10} step={1} />
          <ParamRow label="高度 (U)" value={p.height_u} onChange={(v) => setCADParams({ height_u: v })} min={1} max={10} />
          <label className="flex items-center gap-2 text-xs text-zinc-300">
            <input
              type="checkbox"
              checked={p.has_magnet_holes}
              onChange={(e) => setCADParams({ has_magnet_holes: e.target.checked })}
              className="rounded border-zinc-600 bg-canvas-800 text-brand-500 focus:ring-brand-500/30"
            />
            磁吸孔
          </label>
        </div>
      )}

      {/* 通用参数 */}
      <div className="space-y-2.5 mb-4">
        <ParamRow label="嵌入深度 (mm)" value={p.embed_depth} onChange={(v) => setCADParams({ embed_depth: v })} min={1} max={50} />
        <ParamRow label="轮廓偏移 (mm)" value={p.tool_offset} onChange={(v) => setCADParams({ tool_offset: v })} min={-5} max={10} />
      </div>

      {/* 生成按钮 */}
      <button
        onClick={onGenerate}
        disabled={isGenerating}
        className="w-full py-2.5 rounded-xl text-sm font-semibold transition-all bg-brand-600 hover:bg-brand-500 text-white disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
      >
        {isGenerating ? (
          <>
            <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            生成中...
          </>
        ) : (
          <>
            <Icon name="box" size={16} />
            生成 3D 模型
          </>
        )}
      </button>
    </div>
  );
}

function ParamRow({
  label,
  value,
  onChange,
  min,
  max,
  step,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min: number;
  max: number;
  step?: number;
}) {
  return (
    <div className="flex items-center gap-2">
      <label className="text-[11px] font-medium text-zinc-400 w-24 flex-shrink-0">
        {label}
      </label>
      <input
        type="range"
        min={min}
        max={max}
        step={step ?? 0.5}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="flex-1 h-1.5 rounded-full appearance-none bg-canvas-700 accent-brand-500 cursor-pointer"
      />
      <span className="text-xs text-zinc-300 w-12 text-right tabular-nums">
        {Number.isInteger(value) ? value : value.toFixed(1)}
      </span>
    </div>
  );
}