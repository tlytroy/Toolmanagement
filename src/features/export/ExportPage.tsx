import { useStore } from "@/app/store";

export function ExportPage() {
  const setStep = useStore((s) => s.setStep);

  // 模拟导出功能
  const handleExport = (format: string) => {
    alert(`导出为 ${format} 格式（模拟）`);
    // 实际实现中这里会生成相应的文件格式
  };

  return (
    <div className="p-8">
      <h2 className="text-xl mb-4">导出文件</h2>

      <div className="mb-6 p-4 bg-gray-100 rounded">
        <h3 className="font-bold mb-2">3D 预览</h3>
        <div className="h-64 bg-gray-200 rounded flex items-center justify-center">
          <p>3D 模型预览占位符（将使用 Three.js 实现）</p>
        </div>
      </div>

      <div className="mb-6 p-4 bg-gray-100 rounded">
        <h3 className="font-bold mb-2">导出选项</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="border p-4 rounded">
            <h4 className="font-bold mb-2">3D 打印格式</h4>
            <div className="space-y-2">
              <button
                onClick={() => handleExport("STL")}
                className="w-full px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
              >
                STL 格式
              </button>
              <button
                onClick={() => handleExport("3MF")}
                className="w-full px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600"
              >
                3MF 格式
              </button>
            </div>
          </div>

          <div className="border p-4 rounded">
            <h4 className="font-bold mb-2">CAD 格式</h4>
            <div className="space-y-2">
              <button
                onClick={() => handleExport("STEP")}
                className="w-full px-4 py-2 bg-purple-500 text-white rounded hover:bg-purple-600"
              >
                STEP 格式
              </button>
              <button
                onClick={() => handleExport("DXF")}
                className="w-full px-4 py-2 bg-yellow-500 text-white rounded hover:bg-yellow-600"
              >
                DXF 格式
              </button>
            </div>
          </div>

          <div className="border p-4 rounded md:col-span-2">
            <h4 className="font-bold mb-2">2D 矢量格式</h4>
            <div className="space-y-2">
              <button
                onClick={() => handleExport("SVG")}
                className="w-full px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600"
              >
                SVG 格式
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="flex justify-between">
        <button
          onClick={() => setStep("params")}
          className="px-4 py-2 bg-gray-300 rounded hover:bg-gray-400"
        >
          上一步
        </button>

        <button
          onClick={() => setStep("upload")}
          className="px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600"
        >
          重新开始
        </button>
      </div>
    </div>
  );
}