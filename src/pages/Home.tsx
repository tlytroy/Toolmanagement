import { useStore } from "@/app/store";
import { Stepper } from "@/components/Stepper";
import { UploadPage } from "@/features/upload/UploadPage";
import { CanvasEditor } from "@/components/CanvasEditor";
import { ParamsPanel } from "@/features/params/ParamsPanel";
import { CalibrationPage } from "@/features/calibration/CalibrationPage";
import { SegmentationPage } from "@/features/segmentation/SegmentationPage";
import { ExportPage } from "@/features/export/ExportPage";

export function Home() {
  const step = useStore((s) => s.step);
  const imageUrl = useStore((s) => s.imageUrl);

  const renderStep = () => {
    switch (step) {
      case "upload":
        return <UploadPage />;
      case "calibration":
        return <CalibrationPage />;
      case "segmentation":
        return <SegmentationPage />;
      case "editor":
        return <CanvasEditor />;
      case "params":
        return (
          <div className="flex flex-1 overflow-hidden">
            <div className="flex-1 overflow-auto">
              <div className="p-8">
                <h2 className="text-xl mb-4">轮廓编辑</h2>
                <CanvasEditor />
              </div>
            </div>
            <ParamsPanel />
          </div>
        );
      case "export":
        return <ExportPage />;
      default:
        return <UploadPage />;
    }
  };

  return (
    <div className="h-screen flex flex-col">
      <Stepper />

      <div className="flex flex-1 overflow-hidden">
        {renderStep()}
      </div>
    </div>
  );
}