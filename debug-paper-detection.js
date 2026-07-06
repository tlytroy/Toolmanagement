// 简单的调试脚本，用于测试纸张检测功能
import fs from 'fs';
import path from 'path';

// 模拟浏览器环境中的部分API
global.HTMLImageElement = class {};
global.document = {
  createElement: (tag) => {
    if (tag === 'canvas') {
      return {
        width: 0,
        height: 0,
        getContext: () => null,
        toDataURL: () => 'data:image/jpeg;base64,test'
      };
    }
    return {};
  }
};

console.log('PaperDetector debugging script');

// 尝试动态导入编译后的模块
try {
  const modulePath = './dist/utils/PaperDetector.js';
  console.log('Checking if module exists:', fs.existsSync(modulePath));

  // 注意：由于OpenCV依赖和浏览器API，在Node.js环境中很难完整测试
  console.log('Note: Full testing requires browser environment due to OpenCV.js dependencies');
} catch (error) {
  console.error('Error in debug script:', error.message);
}

console.log('Debug script completed');