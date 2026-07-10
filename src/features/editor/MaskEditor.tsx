import React, { useRef, useEffect, useState, forwardRef, useImperativeHandle } from 'react';
import { Button } from '@/components/ui/Button';
import { Icon } from '@/components/ui/icons';
import type { SimplifyResult } from '@/api/toolProcessor';
import { simplifyContours } from '@/api/toolProcessor';

interface MaskEditorProps {
  maskImage: string;
  onMaskUpdate: (updatedMask: string) => void;
  onSimplifyComplete: (result: SimplifyResult) => void;
  originalContour?: string; // 原始轮廓图像（红色边框）
  backgroundImage?: string; // 背景图像（用于半透明叠加）
}

export function MaskEditor({ maskImage, onMaskUpdate, onSimplifyComplete, originalContour, backgroundImage }: MaskEditorProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [tool, setTool] = useState<'brush' | 'eraser'>('brush');
  const [brushSize, setBrushSize] = useState(10);
  const [originalImageData, setOriginalImageData] = useState<string>('');
  const [lastPos, setLastPos] = useState<{x: number, y: number} | null>(null);

  useEffect(() => {
    if (maskImage) {
      setOriginalImageData(maskImage);
      // 确保图像加载完成后再绘制
      const img = new Image();
      img.onload = () => {
        drawMaskOnCanvas(maskImage);
      };
      img.src = maskImage;
    }
  }, [maskImage]);

  const drawMaskOnCanvas = (imageSrc: string) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const img = new Image();
    img.onload = () => {
      // 设置主画布尺寸
      canvas.width = img.width;
      canvas.height = img.height;

      // 清空主画布
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // 直接绘制蒙版图像
      ctx.drawImage(img, 0, 0);

      // 如果有背景图像，绘制背景图像（半透明）
      if (backgroundImage) {
        const bgImg = new Image();
        bgImg.onload = () => {
          // 保存当前状态
          ctx.save();
          ctx.globalAlpha = 0.3; // 背景半透明显示
          ctx.drawImage(bgImg, 0, 0);
          // 恢复状态
          ctx.restore();
        };
        bgImg.src = backgroundImage;
      }

      // 如果有原始轮廓图像，叠加显示（半透明）
      if (originalContour) {
        const contourImg = new Image();
        contourImg.onload = () => {
          // 保存当前状态
          ctx.save();
          ctx.globalAlpha = 0.5; // 轮廓半透明显示
          ctx.drawImage(contourImg, 0, 0);
          // 恢复状态
          ctx.restore();
        };
        contourImg.src = originalContour;
      }

      // 初始化预览
      updateViewportPreview();
    };
    img.onerror = (error) => {
      console.error('Failed to load mask image:', error);
    };
    img.src = imageSrc;
  };

  const getMousePos = (e: React.MouseEvent<HTMLCanvasElement> | React.TouchEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };

    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;

    let clientX, clientY;
    if ('touches' in e) {
      clientX = e.touches[0].clientX;
      clientY = e.touches[0].clientY;
    } else {
      clientX = e.clientX;
      clientY = e.clientY;
    }

    return {
      x: (clientX - rect.left) * scaleX,
      y: (clientY - rect.top) * scaleY
    };
  };

  const startDrawing = (e: React.MouseEvent<HTMLCanvasElement> | React.TouchEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    setIsDrawing(true);
    const pos = getMousePos(e);
    setLastPos(pos);
    // 开始一个新的路径
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.beginPath();
    ctx.moveTo(pos.x, pos.y);
  };

  const stopDrawing = () => {
    setIsDrawing(false);
    setLastPos(null);
    // 停止绘制时更新蒙版数据
    const canvas = canvasRef.current;
    if (canvas) {
      const dataUrl = canvas.toDataURL('image/jpeg');
      onMaskUpdate(dataUrl);
    }
  };

  const updateViewportPreview = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const viewportCanvas = document.getElementById('editor-preview-canvas') as HTMLCanvasElement;
    if (viewportCanvas) {
      const viewportCtx = viewportCanvas.getContext('2d');
      if (viewportCtx) {
        // 设置Viewport画布尺寸
        viewportCanvas.width = canvas.width;
        viewportCanvas.height = canvas.height;

        // 清空画布
        viewportCtx.clearRect(0, 0, viewportCanvas.width, viewportCanvas.height);

        // 直接绘制当前画布内容到预览画布
        viewportCtx.drawImage(canvas, 0, 0);

        // 如果有背景图像，绘制背景图像（半透明）
        if (backgroundImage) {
          const bgImg = new Image();
          bgImg.onload = () => {
            // 保存当前状态
            viewportCtx.save();
            viewportCtx.globalAlpha = 0.3; // 背景半透明显示
            viewportCtx.drawImage(bgImg, 0, 0);
            // 恢复状态
            viewportCtx.restore();
          };
          bgImg.src = backgroundImage;
        }

        // 如果有原始轮廓图像，叠加显示（半透明）
        if (originalContour) {
          const contourImg = new Image();
          contourImg.onload = () => {
            // 保存当前状态
            viewportCtx.save();
            viewportCtx.globalAlpha = 0.5; // 轮廓半透明显示
            viewportCtx.drawImage(contourImg, 0, 0);
            // 恢复状态
            viewportCtx.restore();
          };
          contourImg.src = originalContour;
        }
      }
    }
  };

  
  const draw = (x: number, y: number) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.lineWidth = brushSize;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    // 画笔使用白色（增加蒙版区域），橡皮擦使用黑色（减少蒙版区域）
    ctx.strokeStyle = tool === 'brush' ? '#ffffff' : '#000000';
    ctx.globalCompositeOperation = 'source-over';

    if (lastPos) {
      // 简单直线绘制
      ctx.beginPath();
      ctx.moveTo(lastPos.x, lastPos.y);
      ctx.lineTo(x, y);
      ctx.stroke();
    }

    // 更新最后位置
    setLastPos({x, y});

    // 实时更新Viewport预览
    updateViewportPreview();

    // 更新蒙版数据
    const dataUrl = canvas.toDataURL('image/jpeg');
    onMaskUpdate(dataUrl);
  };


  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDrawing) return;
    e.preventDefault();
    const pos = getMousePos(e);
    draw(pos.x, pos.y);
  };

  const handleTouchStart = (e: React.TouchEvent<HTMLCanvasElement>) => {
    startDrawing(e);
  };

  const handleTouchMove = (e: React.TouchEvent<HTMLCanvasElement>) => {
    if (!isDrawing) return;
    e.preventDefault();
    const pos = getMousePos(e);
    draw(pos.x, pos.y);
  };

  const handleTouchEnd = () => {
    stopDrawing();
  };

  const handleSimplify = async () => {
    if (!canvasRef.current) return;

    try {
      const maskDataUrl = canvasRef.current.toDataURL('image/jpeg');
      const maskData = {
        mask_image: maskDataUrl
      };

      const result = await simplifyContours(maskData);
      onSimplifyComplete(result);
    } catch (error) {
      console.error('简化轮廓失败:', error);
      onSimplifyComplete({
        success: false,
        error: error instanceof Error ? error.message : '未知错误'
      });
    }
  };

  const resetToOriginal = () => {
    if (originalImageData) {
      drawMaskOnCanvas(originalImageData);
      onMaskUpdate(originalImageData);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 mb-4">
        <Button
          variant={tool === 'brush' ? 'primary' : 'secondary'}
          size="sm"
          onClick={() => setTool('brush')}
        >
          <Icon name="pencil" size={16} />
          画笔
        </Button>
        <Button
          variant={tool === 'eraser' ? 'primary' : 'secondary'}
          size="sm"
          onClick={() => setTool('eraser')}
        >
          <Icon name="crop" size={16} />
          橡皮擦
        </Button>
        <div className="flex items-center gap-2 ml-4">
          <span className="text-sm text-zinc-400">大小:</span>
          <input
            type="range"
            min="1"
            max="50"
            value={brushSize}
            onChange={(e) => setBrushSize(parseInt(e.target.value))}
            className="w-20"
          />
          <span className="text-sm text-zinc-300 w-8">{brushSize}px</span>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={resetToOriginal}
          className="ml-auto"
        >
          <Icon name="arrowLeft" size={16} />
          重置
        </Button>
      </div>

      <div className="border border-canvas-700 rounded-lg overflow-hidden">
        <canvas
          ref={canvasRef}
          onMouseDown={startDrawing}
          onMouseUp={stopDrawing}
          onMouseMove={handleMouseMove}
          onMouseLeave={stopDrawing}
          onTouchStart={handleTouchStart}
          onTouchMove={handleTouchMove}
          onTouchEnd={handleTouchEnd}
          className="cursor-crosshair w-full"
          style={{ maxHeight: '70vh' }}
        />
      </div>

      <div className="flex gap-2">
        <Button
          onClick={handleSimplify}
          className="flex-1"
        >
          <Icon name="wand" size={16} />
          抽稀基元化
        </Button>
      </div>

          </div>
  );
}

export default MaskEditor;