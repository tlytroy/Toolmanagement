import { Icon } from "@/components/ui/icons";
import { useEffect, useRef, useState, useCallback } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { STLLoader } from "three/addons/loaders/STLLoader.js";
import { useStore, type FingerSlot } from "@/app/store";

interface ViewportProps {
  imgUrl?: string;
  warpedUrl?: string;
  maskUrl?: string;
  showGrid: boolean;
  zoom: number;
  onFile: (file: File | undefined) => void;
  hasImage: boolean;
  stage: 0 | 1 | 2;
  detecting: boolean;
  extracting: boolean;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onFit: () => void;
  onToggleGrid: () => void;
  step?: string;
  primitives?: any[];
}

function ViewportToolBtn({
  icon,
  title,
  active,
  onClick,
}: {
  icon: any;
  title: string;
  active?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      title={title}
      onClick={onClick}
      className={`w-8 h-8 rounded-lg flex items-center justify-center transition-colors ${
        active
          ? "bg-white/10 text-zinc-100"
          : "text-zinc-400 hover:text-zinc-200 hover:bg-white/5"
      }`}
    >
      <Icon name={icon} size={16} />
    </button>
  );
}

function CADPreview({ stlBase64 }: { stlBase64: string }) {
  const mountRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!mountRef.current) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x1a1a2e);

    const container = mountRef.current;
    const w = container.clientWidth;
    const h = container.clientHeight;
    const camera = new THREE.PerspectiveCamera(35, w / h, 0.1, 1000);
    camera.position.set(80, 60, 120);
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(w, h);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.1;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 2;
    controls.target.set(0, 0, 0);

    const ambient = new THREE.AmbientLight(0xffffff, 0.4);
    scene.add(ambient);

    const dirLight = new THREE.DirectionalLight(0xffffff, 1.2);
    dirLight.position.set(50, 100, 50);
    scene.add(dirLight);

    const fillLight = new THREE.DirectionalLight(0x8888ff, 0.5);
    fillLight.position.set(-50, 20, -50);
    scene.add(fillLight);

    const gridHelper = new THREE.GridHelper(200, 20, 0x444466, 0x333355);
    scene.add(gridHelper);

    const loader = new STLLoader();
    const byteString = atob(stlBase64);
    const bytes = new Uint8Array(byteString.length);
    for (let i = 0; i < byteString.length; i++) {
      bytes[i] = byteString.charCodeAt(i);
    }
    const geometry = loader.parse(bytes.buffer);

    // Auto-center
    geometry.computeBoundingBox();
    const box = geometry.boundingBox!;
    const cx = (box.max.x + box.min.x) / 2;
    const cy = (box.max.y + box.min.y) / 2;
    const cz = (box.max.z + box.min.z) / 2;
    geometry.translate(-cx, -cy, -cz);

    // Scale to fit viewport (~60 units max dimension)
    const size = new THREE.Vector3();
    box.getSize(size);
    const maxDim = Math.max(size.x, size.y, size.z);
    const scale = maxDim > 0 ? 60 / maxDim : 1;
    geometry.scale(scale, scale, scale);

    const material = new THREE.MeshPhysicalMaterial({
      color: 0x4a9eff,
      metalness: 0.1,
      roughness: 0.4,
      clearcoat: 0.1,
    });
    const mesh = new THREE.Mesh(geometry, material);

    // Place on grid plane
    geometry.computeBoundingBox();
    const bb = geometry.boundingBox!;
    const minY = bb.min.y;
    mesh.position.y = -minY;
    scene.add(mesh);

    // Wireframe edges
    const edges = new THREE.EdgesGeometry(geometry);
    const edgeMat = new THREE.LineBasicMaterial({ color: 0x88ccff, transparent: true, opacity: 0.25 });
    const wireframe = new THREE.LineSegments(edges, edgeMat);
    wireframe.position.y = -minY;
    scene.add(wireframe);

    let animId: number;
    const animate = () => {
      animId = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    const onResize = () => {
      const w2 = container.clientWidth;
      const h2 = container.clientHeight;
      camera.aspect = w2 / h2;
      camera.updateProjectionMatrix();
      renderer.setSize(w2, h2);
    };
    window.addEventListener("resize", onResize);

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener("resize", onResize);
      controls.dispose();
      renderer.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, [stlBase64]);

  return (
    <div
      ref={mountRef}
      className="w-full h-full rounded-xl overflow-hidden"
      style={{ minHeight: "400px" }}
    />
  );
}

/**
 * Draw finger slot overlays on a temporary canvas that sits on top of the image.
 */
function FingerSlotOverlay({
  slots,
  imageRect,
  foamWidth,
  foamHeight,
  imageWidth,
  imageHeight,
}: {
  slots: FingerSlot[];
  imageRect: { x: number; y: number; width: number; height: number } | null;
  foamWidth: number;
  foamHeight: number;
  imageWidth: number;
  imageHeight: number;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !imageRect || slots.length === 0) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Match the parent image's displayed size
    canvas.style.width = `${imageRect.width}px`;
    canvas.style.height = `${imageRect.height}px`;
    canvas.width = imageWidth;
    canvas.height = imageHeight;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Scale from mm to pixel coordinates
    // The foam block maps to the image dimensions
    const scaleX = imageWidth / foamWidth;
    const scaleY = imageHeight / foamHeight;

    slots.forEach((slot) => {
      const cx = slot.x * scaleX + imageWidth / 2;
      const cy = slot.y * scaleY + imageHeight / 2;
      const halfLen = (slot.length / 2) * scaleX;
      const halfWid = (slot.width / 2) * scaleX;
      const angleRad = (slot.rotation * Math.PI) / 180;

      // Draw the slot as a filled capsule shape
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(angleRad);

      // Capsule body (rectangle with rounded ends)
      ctx.beginPath();
      ctx.moveTo(-halfLen, -halfWid);
      ctx.lineTo(halfLen, -halfWid);
      ctx.arc(halfLen, 0, halfWid, -Math.PI / 2, Math.PI / 2);
      ctx.lineTo(-halfLen, halfWid);
      ctx.arc(-halfLen, 0, halfWid, Math.PI / 2, -Math.PI / 2);
      ctx.closePath();

      // Fill with semi-transparent color
      ctx.fillStyle = "rgba(59, 130, 246, 0.25)";
      ctx.fill();
      ctx.strokeStyle = "#3b82f6";
      ctx.lineWidth = 2;
      ctx.stroke();

      // Center line
      ctx.beginPath();
      ctx.moveTo(-halfLen, 0);
      ctx.lineTo(halfLen, 0);
      ctx.strokeStyle = "#60a5fa";
      ctx.lineWidth = 1.5;
      ctx.setLineDash([4, 4]);
      ctx.stroke();
      ctx.setLineDash([]);

      ctx.restore();
    });
  }, [slots, imageRect, foamWidth, foamHeight, imageWidth, imageHeight]);

  if (slots.length === 0) return null;

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 max-w-full max-h-[78vh] rounded-xl pointer-events-none"
      style={{ display: "block" }}
    />
  );
}

export function Viewport({
  imgUrl,
  warpedUrl,
  maskUrl,
  showGrid,
  zoom,
  onFile,
  hasImage,
  stage,
  detecting,
  extracting,
  onZoomIn,
  onZoomOut,
  onFit,
  onToggleGrid,
  step,
  primitives,
}: ViewportProps) {
  const { cadResult, cadParams, setFingerSlots } = useStore();
  const [drawingMode, setDrawingMode] = useState(false);
  const [drawStart, setDrawStart] = useState<{ x: number; y: number } | null>(null);
  const [drawEnd, setDrawEnd] = useState<{ x: number; y: number } | null>(null);
  const [imageRect, setImageRect] = useState<{ x: number; y: number; width: number; height: number } | null>(null);

  const isParamsMode = step === "params";
  const isManualSlotMode = isParamsMode && cadParams.finger_slot_enabled && !cadParams.finger_slot_auto;

  // Track the displayed image's bounding rect for coordinate mapping
  const imgRef = useRef<HTMLImageElement | null>(null);
  const updateImageRect = useCallback(() => {
    const img = isParamsMode
      ? document.querySelector<HTMLImageElement>('#params-img')
      : document.querySelector<HTMLImageElement>('#editor-warp-img');
    if (img) {
      imgRef.current = img;
      const rect = img.getBoundingClientRect();
      setImageRect({
        x: rect.left,
        y: rect.top,
        width: rect.width,
        height: rect.height,
      });
    }
  }, [isParamsMode]);

  useEffect(() => {
    updateImageRect();
    const onResize = () => updateImageRect();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [updateImageRect, warpedUrl, imgUrl, step]);

  // Draw contour overlay on editor canvas
  useEffect(() => {
    if (step !== "editor" || !primitives || primitives.length === 0) return;

    const canvas = document.getElementById('editor-contour-canvas') as HTMLCanvasElement;
    const warpImg = document.getElementById('editor-warp-img') as HTMLImageElement;
    if (!canvas || !warpImg) return;

    const setupAndDraw = () => {
      if (!warpImg.naturalWidth) {
        setTimeout(setupAndDraw, 50);
        return;
      }
      canvas.width = warpImg.naturalWidth;
      canvas.height = warpImg.naturalHeight;
      canvas.style.width = warpImg.clientWidth + 'px';
      canvas.style.height = warpImg.clientHeight + 'px';

      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      ctx.strokeStyle = '#ef4444';
      ctx.lineWidth = 2.5;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.shadowColor = 'rgba(239, 68, 68, 0.5)';
      ctx.shadowBlur = 3;

      const toPt = (v: any) =>
        Array.isArray(v) ? { x: v[0], y: v[1] } : v;

      primitives.forEach((primitive: any) => {
        if (primitive.type === 'line') {
          const p0 = toPt(primitive.p0);
          const p1 = toPt(primitive.p1);
          if (p0 && p1) {
            ctx.beginPath();
            ctx.moveTo(p0.x, p0.y);
            ctx.lineTo(p1.x, p1.y);
            ctx.stroke();
          }
        } else if (primitive.type === 'arc') {
          const c = toPt(primitive.center);
          const arcPts = primitive.points || primitive.seg_pts;
          if (c && primitive.radius && arcPts && arcPts.length > 0) {
            const seg = arcPts;
            const angles = seg.map((pt: any) => {
              const x = typeof pt.x === 'number' ? pt.x : pt[0];
              const y = typeof pt.y === 'number' ? pt.y : pt[1];
              return Math.atan2(y - c.y, x - c.x);
            });
            for (let i = 1; i < angles.length; i++) {
              while (angles[i] - angles[i - 1] > Math.PI) angles[i] -= 2 * Math.PI;
              while (angles[i] - angles[i - 1] < -Math.PI) angles[i] += 2 * Math.PI;
            }
            const a0 = angles[0];
            const a1 = angles[angles.length - 1];
            const counterclockwise = a1 > a0;
            ctx.beginPath();
            ctx.arc(c.x, c.y, primitive.radius, a0, a1, counterclockwise);
            ctx.stroke();
          }
        } else if (primitive.type === 'polyline' && primitive.points) {
          const pts = primitive.points.map(toPt);
          if (pts.length > 1) {
            ctx.beginPath();
            ctx.moveTo(pts[0].x, pts[0].y);
            for (let i = 1; i < pts.length; i++) {
              ctx.lineTo(pts[i].x, pts[i].y);
            }
            ctx.stroke();
          }
        }
      });

      ctx.shadowBlur = 0;
    };

    requestAnimationFrame(setupAndDraw);
  }, [primitives, step, warpedUrl]);

  // ── Finger slot drawing handlers ──
  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (!isManualSlotMode || !drawingMode || !imgRef.current || !imageRect) return;

      const rect = imgRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      // Convert to image pixel coordinates
      const imgX = (x / rect.width) * imgRef.current.naturalWidth;
      const imgY = (y / rect.height) * imgRef.current.naturalHeight;

      setDrawStart({ x: imgX, y: imgY });
      setDrawEnd(null);
    },
    [isManualSlotMode, drawingMode, imageRect]
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!drawStart || !drawingMode || !imgRef.current) return;

      const rect = imgRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const imgX = (x / rect.width) * imgRef.current.naturalWidth;
      const imgY = (y / rect.height) * imgRef.current.naturalHeight;

      setDrawEnd({ x: imgX, y: imgY });
    },
    [drawStart, drawingMode]
  );

  const handleMouseUp = useCallback(
    (e: React.MouseEvent) => {
      if (!drawStart || !drawingMode || !imgRef.current) return;

      const rect = imgRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const imgX = (x / rect.width) * imgRef.current.naturalWidth;
      const imgY = (y / rect.height) * imgRef.current.naturalHeight;

      // Calculate line vector
      const dx = imgX - drawStart.x;
      const dy = imgY - drawStart.y;
      const dist = Math.sqrt(dx * dx + dy * dy);

      // Only create slot if line is long enough (min 20px)
      if (dist >= 20) {
        // Convert image coords to mm (relative to foam center)
        const foamW = cadParams.mode === "foam" ? cadParams.length_mm : cadParams.units_x * 42;
        const foamH = cadParams.mode === "foam" ? cadParams.width_mm : cadParams.units_y * 42;
        const scaleX = foamW / imgRef.current.naturalWidth;
        const scaleY = foamH / imgRef.current.naturalHeight;

        const midX = (drawStart.x + imgX) / 2;
        const midY = (drawStart.y + imgY) / 2;

        // Center of image → center of foam
        const mmX = (midX - imgRef.current.naturalWidth / 2) * scaleX;
        const mmY = (midY - imgRef.current.naturalHeight / 2) * scaleY;

        // Length and rotation
        const lenMm = dist * scaleX;
        const angleDeg = (Math.atan2(dy, dx) * 180) / Math.PI;

        const newSlot: FingerSlot = {
          id: `drawn_slot_${Date.now()}`,
          x: mmX,
          y: mmY,
          length: Math.round(lenMm * 10) / 10,
          width: cadParams.finger_slot_width,
          depth: cadParams.finger_slot_depth,
          rotation: angleDeg,
        };

        setFingerSlots([...cadParams.finger_slots, newSlot]);
      }

      setDrawStart(null);
      setDrawEnd(null);
    },
    [drawStart, drawingMode, cadParams, setFingerSlots]
  );

  // Draw the in-progress line on a temporary canvas
  const drawLineCanvasRef = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = drawLineCanvasRef.current;
    if (!canvas || !imgRef.current) return;

    const img = imgRef.current;
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    canvas.style.width = img.clientWidth + "px";
    canvas.style.height = img.clientHeight + "px";

    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (drawStart && drawEnd) {
      ctx.beginPath();
      ctx.moveTo(drawStart.x, drawStart.y);
      ctx.lineTo(drawEnd.x, drawEnd.y);
      ctx.strokeStyle = "#f59e0b";
      ctx.lineWidth = 3;
      ctx.lineCap = "round";
      ctx.setLineDash([8, 4]);
      ctx.stroke();
      ctx.setLineDash([]);

      // Draw endpoints
      ctx.fillStyle = "#f59e0b";
      ctx.beginPath();
      ctx.arc(drawStart.x, drawStart.y, 5, 0, Math.PI * 2);
      ctx.fill();
      ctx.beginPath();
      ctx.arc(drawEnd.x, drawEnd.y, 5, 0, Math.PI * 2);
      ctx.fill();
    }
  }, [drawStart, drawEnd]);

  // Delete a finger slot
  const handleDeleteSlot = useCallback(
    (slotId: string) => {
      setFingerSlots(cadParams.finger_slots.filter((s) => s.id !== slotId));
    },
    [cadParams.finger_slots, setFingerSlots]
  );

  // Export mode: 3D preview
  if (step === "export" && cadResult.stl_base64) {
    return (
      <main className="relative flex-1 min-w-0 bg-canvas-950 overflow-hidden">
        <CADPreview stlBase64={cadResult.stl_base64} />
        <div className="absolute top-4 left-4 glass-bar rounded-full px-3 py-1.5 flex items-center gap-2 text-xs text-zinc-300">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
          3D 模型预览
        </div>
      </main>
    );
  }

  // Determine which image to show in params mode
  const paramsImgUrl = isParamsMode ? (warpedUrl || imgUrl) : undefined;

  return (
    <main
      className={`relative flex-1 min-w-0 canvas-scroll overflow-auto ${
        showGrid ? "canvas-grid" : "bg-canvas-950"
      }`}
    >
      {!hasImage ? (
        <label className="absolute inset-0 flex items-center justify-center cursor-pointer group">
          <div className="flex flex-col items-center gap-4 p-12 rounded-3xl border-2 border-dashed border-canvas-600 hover:border-brand-500 transition-colors duration-300 text-center">
            <span className="w-16 h-16 rounded-2xl bg-canvas-800 text-brand-400 flex items-center justify-center group-hover:bg-canvas-700 transition-colors">
              <Icon name="upload" size={30} />
            </span>
            <div>
              <p className="text-lg font-medium text-zinc-200">拖放工具照片到此处</p>
              <p className="text-sm text-zinc-500 mt-1">
                或点击选择文件 · 支持 JPG / PNG / WebP
              </p>
            </div>
          </div>
          <input
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => onFile(e.target.files?.[0])}
          />
        </label>
      ) : step === "editor" ? (
        <div className="min-h-full flex items-center justify-center p-8">
          <div
            className="relative"
            style={{
              transform: `scale(${zoom})`,
              transformOrigin: "center",
              transition: "transform 0.15s ease-out",
            }}
          >
            {warpedUrl && (
              <img
                src={warpedUrl}
                alt="工具校正图"
                className="max-w-full max-h-[78vh] rounded-xl shadow-2xl ring-1 ring-white/10"
                id="editor-warp-img"
              />
            )}
            <canvas
              id="editor-contour-canvas"
              className="absolute inset-0 max-w-full max-h-[78vh] rounded-xl pointer-events-none"
              style={{ display: 'block' }}
            />
          </div>
        </div>
      ) : isParamsMode ? (
        <div className="min-h-full flex items-center justify-center p-8">
          <div
            className="relative"
            style={{
              transform: `scale(${zoom})`,
              transformOrigin: "center",
              transition: "transform 0.15s ease-out",
            }}
          >
            {(warpedUrl || imgUrl) && (
              <img
                ref={imgRef}
                src={paramsImgUrl}
                alt="工具图"
                className="max-w-full max-h-[78vh] rounded-xl shadow-2xl ring-1 ring-white/10"
                id="params-img"
                draggable={false}
                onLoad={updateImageRect}
              />
            )}
            {/* Draw in-progress line */}
            <canvas
              ref={drawLineCanvasRef}
              className="absolute inset-0 max-w-full max-h-[78vh] rounded-xl pointer-events-none"
              style={{ display: drawStart ? "block" : "none" }}
            />
            {/* Draw existing finger slot overlays */}
            <FingerSlotOverlay
              slots={cadParams.finger_slots}
              imageRect={imageRect}
              foamWidth={cadParams.mode === "foam" ? cadParams.length_mm : cadParams.units_x * 42}
              foamHeight={cadParams.mode === "foam" ? cadParams.width_mm : cadParams.units_y * 42}
              imageWidth={imgRef.current?.naturalWidth ?? 0}
              imageHeight={imgRef.current?.naturalHeight ?? 0}
            />
            {/* Drawing mode instruction overlay */}
            {drawingMode && (
              <div className="absolute top-3 left-3 glass-bar rounded-lg px-3 py-1.5 text-xs text-amber-300 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
                在工具图上点击并拖动，画一条线定义手指槽位置
              </div>
            )}
            {/* Slot list overlay */}
            {isManualSlotMode && cadParams.finger_slots.length > 0 && (
              <div className="absolute top-3 right-3 glass-panel rounded-xl p-2 max-w-[200px] space-y-1">
                <p className="text-[10px] text-zinc-400 font-medium px-1">手指槽 ({cadParams.finger_slots.length})</p>
                {cadParams.finger_slots.map((slot) => (
                  <div
                    key={slot.id}
                    className="flex items-center gap-1.5 text-[10px] text-zinc-300 bg-canvas-800/80 rounded-lg px-2 py-1"
                  >
                    <span className="flex-1 truncate">
                      ({slot.x.toFixed(0)}, {slot.y.toFixed(0)}) {slot.length.toFixed(0)}mm
                    </span>
                    <button
                      onClick={() => handleDeleteSlot(slot.id)}
                      className="text-red-400 hover:text-red-300 transition-colors flex-shrink-0"
                      title="删除此手指槽"
                    >
                      <Icon name="alert" size={12} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="min-h-full flex items-center justify-center p-8">
          <div
            className="relative"
            style={{
              transform: `scale(${zoom})`,
              transformOrigin: "center",
              transition: "transform 0.15s ease-out",
            }}
          >
            {(warpedUrl || imgUrl) && (
              <img
                src={warpedUrl || imgUrl}
                alt="工作图"
                className="max-w-full max-h-[78vh] rounded-xl shadow-2xl ring-1 ring-white/10"
              />
            )}
            {maskUrl && (
              <img
                src={maskUrl}
                alt="工具蒙版"
                className="absolute inset-0 max-w-full max-h-[78vh] rounded-xl opacity-70 mix-blend-overlay"
                style={{
                  filter: 'contrast(1.2) brightness(1.1)',
                  mixBlendMode: 'multiply'
                }}
              />
            )}
          </div>
        </div>
      )}

      {hasImage && (
        <div className="absolute top-4 left-4 glass-bar rounded-full px-3 py-1.5 flex items-center gap-2 text-xs text-zinc-300">
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              stage === 2
                ? "bg-emerald-400"
                : stage === 1
                  ? "bg-amber-400"
                  : "bg-brand-400"
            }`}
          />
          {isParamsMode
            ? "参数配置"
            : stage === 0
              ? "已导入照片"
              : stage === 1
                ? "已识别纸张 · 待校正"
                : isManualSlotMode
                  ? "轮廓已提取 · 划线定义手指槽"
                  : "轮廓已提取"}
          {(detecting || extracting) && (
            <Icon name="loader" size={13} className="animate-spin text-brand-300" />
          )}
        </div>
      )}

      {hasImage && (
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 glass-bar rounded-full px-2 py-1.5 flex items-center gap-1 text-zinc-300">
          {isManualSlotMode ? (
            <>
              <ViewportToolBtn
                icon="pencil"
                title="划线定义手指槽"
                active={drawingMode}
                onClick={() => {
                  setDrawingMode(!drawingMode);
                  setDrawStart(null);
                  setDrawEnd(null);
                }}
              />
              <ViewportToolBtn
                icon="pointer"
                title="选择/查看"
                active={!drawingMode}
                onClick={() => {
                  setDrawingMode(false);
                  setDrawStart(null);
                  setDrawEnd(null);
                }}
              />
              <div className="w-px h-5 bg-canvas-600 mx-1" />
              {cadParams.finger_slots.length > 0 && (
                <button
                  onClick={() => setFingerSlots([])}
                  className="px-2 py-1 text-[10px] text-red-400 hover:text-red-300 hover:bg-white/5 rounded-lg transition-colors"
                  title="清除所有手指槽"
                >
                  清除
                </button>
              )}
              <div className="w-px h-5 bg-canvas-600 mx-1" />
            </>
          ) : !isParamsMode && (
            <>
              <ViewportToolBtn icon="pointer" active title="选择" />
              <ViewportToolBtn icon="image" title="平移" />
              <div className="w-px h-5 bg-canvas-600 mx-1" />
            </>
          )}
          <ViewportToolBtn icon="zoomOut" title="缩小" onClick={onZoomOut} />
          <span className="text-xs tabular-nums w-10 text-center">{Math.round(zoom * 100)}%</span>
          <ViewportToolBtn icon="zoomIn" title="放大" onClick={onZoomIn} />
          <ViewportToolBtn icon="maximize" title="适应窗口" onClick={onFit} />
          <div className="w-px h-5 bg-canvas-600 mx-1" />
          <ViewportToolBtn icon="grid" title="网格" active={showGrid} onClick={onToggleGrid} />
        </div>
      )}

      {hasImage && step !== "export" && step !== "params" && (
        <div className="absolute bottom-4 left-4 glass-bar rounded-xl px-3 py-2 flex items-center gap-2 text-xs">
          <Icon name="box" size={15} className="text-zinc-400" />
          <div className="leading-tight">
            <p className="text-zinc-300 font-medium">3D 预览区</p>
            <p className="text-zinc-500 text-[11px]">生成模型后在此预览</p>
          </div>
        </div>
      )}

      {/* Mouse event overlay for drawing */}
      {isManualSlotMode && drawingMode && (
        <div
          className="absolute inset-0 z-20"
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={() => {
            if (drawStart) {
              setDrawStart(null);
              setDrawEnd(null);
            }
          }}
          style={{ cursor: "crosshair" }}
        />
      )}
    </main>
  );
}