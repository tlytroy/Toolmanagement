import { useState, useCallback, useEffect } from 'react'
import { useOpenCV } from '@/hooks/useOpenCV'
import { useStore } from '@/app/store'
import { detectPaperCorners, perspectiveWarp, extractToolContours } from '@/lib/opencvUtils'
import { Button } from '@/components/ui/Button'

export default function CalibrationPage() {
  const { cv, loaded } = useOpenCV()
  const storedImageUrl = useStore((s) => s.imageUrl)
  // 调试参数（全放这，不用散在各个文件）
  const [cannyLow, setCannyLow] = useState(80)
  const [cannyHigh, setCannyHigh] = useState(220)
  const [blurSize, setBlurSize] = useState(7)
  const [minArea, setMinArea] = useState(500)
  // 状态
  const [imgUrl, setImgUrl] = useState<string>()
  const [corners, setCorners] = useState<any[] | null>(null)
  const [warpedUrl, setWarpedUrl] = useState<string>()
  const [debugUrl, setDebugUrl] = useState<string>()

  // 当存储中的图片URL变化时，同步到本地状态
  useEffect(() => {
    if (storedImageUrl) {
      setImgUrl(storedImageUrl)
      // 重置处理状态
      setCorners(null)
      setWarpedUrl(undefined)
      setDebugUrl(undefined)
    }
  }, [storedImageUrl])

  // 上传图片
  const handleUpload = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setImgUrl(URL.createObjectURL(file))
    // 重置状态
    setCorners(null)
    setWarpedUrl(undefined)
    setDebugUrl(undefined)
  }, [])

  // 检测A4纸（带调试参数）
  const handleDetectPaper = useCallback(() => {
    // 防御1：校验OpenCV是否完全加载
    if (!cv || !loaded) {
      alert('OpenCV还在加载中，请稍后再试')
      return
    }
    // 防御2：显式校验imread方法是否存在（避免cv对象残缺）
    if (typeof cv.imread !== 'function') {
      alert('OpenCV加载异常，请刷新页面重试')
      console.error('cv.imread不存在，当前cv对象：', cv)
      return
    }
    if (!imgUrl) return

    const img = new Image()
    img.crossOrigin = 'anonymous' // 解决跨域导致的canvas污染问题
    img.src = imgUrl

    // 关键：必须等图片完全加载后才能调用cv.imread
    img.onload = () => {
      try {
        const corners = detectPaperCorners(cv, img, {
          cannyLow,
          cannyHigh,
          blurSize,
        })
        setCorners(corners)
      } catch (err: any) {
        alert(err.message)
      }
    }
    img.onerror = () => {
      alert('图片加载失败，请重新上传')
    }
  }, [cv, loaded, imgUrl, cannyLow, cannyHigh, blurSize])

  // 透视校正
  const handleWarp = useCallback(() => {
    if (!cv || !imgUrl || !corners) return
    const img = new Image()
    img.src = imgUrl
    img.onload = () => {
      const { warpedUrl } = perspectiveWarp(cv, img, corners)
      setWarpedUrl(warpedUrl)
    }
  }, [cv, imgUrl, corners])

  // 提取工具轮廓
  const handleExtract = useCallback(async () => {
    if (!cv || !warpedUrl) return
    const result: any = await extractToolContours(cv, warpedUrl, minArea)
    const { debugUrl } = result
    setDebugUrl(debugUrl)
  }, [cv, warpedUrl, minArea])

  if (!loaded) return <div className="p-8">加载OpenCV中...</div>

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">纸张校准 & 轮廓检测调试</h1>

      {/* 调试参数区（所有调参都在这，不用翻文件） */}
      <div className="grid grid-cols-4 gap-4 mb-8 p-4 bg-gray-50 rounded-lg">
        <div>
          <label className="block text-sm mb-1">Canny低阈值: {cannyLow}</label>
          <input
            type="range"
            min="30"
            max="150"
            value={cannyLow}
            onChange={(e) => setCannyLow(Number(e.target.value))}
            className="w-full"
          />
        </div>
        <div>
          <label className="block text-sm mb-1">Canny高阈值: {cannyHigh}</label>
          <input
            type="range"
            min="150"
            max="300"
            value={cannyHigh}
            onChange={(e) => setCannyHigh(Number(e.target.value))}
            className="w-full"
          />
        </div>
        <div>
          <label className="block text-sm mb-1">模糊核大小: {blurSize}</label>
          <input
            type="range"
            min="3"
            max="15"
            step="2"
            value={blurSize}
            onChange={(e) => setBlurSize(Number(e.target.value))}
            className="w-full"
          />
        </div>
        <div>
          <label className="block text-sm mb-1">最小轮廓面积: {minArea}</label>
          <input
            type="range"
            min="100"
            max="2000"
            value={minArea}
            onChange={(e) => setMinArea(Number(e.target.value))}
            className="w-full"
          />
        </div>
      </div>

      {/* 操作区 */}
      <div className="flex gap-4 mb-8">
        <input type="file" accept="image/*" onChange={handleUpload} />
        <Button onClick={handleDetectPaper} disabled={!imgUrl}>1. 检测A4纸</Button>
        <Button onClick={handleWarp} disabled={!corners}>2. 透视校正</Button>
        <Button onClick={handleExtract} disabled={!warpedUrl}>3. 提取工具轮廓</Button>
      </div>

      {/* 预览区 */}
      <div className="grid grid-cols-2 gap-8">
        {imgUrl && (
          <div>
            <h3 className="font-medium mb-2">原图</h3>
            <img src={imgUrl} className="max-w-full border rounded" />
          </div>
        )}
        {corners && (
          <div>
            <h3 className="font-medium mb-2">A4四角坐标</h3>
            <div className="text-sm space-y-1">
              <p>左上: ({corners[0].x}, {corners[0].y})</p>
              <p>右上: ({corners[1].x}, {corners[1].y})</p>
              <p>右下: ({corners[2].x}, {corners[2].y})</p>
              <p>左下: ({corners[3].x}, {corners[3].y})</p>
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