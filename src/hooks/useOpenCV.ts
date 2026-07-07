import { useState, useEffect } from 'react';
import { loadCv } from '@/lib/opencvLoader';

/**
 * React hook：等待 OpenCV.js 就绪。
 *
 * opencv.js 由 index.html 的 <script> 标签以 UMD 形式加载，挂到 window.cv。
 * 本 hook 复用 @/lib/opencvLoader 的 loadCv() 来解析出真正的 cv 实例。
 */
export const useOpenCV = () => {
  const [cv, setCv] = useState<any>(null);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    const init = async () => {
      try {
        const cvInstance = await loadCv();
        if (!active) return;
        console.log('✅ OpenCV.js loaded successfully, cv.imread:', typeof cvInstance.imread);
        setCv(cvInstance);
        setLoaded(true);
      } catch (err) {
        console.error('❌ Failed to load OpenCV.js:', err);
        if (active) {
          setError(
            'OpenCV 加载失败: ' + (err instanceof Error ? err.message : String(err)),
          );
          setLoaded(false);
        }
      }
    };

    init();

    return () => {
      active = false;
    };
  }, []);

  return { cv, loaded, error };
};
