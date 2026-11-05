import { Icon } from "@/components/ui/icons";
import { useStore, type CADMode } from "@/app/store";

export function ParamsPanel() {
  const { cadParams, setCADParams, isGenerating } = useStore();
  const p = cadParams;

  const onModeChange = (mode: CADMode) => {
    setCADParams({ mode });
  };

  const onGenerate = async () => {
    const { generateCAD: apiGenerate, generateSTEP: apiGenerateStep, autoFingerSlots: apiAutoSlots } = await import("@/api/toolProcessor");
    const { primitives, setCADResult, setIsGenerating } = useStore.getState();

    setIsGenerating(true);
    setCADResult({ stl_base64: null, step_base64: null, summary: null });

    try {
      // 如果手指槽被禁用，传入空列表；否则根据 auto/manual 模式决定
      let slots: typeof p.finger_slots = [];
      if (p.finger_slot_enabled) {
        if (p.finger_slot_auto) {
          const autoResult = await apiAutoSlots({
            mode: p.mode,
            foam: {
              length_mm: p.length_mm,
              width_mm: p.width_mm,
            },
            gridfinity: {
              units_x: p.units_x,
              units_y: p.units_y,
            },
            primitives,
            tool_offset: p.tool_offset,
            slot_width: p.finger_slot_width,
            slot_depth: p.finger_slot_depth,
            slot_length: p.finger_slot_length,
          });

          if (autoResult.success && autoResult.finger_slots && autoResult.finger_slots.length > 0) {
            // 给后端返回的槽位添加唯一 ID
            let idCounter = 0;
            slots = autoResult.finger_slots.map((s) => ({
              id: `auto_slot_${++idCounter}`,
              x: s.x,
              y: s.y,
              length: s.length,
              width: s.width,
              depth: s.depth,
              rotation: s.rotation,
            }));
          }
        } else {
          // 手动模式：使用用户绘制的槽位
          slots = p.finger_slots;
        }
      }

      const paramsWithSlots = { ...p, finger_slots: slots };

      // 并行生成 STL 和 STEP
      const [stlResult, stepResult] = await Promise.all([
        apiGenerate(paramsWithSlots, primitives),
        apiGenerateStep(paramsWithSlots, primitives),
      ]);

      setCADResult({
        stl_base64: stlResult.stl_base64 ?? null,
        step_base64: stepResult.step_base64 ?? null,
        // 使用 STL 的结果摘要（两者相同）
        summary: stlResult.summary ?? null,
      });
    } catch (error) {
      console.error("生成 3D 模型失败:", error);
    } finally {
      setIsGenerating(false);
    }
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

          {/* 堆叠功能 */}
          <div className="pt-2 border-t border-canvas-700">
            <label className="flex items-center gap-2 text-xs text-zinc-300 cursor-pointer group">
              <input
                type="checkbox"
                checked={p.stackable}
                onChange={(e) => setCADParams({ stackable: e.target.checked })}
                className="rounded border-zinc-600 bg-canvas-800 text-brand-500 focus:ring-brand-500/30"
              />
              <span className={`font-medium transition-colors ${p.stackable ? "text-brand-300" : "text-zinc-400"}`}>
                启用堆叠槽位
              </span>
              <span className="text-[10px] text-zinc-600 ml-auto">Lip & Groove</span>
            </label>
            {p.stackable && (
              <p className="text-[10px] text-zinc-500 mt-1 ml-5 leading-relaxed">
                底部唇边 (3mm×2mm) + 顶部凹槽，多个嵌件可上下堆叠
              </p>
            )}
          </div>
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

      {/* 手指槽参数 — 折叠面板 */}
      <div className="mb-4 pt-2 border-t border-canvas-700">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-[11px] font-semibold text-zinc-300 uppercase tracking-wider">
            手指槽
          </span>
          <span className="text-[10px] text-zinc-600">Finger Groove</span>
        </div>

        {/* 启用/禁用手指槽主开关 */}
        <label className="flex items-center gap-2 text-xs text-zinc-300 cursor-pointer group mb-2">
          <input
            type="checkbox"
            checked={p.finger_slot_enabled}
            onChange={(e) => setCADParams({ finger_slot_enabled: e.target.checked })}
            className="rounded border-zinc-600 bg-canvas-800 text-brand-500 focus:ring-brand-500/30"
          />
          <span className={`font-medium transition-colors ${p.finger_slot_enabled ? "text-brand-300" : "text-zinc-400"}`}>
            启用手指槽
          </span>
          <span className="text-[10px] text-zinc-600 ml-auto">Finger Slot</span>
        </label>

        {p.finger_slot_enabled && (
          <>
            {/* 自动生成开关 */}
            <label className="flex items-center gap-2 text-xs text-zinc-300 cursor-pointer group mb-2 ml-5">
              <input
                type="checkbox"
                checked={p.finger_slot_auto}
                onChange={(e) => setCADParams({ finger_slot_auto: e.target.checked })}
                className="rounded border-zinc-600 bg-canvas-800 text-brand-500 focus:ring-brand-500/30"
              />
              <span className={`font-medium transition-colors ${p.finger_slot_auto ? "text-brand-300" : "text-zinc-400"}`}>
                自动生成
              </span>
              <span className="text-[10px] text-zinc-600 ml-auto">半胶囊形</span>
            </label>

            {p.finger_slot_auto && (
              <p className="text-[10px] text-zinc-500 mb-2.5 ml-5 leading-relaxed">
                沿工具轮廓长轴两端自动放置半胶囊形手指槽，方便手指伸入拿取工具
              </p>
            )}

            {/* 手指槽尺寸参数 */}
            <div className="space-y-2">
              <ParamRow
                label="槽位宽度 (mm)"
                value={p.finger_slot_width}
                onChange={(v) => setCADParams({ finger_slot_width: v })}
                min={6}
                max={20}
              />
              <ParamRow
                label="槽位长度 (mm)"
                value={p.finger_slot_length}
                onChange={(v) => setCADParams({ finger_slot_length: v })}
                min={10}
                max={50}
              />
              <ParamRow
                label="槽位深度 (mm)"
                value={p.finger_slot_depth}
                onChange={(v) => setCADParams({ finger_slot_depth: v })}
                min={3}
                max={30}
              />
            </div>

            {!p.finger_slot_auto && p.finger_slots.length === 0 && (
              <p className="text-[10px] text-zinc-600 italic mt-1">
                关闭自动生成后，可在视口中用 <span className="text-amber-400">铅笔工具</span> 划线定义手指槽位置
              </p>
            )}

            {!p.finger_slot_auto && p.finger_slots.length > 0 && (
              <div className="mt-2 space-y-1.5">
                <p className="text-[10px] text-zinc-500 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-brand-400" />
                  已定义 {p.finger_slots.length} 个手指槽：
                </p>
                {p.finger_slots.map((slot) => (
                  <div
                    key={slot.id}
                    className="flex items-center gap-1.5 text-[10px] text-zinc-400 bg-canvas-800 rounded-lg px-2 py-1.5"
                  >
                    <Icon name="pencil" size={12} />
                    <span>({slot.x.toFixed(0)}, {slot.y.toFixed(0)})</span>
                    <span className="text-zinc-600">{slot.length.toFixed(0)}mm × {slot.width.toFixed(0)}mm</span>
                    <span className="text-zinc-600">{slot.rotation.toFixed(0)}°</span>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
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
