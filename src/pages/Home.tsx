import { useStore } from "@/app/store";
import { Stepper } from "@/components/Stepper";
import { UploadPage } from "@/features/upload/UploadPage";
import { CanvasEditor } from "@/components/CanvasEditor";
import { ParamsPanel } from "@/features/params/ParamsPanel";

export function Home() {
  const step = useStore((s) => s.step);
  const imageUrl = useStore((s) => s.imageUrl);

  return (
    <div className="h-screen flex flex-col">
      <Stepper />

      <div className="flex flex-1 overflow-hidden">
        <div className="flex-1 overflow-auto">
          {!imageUrl && <UploadPage />}
          {imageUrl && <CanvasEditor />}
        </div>

        {imageUrl && <ParamsPanel />}
      </div>
    </div>
  );
}