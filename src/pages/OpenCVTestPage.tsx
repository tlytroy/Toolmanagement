import { useState } from "react";
import { testOpenCVImport } from "@/utils/opencvDebugTest";
import { PaperDetector } from "@/utils/PaperDetector";

export function OpenCVTestPage() {
  const [testResult, setTestResult] = useState<string>("");
  const [isTesting, setIsTesting] = useState(false);

  const runOpenCVTest = async () => {
    setIsTesting(true);
    setTestResult("测试中...");

    try {
      const result = await testOpenCVImport();
      setTestResult(`OpenCV.js 测试${result ? "成功" : "失败"}`);
    } catch (error) {
      setTestResult(`测试出错: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setIsTesting(false);
    }
  };

  const runPaperDetectorTest = async () => {
    setIsTesting(true);
    setTestResult("纸张检测器测试中...");

    try {
      const detector = new PaperDetector();
      // 这里只是测试初始化，不进行实际检测
      console.log('PaperDetector created:', detector);
      setTestResult("纸张检测器创建成功");
    } catch (error) {
      setTestResult(`纸张检测器测试出错: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setIsTesting(false);
    }
  };

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-6">OpenCV.js 测试页面</h1>

      <div className="space-y-4">
        <div className="p-4 bg-gray-100 rounded">
          <h2 className="text-lg font-semibold mb-2">测试说明</h2>
          <p className="text-sm text-gray-600">
            这个页面用于测试OpenCV.js是否正确集成到项目中。
          </p>
        </div>

        <div className="flex gap-4">
          <button
            onClick={runOpenCVTest}
            disabled={isTesting}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:bg-gray-400"
          >
            {isTesting ? "测试中..." : "测试 OpenCV.js"}
          </button>

          <button
            onClick={runPaperDetectorTest}
            disabled={isTesting}
            className="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600 disabled:bg-gray-400"
          >
            {isTesting ? "测试中..." : "测试 PaperDetector"}
          </button>
        </div>

        {testResult && (
          <div className="p-4 bg-white border rounded">
            <h3 className="font-semibold mb-2">测试结果:</h3>
            <p className={testResult.includes("成功") ? "text-green-600" : "text-red-600"}>
              {testResult}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}