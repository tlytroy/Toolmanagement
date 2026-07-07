// 简单的OpenCV.js测试
import * as cv from '@techstark/opencv-js';

export async function testOpenCVImport() {
  console.log('Testing OpenCV.js import...');

  // 检查cv对象
  console.log('cv type:', typeof cv);
  console.log('cv keys:', Object.keys(cv).slice(0, 10));

  // 检查关键方法
  console.log('cv.imread exists:', typeof cv.imread);
  console.log('cv.Mat exists:', typeof cv.Mat);

  // 等待初始化（如果需要）
  // 注意：我们不能直接修改只读属性onRuntimeInitialized
  // 而是应该等待它自然触发或检查OpenCV是否已经准备好

  // 测试基本功能
  try {
    // 检查OpenCV是否已经初始化
    if (typeof cv.Mat === 'function') {
      const mat = new cv.Mat(10, 10, cv.CV_8UC1);
      console.log('Mat creation successful');
      mat.delete();
      console.log('Mat deletion successful');
      return true;
    } else {
      console.log('cv.Mat is not a function - OpenCV may not be ready yet');

      // 尝试等待一段时间看是否初始化完成
      await new Promise(resolve => setTimeout(resolve, 1000));

      if (typeof cv.Mat === 'function') {
        const mat = new cv.Mat(10, 10, cv.CV_8UC1);
        console.log('Mat creation successful after wait');
        mat.delete();
        console.log('Mat deletion successful');
        return true;
      }

      return false;
    }
  } catch (error) {
    console.error('OpenCV test failed:', error);
    return false;
  }
}