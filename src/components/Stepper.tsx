import { useStore } from "@/app/store";

const steps = [
  "upload",
  "calibration",
  "segmentation",
  "editor",
  "params",
  "export",
];

export function Stepper() {
  const step = useStore((s) => s.step);
  const setStep = useStore((s) => s.setStep);

  return (
    <div className="flex gap-2 p-4 bg-gray-100">
      {steps.map((s, i) => (
        <button
          key={s}
          onClick={() => setStep(s as any)}
          className={`px-3 py-1 rounded ${
            step === s ? "bg-blue-600 text-white" : "bg-white"
          }`}
        >
          {i + 1}. {s}
        </button>
      ))}
      <button
        onClick={() => setStep("opencv-test" as any)}
        className={`px-3 py-1 rounded ${
          step === "opencv-test" ? "bg-green-600 text-white" : "bg-white"
        }`}
      >
        Test
      </button>
    </div>
  );
}