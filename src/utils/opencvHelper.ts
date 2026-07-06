// OpenCV.js 测试文件
export class OpenCVHelper {
  static async loadOpenCV() {
    return new Promise((resolve, reject) => {
      if (window.cv && window.cv.Mat) {
        console.log('OpenCV.js already loaded');
        resolve(window.cv);
        return;
      }

      const script = document.createElement('script');
      script.src = '/opencv/opencv.js';
      script.async = true;
      script.onload = () => {
        setTimeout(() => {
          if (window.cv && window.cv.Mat) {
            console.log('OpenCV.js loaded successfully');
            resolve(window.cv);
          } else {
            reject(new Error('Failed to load OpenCV.js'));
          }
        }, 1000);
      };
      script.onerror = () => reject(new Error('Failed to load OpenCV.js script'));
      document.head.appendChild(script);
    });
  }

  static async detectPaperEdges(imageSrc) {
    try {
      const cv = await this.loadOpenCV();

      // 创建图像元素
      const img = new Image();
      img.src = imageSrc;

      // 等待图像加载
      await new Promise((resolve) => {
        img.onload = resolve;
      });

      // 创建画布
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      canvas.width = img.width;
      canvas.height = img.height;

      // 绘制图像到画布
      ctx.drawImage(img, 0, 0);

      // 使用 OpenCV 处理
      const src = cv.imread(canvas);
      const dst = new cv.Mat();

      // 转换为灰度图
      cv.cvtColor(src, src, cv.COLOR_RGBA2GRAY);

      // 高斯模糊
      cv.GaussianBlur(src, src, new cv.Size(5, 5), 0, 0, cv.BORDER_DEFAULT);

      // Canny 边缘检测
      cv.Canny(src, src, 50, 150, 3, false);

      // 查找轮廓
      const contours = new cv.MatVector();
      const hierarchy = new cv.Mat();
      cv.findContours(src, contours, hierarchy, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE);

      // 清理内存
      src.delete();
      dst.delete();
      contours.delete();
      hierarchy.delete();

      console.log('Paper detection completed');
      return { success: true };
    } catch (error) {
      console.error('Error in paper detection:', error);
      return { success: false, error: error.message };
    }
  }
}

// 测试函数
export async function testOpenCV() {
  console.log('Testing OpenCV.js...');

  try {
    const cv = await OpenCVHelper.loadOpenCV();
    console.log('OpenCV version:', cv.getVersionString());
    return true;
  } catch (error) {
    console.error('OpenCV test failed:', error);
    return false;
  }
}