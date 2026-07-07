import { useState, useCallback, useEffect, useRef } from 'react'
import { useOpenCV } from '@/hooks/useOpenCV'
import { useStore } from '@/app/store'
import { detectPaperCorners, perspectiveWarp, extractToolContours, type PaperDetection } from '@/lib/opencvUtils'
import { Button } from '@/components/ui/Button'

export default function CalibrationPage() {
  const { cv, loaded, error } = useOpenCV()
  const storedImageUrl = useStore((s) => s.imageUrl)

  const [imgUrl, setImgUrl] = useState<string>()
  const [detect, setDetect] = useState<PaperDetection | null>(null)
  const [warpedUrl, setWarpedUrl] = useState<string>()
  const [debugUrl, setDebugUrl] = useState<string>()
  const [detecting, setDetecting] = useState(false)
  const [detectError, setDetectError] = useState<string | null>(null)
  // 防止并发/StrictMode 下重复检测
  const runningRef = useRef(false)

  // store 中的图片 URL 变化时同步本地状态并清空旧结果
  useEffect(() => {
    if (storedImageUrl) {
      setImgUrl(storedImageUrl)
      setDetect(null)
      setWarpedUrl(undefined)
      setDebugUrl(undefined)
      setDetectError(null)
    }
  }, [storedImageUrl])

  // 自动检测：图片就绪后自动跑，无需点击
  const runDetection = useCallback(() => {
    if (!cv || !loaded || !imgUrl || runningRef.current) return
    runningRef.current = true
    setDetecting(true)
    setDetectError(null)

    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => {
      try {
        const result = detectPaperCorners(cv, img)
        setDetect(result)
        if (!result) {
          setDetectError('未检测到纸张，请调整光线/角度后重新上传，或点击"重新检测"')
        }
      } catch (err: any) {
        console.error('[CalibrationPage] detectPaperCorners threw:', err)
        setDetectError(err?.message || '检测失败')
      } finally {
        setDetecting(false)
        runningRef.current = false
      }
    }
    img.onerror = () => {
      setDetecting(false)
      runningRef.current = false
      setDetectError('图片加载失败，请重新上传')
    }
    img.src = imgUrl
  }, [cv, loaded, imgUrl])

  // 图片/OpenCV 就绪即自动触发检测
  useEffect(() => {
    if (imgUrl && loaded && cv) runDetection()
  }, [imgUrl, loaded, cv, runDetection])

  // 上传（页内也允许换图）
  const handleUpload = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setImgUrl(URL.createObjectURL(file))
    setDetect(null)
    setWarpedUrl(undefined)
    setDebugUrl(undefined)
    setDetectError(null)
  }, [])

  // 透视校正
  const handleWarp = useCallback(() => {
    if (!cv || !imgUrl || !detect) return
    const img = new Image()
    img.src = imgUrl
    img.onload = () => {
      const { warpedUrl: w } = perspectiveWarp(cv, img, detect.corners)
      setWarpedUrl(w)
    }
  }, [cv, imgUrl, detect])

  // 提取工具轮廓
  const handleExtract = useCallback(async () => {
    if (!cv || !warpedUrl) return
    const result: any = await extractToolContours(cv, warpedUrl, 300)
    setDebugUrl(result.debugUrl)
  }, [cv, warpedUrl])

  if (!loaded) return (
    <div className="p-8">
      <p className="text-lg">加载OpenCV中...</p>
      {error && (
        <p className="mt-3 text-red-600 whitespace-pre-wrap">⚠️ {error}</p>
      )}
    </div>
  )

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <h1 className="text-2xl font-bold mb-2">纸张校准 & 轮廓检测</h1>
      <p className="mb-4 text-gray-600">
        导入照片后系统会自动识别 A4 纸，无需手动调整参数。
      </p>

      <div className="flex gap-4 mb-6 flex-wrap items-center">
        <input type="file" accept="image/*" onChange={handleUpload} />
        <Button onClick={runDetection} disabled={!imgUrl || detecting}>
          {detecting ? '识别中…' : '重新检测'}
        </Button>
        <Button onClick={handleWarp} disabled={!detect}>2. 透视校正</Button>
        <Button onClick={handleExtract} disabled={!warpedUrl}>3. 提取工具轮廓</Button>
      </div>

      {detecting && <p className="mb-4 text-blue-600">正在自动识别纸张…</p>}
      {!detecting && detectError && (
        <p className="mb-4 text-red-600 whitespace-pre-wrap">⚠️ {detectError}</p>
      )}
      {!detecting && !detectError && detect && (
        <>
          <p className="mb-2 text-green-600">
            ✅ 已自动识别纸张四角（
            {detect.mode === "strong"
              ? "首轮强命中"
              : `${detect.methodCount} 个方法族共识`}
            ，置信度 {Math.round(detect.confidence * 100)}%）
          </p>
          {detect.skew.message && (
            <p
              className={`mb-2 whitespace-pre-wrap ${
                detect.skew.level === 'severe' ? 'text-red-600' : 'text-amber-600'
              }`}
            >
              {detect.skew.message}
            </p>
          )}
          {detect.lowConfidence && (
            <p className="mb-2 text-amber-500">
              ⚠️ 仅单方法命中，结果仅供参考，建议重新拍摄确认。
            </p>
          )}
        </>
      )}

      <div className="grid grid-cols-2 gap-8">
        {imgUrl && (
          <div>
            <h3 className="font-medium mb-2">原图</h3>
            <img src={imgUrl} className="max-w-full border rounded" />
          </div>
        )}
        {detect && (
          <div>
            <h3 className="font-medium mb-2">A4四角坐标</h3>
            <div className="text-sm space-y-1">
              <p>左上: ({detect.corners[0].x}, {detect.corners[0].y})</p>
              <p>右上: ({detect.corners[1].x}, {detect.corners[1].y})</p>
              <p>右下: ({detect.corners[2].x}, {detect.corners[2].y})</p>
              <p>左下: ({detect.corners[3].x}, {detect.corners[3].y})</p>
            </div>
          </div>
        )}
        {warpedUrl && (
          <div>
            <h3 className="font-medium mb-2">校正后A4图</h3>
            <img src={warpedUrl} className="max-w-full border rounded" />
          </div>
        )}
        {debugUrl && (
          <div>
            <h3 className="font-medium mb-2">轮廓提取结果</h3>
            <img src={debugUrl} className="max-w-full border rounded" />
          </div>
        )}
      </div>
    </div>
  )
}
