import { useState, useEffect } from 'react';
import type { OpenCV } from '@/types/opencv';

export const useOpenCV = () => {
  const [cv, setCv] = useState<OpenCV | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadOpenCV = async () => {
      try {
        // 动态导入OpenCV.js
        const cvModule = await import('@techstark/opencv-js');
        const loadedCv = cvModule.default || cvModule;
        setCv(loadedCv);
        setLoaded(true);
      } catch (err) {
        console.error('Failed to load OpenCV:', err);
        setError('Failed to load OpenCV.js');
        setLoaded(false);
      }
    };

    loadOpenCV();
  }, []);

  return { cv, loaded, error };
};