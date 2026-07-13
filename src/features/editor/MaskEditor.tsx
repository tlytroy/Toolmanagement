import React, { useRef, useEffect, useState, useCallback, forwardRef, useImperativeHandle } from 'react';
import { Button } from '@/components/ui/Button';
import { Icon } from '@/components/ui/icons';
import type { SimplifyResult } from '@/api/toolProcessor';
import { simplifyContours, updateContour } from '@/api/toolProcessor';

/* ============================================================
   Stroke Stabilization — weighted moving average + EMA
   ============================================================ */

interface Point { x: number; y: number; }

class StrokeStabilizer {
  private buffer: Point[] = [];
  private smoothed: Point | null = null;
  private bufferSize: number;
  private alpha: number;

  constructor(bufferSize: number = 8, alpha: number = 0.20) {
    this.bufferSize = bufferSize;
    this.alpha = alpha;
  }

  reset(): void {
    this.buffer = [];
    this.smoothed = null;
  }

  configure(bufferSize: number, alpha: number): void {
    this.bufferSize = bufferSize;
    this.alpha = alpha;
    this.reset();
  }

  /** Feed a raw point, return the smoothed point (or null if buffer not full enough) */
  feed(raw: Point): Point | null {
    this.buffer.push(raw);
    if (this.buffer.length > this.bufferSize) {
      this.buffer = this.buffer.slice(-this.bufferSize);
    }

    // Weighted average: more recent = higher weight
    const n = this.buffer.length;
    let totalWeight = 0;
    let wx = 0;
    let wy = 0;
    for (let i = 0; i < n; i++) {
      const w = i + 1;
      wx += this.buffer[i].x * w;
      wy += this.buffer[i].y * w;
      totalWeight += w;
    }

    const avg: Point = { x: wx / totalWeight, y: wy / totalWeight };

    // Exponential moving average over the weighted average result
    if (!this.smoothed) {
      this.smoothed = avg;
    } else {
      this.smoothed = {
        x: this.smoothed.x + (avg.x - this.smoothed.x) * this.alpha,
        y: this.smoothed.y + (avg.y - this.smoothed.y) * this.alpha,
      };
    }

    return this.smoothed;
  }
}

/* ============================================================
   Drawing tool modes
   ============================================================ */

/** Shape tools (fill mode) — NOT freehand */
type ShapeTool = 'line' | 'rect' | 'ellipse' | 'polyline';
/** All tools */
type DrawTool = 'brush' | 'eraser' | ShapeTool;

const SHAPE_TOOLS: { id: ShapeTool; label: string; key: string; icon: string }[] = [
  { id: 'line',      label: '直线',   key: 'L', icon: 'line' },
  { id: 'polyline',  label: '折线',   key: 'P', icon: 'polyline' },
  { id: 'rect',      label: '矩形',   key: 'R', icon: 'rect' },
  { id: 'ellipse',   label: '椭圆',   key: 'O', icon: 'ellipse' },
];

/* ============================================================
   MaskEditor Component
   ============================================================ */

interface MaskEditorProps {
  maskImage: string;
  onMaskUpdate: (updatedMask: string) => void;
  onSimplifyComplete: (result: SimplifyResult) => void;
  onUpdateContour: (result: SimplifyResult) => void;
  backgroundImage?: string;
}

export const MaskEditor = forwardRef<{ handleSimplify: () => Promise<void> }, MaskEditorProps>(({
  maskImage,
  onMaskUpdate,
  onSimplifyComplete,
  onUpdateContour,
  backgroundImage
}, ref) => {
  // --- Refs ---
  const displayCanvasRef = useRef<HTMLCanvasElement>(null);
  const previewCanvasRef = useRef<HTMLCanvasElement>(null);
  const offscreenRef = useRef<HTMLCanvasElement | null>(null);
  const bgImageRef = useRef<HTMLImageElement | null>(null);
  const maskImageDataRef = useRef<ImageData | null>(null);
  const stabilizerRef = useRef(new StrokeStabilizer());
  const prevSmoothedRef = useRef<Point | null>(null);
  const updateTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // --- State ---
  const [isDrawing, setIsDrawing] = useState(false);
  const [paintMode, setPaintMode] = useState<'brush' | 'eraser'>('brush');
  const [drawTool, setDrawTool] = useState<DrawTool>('brush');
  const [brushSize, setBrushSize] = useState(12);
  const [loaded, setLoaded] = useState(false);

  // --- History for undo functionality ---
  const [history, setHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const maxHistoryLength = 50; // 限制历史记录数量

  // Remember last shape tool for each paint mode (brush/eraser)
  const lastShapeForBrushRef = useRef<ShapeTool>('line');
  const lastShapeForEraserRef = useRef<ShapeTool>('line');

  // Cursor position for visual feedback
  const [cursorPosition, setCursorPosition] = useState<Point | null>(null);

  // Shape-specific state
  const [dragStart, setDragStart] = useState<Point | null>(null);
  const [dragCurrent, setDragCurrent] = useState<Point | null>(null);
  const [polyPoints, setPolyPoints] = useState<Point[]>([]);

  // Stabilization strength (0-100, maps to buffer 3-15 and alpha 0.45-0.10)
  const [stability, setStability] = useState(65);

  // Derived: map stability slider to buffer size + alpha
  const stabilizerConfig = useCallback((strength: number) => {
    const t = strength / 100; // 0..1
    const buf = Math.round(3 + t * 12); // 3 .. 15
    const alpha = 0.45 - t * 0.35;      // 0.45 .. 0.10
    return { buf, alpha: Math.max(0.10, alpha) };
  }, []);

  // Apply stabilizer config when it changes
  useEffect(() => {
    const { buf, alpha } = stabilizerConfig(stability);
    stabilizerRef.current.configure(buf, alpha);
  }, [stability, stabilizerConfig]);

  // Update cursor indicator when cursor position or brush size changes
  useEffect(() => {
    if (cursorPosition && !isDrawing) {
      drawCursorIndicator(cursorPosition);
    }
  }, [cursorPosition, brushSize, isDrawing]);

  // --- Image loading ---
  useEffect(() => {
    setLoaded(false);
    const bgImg = new Image();
    const maskImg = new Image();
    let bgOk = !backgroundImage;
    let maskOk = false;

    const tryInit = () => {
      if (bgOk && maskOk) {
        initCanvases(bgImageRef.current ?? maskImg, maskImg);
      }
    };

    if (backgroundImage) {
      const onBgLoad = () => {
        bgImageRef.current = bgImg;
        bgOk = true;
        tryInit();
      };
      bgImg.onload = onBgLoad;
      bgImg.onerror = () => { bgOk = true; tryInit(); };
      bgImg.src = backgroundImage;
      if (bgImg.complete) onBgLoad();
    }

    const onMaskLoad = () => {
      maskOk = true;
      tryInit();
    };
    maskImg.onload = onMaskLoad;
    maskImg.src = maskImage;
    if (maskImg.complete) onMaskLoad();
  }, [maskImage, backgroundImage]);

  /** Initialize canvases */
  const initCanvases = (_bg: HTMLImageElement, mask: HTMLImageElement) => {
    const w = mask.width;
    const h = mask.height;

    let off = offscreenRef.current;
    if (!off || off.width !== w || off.height !== h) {
      off = document.createElement('canvas');
      off.width = w;
      off.height = h;
      offscreenRef.current = off;
    }
    const octx = off.getContext('2d')!;
    octx.fillStyle = '#000000';
    octx.fillRect(0, 0, w, h);
    octx.drawImage(mask, 0, 0);
    maskImageDataRef.current = octx.getImageData(0, 0, w, h);

    renderDisplay();
    setLoaded(true);
  };

  /** Composite: background → offscreen mask → display canvas */
  const renderDisplay = () => {
    const canvas = displayCanvasRef.current;
    const off = offscreenRef.current;
    if (!canvas || !off) return;

    canvas.width = off.width;
    canvas.height = off.height;
    const ctx = canvas.getContext('2d')!;

    if (bgImageRef.current) {
      ctx.globalAlpha = 0.30;
      ctx.drawImage(bgImageRef.current, 0, 0);
      ctx.globalAlpha = 1.0;
    }

    ctx.drawImage(off, 0, 0);
  };

  /** Clear preview canvas */
  const clearPreview = () => {
    const prev = previewCanvasRef.current;
    if (!prev) return;
    const pctx = prev.getContext('2d')!;
    pctx.clearRect(0, 0, prev.width, prev.height);
  };

  /** Draw cursor indicator on preview canvas */
  const drawCursorIndicator = (pos: Point) => {
    const prev = previewCanvasRef.current;
    const off = offscreenRef.current;
    if (!prev || !off) return;

    const pctx = prev.getContext('2d')!;
    pctx.clearRect(0, 0, prev.width, prev.height);

    // Draw brush circle indicator
    pctx.strokeStyle = '#ffffff';
    pctx.lineWidth = 2;
    pctx.setLineDash([5, 5]); // Dashed line
    pctx.lineCap = 'round';
    pctx.beginPath();
    pctx.arc(pos.x, pos.y, brushSize / 2, 0, Math.PI * 2);
    pctx.stroke();

    // Draw center dot
    pctx.fillStyle = '#ffffff';
    pctx.setLineDash([]); // Solid line
    pctx.beginPath();
    pctx.arc(pos.x, pos.y, 2, 0, Math.PI * 2);
    pctx.fill();
  };

  /** Draw shape preview on preview canvas */
  const drawShapePreview = (from: Point, to: Point) => {
    const prev = previewCanvasRef.current;
    const off = offscreenRef.current;
    if (!prev || !off) return;

    prev.width = off.width;
    prev.height = off.height;
    const pctx = prev.getContext('2d')!;
    pctx.clearRect(0, 0, prev.width, prev.height);

    const color = paintMode === 'brush' ? '#ffffff' : '#000000';
    pctx.fillStyle = color;
    pctx.strokeStyle = color;
    pctx.lineWidth = brushSize;
    pctx.lineCap = 'round';
    pctx.lineJoin = 'round';

    // Semi-transparent preview
    pctx.globalAlpha = 0.55;

    if (drawTool === 'line' || drawTool === 'polyline') {
      pctx.beginPath();
      pctx.moveTo(from.x, from.y);
      pctx.lineTo(to.x, to.y);
      pctx.stroke();
    } else if (drawTool === 'rect') {
      const x = Math.min(from.x, to.x);
      const y = Math.min(from.y, to.y);
      const w = Math.abs(to.x - from.x);
      const h = Math.abs(to.y - from.y);
      pctx.fillRect(x, y, w, h);
    } else if (drawTool === 'ellipse') {
      const cx = (from.x + to.x) / 2;
      const cy = (from.y + to.y) / 2;
      const rx = Math.abs(to.x - from.x) / 2;
      const ry = Math.abs(to.y - from.y) / 2;
      pctx.beginPath();
      pctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
      pctx.fill();
    }

    pctx.globalAlpha = 1.0;
  };

  // --- Coordinate helper ---
  const getCanvasPos = useCallback((clientX: number, clientY: number): Point | null => {
    const canvas = displayCanvasRef.current;
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    const sx = canvas.width / rect.width;
    const sy = canvas.height / rect.height;
    return { x: (clientX - rect.left) * sx, y: (clientY - rect.top) * sy };
  }, []);

  // ====================================================
  //  FREEHAND (brush / eraser) drawing
  // ====================================================

  const drawDot = useCallback((cx: number, cy: number) => {
    const off = offscreenRef.current;
    if (!off) return;
    const octx = off.getContext('2d')!;
    octx.fillStyle = paintMode === 'brush' ? '#ffffff' : '#000000';
    octx.beginPath();
    octx.arc(cx, cy, brushSize / 2, 0, Math.PI * 2);
    octx.fill();
    renderDisplay();
  }, [paintMode, brushSize]);

  const drawSegment = useCallback((from: Point, to: Point) => {
    const off = offscreenRef.current;
    if (!off) return;
    const octx = off.getContext('2d')!;
    octx.strokeStyle = paintMode === 'brush' ? '#ffffff' : '#000000';
    octx.lineWidth = brushSize;
    octx.lineCap = 'round';
    octx.lineJoin = 'round';
    octx.beginPath();
    const mx = (from.x + to.x) / 2;
    const my = (from.y + to.y) / 2;
    octx.moveTo(from.x, from.y);
    octx.quadraticCurveTo(from.x, from.y, mx, my);
    octx.stroke();
    renderDisplay();
  }, [paintMode, brushSize]);

  // ====================================================
  //  SHAPE drawing — commit to offscreen
  // ====================================================

  const commitShapeLine = (from: Point, to: Point) => {
    const off = offscreenRef.current;
    if (!off) return;
    const octx = off.getContext('2d')!;
    octx.strokeStyle = paintMode === 'brush' ? '#ffffff' : '#000000';
    octx.lineWidth = brushSize;
    octx.lineCap = 'round';
    octx.beginPath();
    octx.moveTo(from.x, from.y);
    octx.lineTo(to.x, to.y);
    octx.stroke();
  };

  const commitShapeRect = (from: Point, to: Point) => {
    const off = offscreenRef.current;
    if (!off) return;
    const octx = off.getContext('2d')!;
    octx.fillStyle = paintMode === 'brush' ? '#ffffff' : '#000000';
    const x = Math.min(from.x, to.x);
    const y = Math.min(from.y, to.y);
    const w = Math.abs(to.x - from.x);
    const h = Math.abs(to.y - from.y);
    octx.fillRect(x, y, w, h);
  };

  const commitShapeEllipse = (from: Point, to: Point) => {
    const off = offscreenRef.current;
    if (!off) return;
    const octx = off.getContext('2d')!;
    octx.fillStyle = paintMode === 'brush' ? '#ffffff' : '#000000';
    const cx = (from.x + to.x) / 2;
    const cy = (from.y + to.y) / 2;
    const rx = Math.abs(to.x - from.x) / 2;
    const ry = Math.abs(to.y - from.y) / 2;
    octx.beginPath();
    octx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
    octx.fill();
  };

  // ====================================================
  //  EVENT HANDLERS
  // ====================================================

  const extractEventPos = (e: React.MouseEvent | React.TouchEvent): { cx: number; cy: number } | null => {
    if ('touches' in e) {
      if (e.touches.length === 0) return null;
      return { cx: e.touches[0].clientX, cy: e.touches[0].clientY };
    }
    return { cx: e.clientX, cy: e.clientY };
  };

  const startDraw = useCallback((e: React.MouseEvent | React.TouchEvent) => {
    e.preventDefault();
    const pos = extractEventPos(e);
    if (!pos) return;
    const pt = getCanvasPos(pos.cx, pos.cy);
    if (!pt) return;

    // Clear cursor indicator when starting to draw
    clearPreview();

    // Shape tools
    if (isShapeTool(drawTool)) {
      setIsDrawing(true);
      setDragStart(pt);
      setDragCurrent(pt);
      if (drawTool === 'polyline' && polyPoints.length === 0) {
        setPolyPoints([pt]);
      }
      return;
    }

    // Freehand
    setIsDrawing(true);
    stabilizerRef.current.reset();
    prevSmoothedRef.current = null;
    drawDot(pt.x, pt.y);
    stabilizerRef.current.feed(pt);
  }, [getCanvasPos, drawDot, drawTool, polyPoints.length, clearPreview]);

  const moveDraw = useCallback((e: React.MouseEvent | React.TouchEvent) => {
    e.preventDefault();
    const pos = extractEventPos(e);
    if (!pos) return;
    const pt = getCanvasPos(pos.cx, pos.cy);
    if (!pt) return;

    // Update cursor position for visual feedback
    setCursorPosition(pt);

    // If not drawing, show cursor indicator
    if (!isDrawing) {
      drawCursorIndicator(pt);
      return;
    }

    // Shape tools: update preview
    if (isShapeTool(drawTool)) {
      setDragCurrent(pt);
      if (dragStart) {
        drawShapePreview(dragStart, pt);
      }
      return;
    }

    // Freehand: stabilized stroke
    const smoothed = stabilizerRef.current.feed(pt);
    if (!smoothed) return;

    if (prevSmoothedRef.current) {
      drawSegment(prevSmoothedRef.current, smoothed);
    } else {
      drawDot(smoothed.x, smoothed.y);
    }
    prevSmoothedRef.current = smoothed;

    // Throttled mask update
    if (!updateTimerRef.current) {
      updateTimerRef.current = setTimeout(() => {
        updateTimerRef.current = null;
        emitMaskUpdate();
      }, 80);
    }
  }, [isDrawing, getCanvasPos, drawTool, dragStart, drawSegment, drawDot]);

  const endDraw = useCallback(() => {
    if (!isDrawing) return;

    // Shape tools: commit shape
    if (isShapeTool(drawTool) && dragStart && dragCurrent) {
      if (drawTool === 'line') {
        commitShapeLine(dragStart, dragCurrent);
      } else if (drawTool === 'rect') {
        commitShapeRect(dragStart, dragCurrent);
      } else if (drawTool === 'ellipse') {
        commitShapeEllipse(dragStart, dragCurrent);
      }
      // polyline is handled in clickPolyVertex

      clearPreview();
      renderDisplay();
    }

    setIsDrawing(false);
    setDragStart(null);
    setDragCurrent(null);

    // Freehand finalize
    if (!isShapeTool(drawTool)) {
      stabilizerRef.current.reset();
      prevSmoothedRef.current = null;
    }

    if (updateTimerRef.current) {
      clearTimeout(updateTimerRef.current);
      updateTimerRef.current = null;
    }
    emitMaskUpdate();
  }, [isDrawing, drawTool, dragStart, dragCurrent, paintMode, clearPreview]);

  const leaveCanvas = useCallback(() => {
    // Clear cursor indicator when leaving canvas
    setCursorPosition(null);
    clearPreview();
  }, [clearPreview]);

  // --- Polyline: click to add vertex ---
  const clickPolyVertex = useCallback((e: React.MouseEvent) => {
    if (drawTool !== 'polyline') return;
    const pt = getCanvasPos(e.clientX, e.clientY);
    if (!pt) return;

    const pts = [...polyPoints, pt];
    setPolyPoints(pts);

    if (pts.length >= 2) {
      // Draw segment between last two points on offscreen canvas
      commitShapeLine(pts[pts.length - 2], pts[pts.length - 1]);
      renderDisplay();
      emitMaskUpdate();
    }

    setDragStart(pt);
    setDragCurrent(pt);
  }, [drawTool, polyPoints, getCanvasPos]);

  const finishPolyline = useCallback(() => {
    if (drawTool !== 'polyline' || polyPoints.length === 0) return;
    setPolyPoints([]);
    clearPreview();
    setIsDrawing(false);
    setDragStart(null);
    setDragCurrent(null);
  }, [drawTool, polyPoints]);

  // Keyboard shortcuts for polyline
  useEffect(() => {
    if (drawTool !== 'polyline') return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        finishPolyline();
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        setPolyPoints([]);
        clearPreview();
        setIsDrawing(false);
        setDragStart(null);
        setDragCurrent(null);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [drawTool, finishPolyline]);

  // Update polyline preview (live preview line from last point to mouse)
  const movePolyPreview = useCallback((e: React.MouseEvent) => {
    if (drawTool !== 'polyline' || polyPoints.length === 0) return;
    const pt = getCanvasPos(e.clientX, e.clientY);
    if (!pt) return;
    setDragCurrent(pt);
    drawShapePreview(polyPoints[polyPoints.length - 1], pt);
  }, [drawTool, polyPoints, getCanvasPos]);

  // --- Canvas mouse event routing ---
  const onCanvasMouseDown = useCallback((e: React.MouseEvent | React.TouchEvent) => {
    if (drawTool === 'polyline') {
      if ('touches' in e && e.touches.length > 0) {
        const touch = e.touches[0];
        const mouseEvent = {
          clientX: touch.clientX,
          clientY: touch.clientY,
          preventDefault: () => {},
          stopPropagation: () => {}
        } as React.MouseEvent;
        clickPolyVertex(mouseEvent);
      } else if (!('touches' in e)) {
        clickPolyVertex(e as React.MouseEvent);
      }
    } else {
      startDraw(e);
    }
  }, [drawTool, clickPolyVertex, startDraw]);

  const onCanvasMouseMove = useCallback((e: React.MouseEvent | React.TouchEvent) => {
    if (drawTool === 'polyline' && polyPoints.length >= 1 && !isDrawing) {
      if ('touches' in e && e.touches.length > 0) {
        const touch = e.touches[0];
        const mouseEvent = {
          clientX: touch.clientX,
          clientY: touch.clientY,
          preventDefault: () => {},
          stopPropagation: () => {}
        } as React.MouseEvent;
        movePolyPreview(mouseEvent);
      } else if (!('touches' in e)) {
        movePolyPreview(e as React.MouseEvent);
      }
    } else {
      moveDraw(e);
    }
  }, [drawTool, polyPoints, isDrawing, movePolyPreview, moveDraw]);

  // Handle touch events for cursor position updates
  const onCanvasTouchMove = useCallback((e: React.TouchEvent) => {
    if (e.touches.length > 0) {
      const touch = e.touches[0];
      const mouseEvent = {
        clientX: touch.clientX,
        clientY: touch.clientY,
        preventDefault: () => {},
        stopPropagation: () => {}
      } as React.MouseEvent;
      moveDraw({
        ...mouseEvent,
        touches: e.touches
      } as unknown as React.TouchEvent);
    }
  }, [moveDraw]);

  const onCanvasMouseUp = useCallback(() => {
    if (drawTool !== 'polyline') {
      endDraw();
    }
  }, [drawTool, endDraw]);

  const onCanvasDoubleClick = useCallback(() => {
    if (drawTool === 'polyline') {
      finishPolyline();
    }
  }, [drawTool, finishPolyline]);

  // Enhanced emitMaskUpdate that saves to history
  const emitMaskUpdate = useCallback(() => {
    const off = offscreenRef.current;
    if (!off) return;
    const dataUrl = off.toDataURL('image/jpeg', 0.92);
    maskImageDataRef.current = off.getContext('2d')!.getImageData(0, 0, off.width, off.height);
    onMaskUpdate(dataUrl);
    
    // Save to history
    const newHistory = [...history.slice(0, historyIndex + 1), dataUrl];
    if (newHistory.length > maxHistoryLength) {
      newHistory.shift();
    }
    setHistory(newHistory);
    setHistoryIndex(newHistory.length - 1);
  }, [history, historyIndex, onMaskUpdate]);

  // --- Undo functionality ---
  const canUndo = historyIndex > 0;
  
  const undo = useCallback(() => {
    if (!canUndo || historyIndex <= 0) return;
    
    const prevIndex = historyIndex - 1;
    const prevState = history[prevIndex];
    
    if (prevState && offscreenRef.current) {
      const img = new Image();
      img.onload = () => {
        const ctx = offscreenRef.current!.getContext('2d')!;
        ctx.clearRect(0, 0, offscreenRef.current!.width, offscreenRef.current!.height);
        ctx.drawImage(img, 0, 0);
        renderDisplay();
        emitMaskUpdate();
        setHistoryIndex(prevIndex);
      };
      img.src = prevState;
    }
  }, [canUndo, history, historyIndex]);

  // --- Simplify & Update Contour ---
  const [updating, setUpdating] = useState(false);
  const [simplifying, setSimplifying] = useState(false);

  const handleUpdateContour = async () => {
    const off = offscreenRef.current;
    if (!off) return;
    setUpdating(true);
    try {
      const maskDataUrl = off.toDataURL('image/png');
      const result = await updateContour({ mask_image: maskDataUrl });
      onUpdateContour(result);
    } catch (error) {
      console.error('更新轮廓失败:', error);
      onUpdateContour({ success: false, error: error instanceof Error ? error.message : '未知错误' });
    } finally {
      setUpdating(false);
    }
  };

  const handleSimplifyClick = async () => {
    const off = offscreenRef.current;
    if (!off) return;
    setSimplifying(true);
    try {
      const maskDataUrl = off.toDataURL('image/png');
      const result = await simplifyContours({ mask_image: maskDataUrl });
      onSimplifyComplete(result);
    } catch (error) {
      console.error('抽稀基元化失败:', error);
      onSimplifyComplete({ success: false, error: error instanceof Error ? error.message : '未知错误' });
    } finally {
      setSimplifying(false);
    }
  };

  // --- Reset ---
  const resetMask = () => {
    if (!offscreenRef.current) return;
    const octx = offscreenRef.current.getContext('2d')!;
    octx.fillStyle = '#000000';
    octx.fillRect(0, 0, offscreenRef.current.width, offscreenRef.current.height);
    const maskImg = new Image();
    maskImg.onload = () => {
      octx.drawImage(maskImg, 0, 0);
      renderDisplay();
      emitMaskUpdate();
    };
    maskImg.src = maskImage;
  };

  // ====================================================
  //  KEYBOARD SHORTCUTS
  // ====================================================

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // Don't trigger when typing in inputs
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

      const key = e.key.toLowerCase();
      
      // Undo (Ctrl+Z)
      if ((e.ctrlKey || e.metaKey) && key === 'z') {
        e.preventDefault();
        if (canUndo) {
          undo();
        }
        return;
      }
      
      // Brush: toggle between brush and last shape tool
      if (key === 'b') {
        if (drawTool === 'brush' && lastShapeForBrushRef.current) {
          setDrawTool(lastShapeForBrushRef.current);
        } else {
          if (isShapeTool(drawTool)) lastShapeForBrushRef.current = drawTool;
          setDrawTool('brush');
          setPaintMode('brush');
        }
      }
      // Eraser: toggle between eraser and last shape tool
      if (key === 'e') {
        if (drawTool === 'eraser' && lastShapeForEraserRef.current) {
          setDrawTool(lastShapeForEraserRef.current);
        } else {
          if (isShapeTool(drawTool)) lastShapeForEraserRef.current = drawTool;
          setDrawTool('eraser');
          setPaintMode('eraser');
        }
      }
      if (key === 'l') setDrawTool('line');
      if (key === 'p') setDrawTool('polyline');
      if (key === 'r') setDrawTool('rect');
      if (key === 'o') setDrawTool('ellipse');
      if (key === '[') setBrushSize(s => Math.max(1, s - 2));
      if (key === ']') setBrushSize(s => Math.min(60, s + 2));
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [drawTool, canUndo, undo]);

  // --- Expose ---
  useImperativeHandle(ref, () => ({ handleSimplify: handleSimplifyClick }));

  // ====================================================
  //  RENDER
  // ====================================================

  const isFreehand = drawTool === 'brush' || drawTool === 'eraser';
  const isBrushTool = drawTool === 'brush';
  const isEraserTool = drawTool === 'eraser';

  return (
    <div className="flex flex-col gap-3 h-full">
      {/* ── Toolbar Row 1: Freehand tools ── */}
      <div className="flex items-center gap-2 flex-wrap">
        <div className="flex items-center bg-canvas-800 rounded-lg p-0.5">
          <button
            onClick={() => {
              if (drawTool === 'brush' && lastShapeForBrushRef.current) {
                setDrawTool(lastShapeForBrushRef.current);
              } else {
                if (isShapeTool(drawTool)) lastShapeForBrushRef.current = drawTool;
                setDrawTool('brush');
                setPaintMode('brush');
              }
            }}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              isBrushTool ? 'bg-brand-600 text-white shadow-sm' : 'text-zinc-400 hover:text-zinc-200'
            }`}
            title="画笔 (B)"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M17 3a2.83 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/><path d="m15 5 4 4"/>
            </svg>
            画笔 <span className="text-[10px] opacity-60 ml-0.5">B</span>
          </button>
          <button
            onClick={() => {
              if (drawTool === 'eraser' && lastShapeForEraserRef.current) {
                setDrawTool(lastShapeForEraserRef.current);
              } else {
                if (isShapeTool(drawTool)) lastShapeForEraserRef.current = drawTool;
                setDrawTool('eraser');
                setPaintMode('eraser');
              }
            }}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              isEraserTool ? 'bg-brand-600 text-white shadow-sm' : 'text-zinc-400 hover:text-zinc-200'
            }`}
            title="橡皮 (E)"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="m7 21-4.3-4.3c-1-1-1-2.5 0-3.4l9.6-9.6c1-1 2.5-1 3.4 0l5.6 5.6c1 1 1 2.5 0 3.4L13 21"/><path d="M22 21H7"/><path d="m5 11 9 9"/>
            </svg>
            橡皮 <span className="text-[10px] opacity-60 ml-0.5">E</span>
          </button>
        </div>

        <div className="h-5 w-px bg-canvas-700" />

        {/* ── Shape tools ── */}
        {SHAPE_TOOLS.map(st => (
          <button
            key={st.id}
            onClick={() => { setDrawTool(st.id); }}
            className={`flex items-center gap-1 px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors ${
              drawTool === st.id ? 'bg-amber-600/80 text-white shadow-sm' : 'text-zinc-400 hover:text-zinc-200 hover:bg-canvas-800'
            }`}
            title={`${st.label} (${st.key})`}
          >
            {shapeIcon(st.id, 14)}
            <span className="text-[10px] opacity-60">{st.key}</span>
          </button>
        ))}

        <div className="h-5 w-px bg-canvas-700" />

        {/* ── Brush size ── */}
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] text-zinc-500">大小</span>
          <input
            type="range" min="2" max="50" value={brushSize}
            onChange={(e) => setBrushSize(parseInt(e.target.value))}
            className="w-16 h-1 accent-brand-500"
          />
          <span className="text-xs text-zinc-300 w-7 tabular-nums">{brushSize}</span>
        </div>

        <button
          onClick={undo}
          disabled={!canUndo}
          className={`flex items-center gap-1 px-2.5 py-1.5 rounded-md text-xs transition-colors ${
            canUndo 
              ? 'text-zinc-400 hover:text-zinc-200 hover:bg-canvas-800' 
              : 'text-zinc-600 cursor-not-allowed'
          }`}
          title="撤回 (Ctrl+Z)"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 7v6h6l-4 4 4 4m8-11h2m-2 4h2m-6 4h6"/>
          </svg>
          撤回
        </button>

        <button
          onClick={resetMask}
          className="flex items-center gap-1 px-2.5 py-1.5 rounded-md text-xs text-zinc-400 hover:text-zinc-200 hover:bg-canvas-800 transition-colors"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>
          </svg>
          重置
        </button>
      </div>

      {/* ── Toolbar Row 2: Stabilization (only for freehand) ── */}
      {isFreehand && (
        <div className="flex items-center gap-2">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className="text-zinc-500">
            <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
          </svg>
          <span className="text-[11px] text-zinc-500 mr-0.5">防抖</span>
          <input
            type="range" min="0" max="100" value={stability}
            onChange={(e) => setStability(parseInt(e.target.value))}
            className="w-20 h-1 accent-amber-500"
          />
          <span className="text-xs text-zinc-400 w-8 tabular-nums">
            {stability <= 33 ? '弱' : stability <= 66 ? '中' : '强'}
          </span>
          <span className="text-[10px] text-zinc-600 ml-1">[ / ] 调大小</span>
        </div>
      )}

      {/* ── Polyline hint ── */}
      {drawTool === 'polyline' && (
        <div className="flex items-center gap-2 text-[11px] text-amber-400/80 bg-amber-400/5 rounded-lg px-3 py-1.5">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="shrink-0">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
          <span>单击添加顶点</span>
          <span className="text-zinc-600">|</span>
          <span>双击或按 <kbd className="px-1 py-0.5 bg-canvas-700 rounded text-[10px]">Enter</kbd> 完成 · <kbd className="px-1 py-0.5 bg-canvas-700 rounded text-[10px]">Esc</kbd> 取消</span>
        </div>
      )}

      {/* ── Canvas area ── */}
      <div className="flex-1 min-h-0 border border-canvas-700 rounded-xl overflow-hidden bg-black/50 relative">
        {!loaded && (
          <div className="absolute inset-0 flex items-center justify-center text-zinc-500 text-sm">加载中...</div>
        )}

        {/* Display canvas (background + mask) */}
        <canvas
          ref={displayCanvasRef}
          className="absolute inset-0 w-full h-full object-contain pointer-events-none"
          style={{ display: loaded ? 'block' : 'none' }}
        />

        {/* Preview canvas (shape previews) */}
        <canvas
          ref={previewCanvasRef}
          className="absolute inset-0 w-full h-full object-contain pointer-events-none"
          style={{ display: loaded ? 'block' : 'none' }}
        />

        {/* Interaction canvas (transparent, catches events) */}
        <canvas
          width={loaded ? offscreenRef.current?.width ?? 0 : 0}
          height={loaded ? offscreenRef.current?.height ?? 0 : 0}
          onMouseDown={onCanvasMouseDown}
          onMouseUp={onCanvasMouseUp}
          onMouseMove={onCanvasMouseMove}
          onMouseLeave={leaveCanvas}
          onDoubleClick={onCanvasDoubleClick}
          onTouchStart={onCanvasMouseDown}
          onTouchMove={onCanvasTouchMove}
          onTouchEnd={onCanvasMouseUp}
          className="absolute inset-0 w-full h-full object-contain"
          style={{
            display: loaded ? 'block' : 'none',
            cursor: drawTool === 'polyline' ? 'crosshair' : 'crosshair',
            opacity: 0,
          }}
        />

        {/* Status bar */}
        {loaded && (
          <div className="absolute bottom-2 left-2 glass-bar rounded-md px-2 py-1 text-[10px] text-zinc-400 flex items-center gap-2">
            <span>
              {drawTool === 'brush' ? '🖌 画笔' :
               drawTool === 'eraser' ? '🧹 橡皮' :
               drawTool === 'line' ? '📏 直线' :
               drawTool === 'rect' ? '🔲 矩形' :
               drawTool === 'ellipse' ? '⭕ 椭圆' :
               '📐 折线'}
            </span>
            <span>·</span>
            <span>{brushSize}px</span>
            <span>·</span>
            <span className="text-zinc-600">[ / ] 调整大小</span>
          </div>
        )}
      </div>

      {/* ── Action buttons ── */}
      <div className="flex gap-2">
        <Button onClick={handleUpdateContour} disabled={!loaded || updating} className="flex-1" variant="secondary">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
          </svg>
          {updating ? '更新中…' : '更新轮廓'}
        </Button>
        <Button onClick={handleSimplifyClick} disabled={!loaded || simplifying} className="flex-1" variant="primary">
          <Icon name="wand" size={16} />
          {simplifying ? '处理中…' : '抽稀基元化'}
        </Button>
      </div>
    </div>
  );
});

export default MaskEditor;

/* ============================================================
   Helpers
   ============================================================ */

function isShapeTool(tool: DrawTool): tool is ShapeTool {
  return tool === 'line' || tool === 'rect' || tool === 'ellipse' || tool === 'polyline';
}

function shapeIcon(tool: ShapeTool, size: number) {
  const s = size;
  switch (tool) {
    case 'line':
      return (
        <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <line x1="4" y1="20" x2="20" y2="4"/>
        </svg>
      );
    case 'polyline':
      return (
        <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="3 20 7 12 13 7 21 14"/>
        </svg>
      );
    case 'rect':
      return (
        <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="4" y="5" width="16" height="14" rx="1"/>
        </svg>
      );
    case 'ellipse':
      return (
        <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <ellipse cx="12" cy="12" rx="9" ry="7"/>
        </svg>
      );
  }
}
