export function ParamsPanel() {
  return (
    <div className="p-4 w-64 border-l">
      <h3 className="font-bold mb-2">嵌件参数</h3>

      <label className="block mb-2">
        轮廓偏移 (mm)
        <input className="border w-full px-2" defaultValue={0.3} />
      </label>

      <label className="block mb-2">
        底板厚度 (mm)
        <input className="border w-full px-2" defaultValue={2} />
      </label>

      <label className="block mb-2">
        腔体深度 (mm)
        <input className="border w-full px-2" defaultValue={15} />
      </label>
    </div>
  );
}