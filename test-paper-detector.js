// 纸张检测器测试脚本
// 用于验证修复后的纸张检测功能

import { PaperDetector } from '../src/utils/PaperDetector';

async function testPaperDetector() {
  console.log('开始测试 PaperDetector...');

  try {
    // 创建检测器实例
    const detector = new PaperDetector();
    console.log('PaperDetector 实例创建成功');

    // 等待初始化完成
    await new Promise(resolve => setTimeout(resolve, 2000));

    if (detector['cv']) {
      console.log('OpenCV.js 初始化成功');
      console.log('PaperDetector 准备就绪');
      return true;
    } else {
      console.log('OpenCV.js 初始化失败');
      return false;
    }
  } catch (error) {
    console.error('测试过程中出现错误:', error);
    return false;
  }
}

// 运行测试
testPaperDetector().then(success => {
  if (success) {
    console.log('PaperDetector 测试通过');
  } else {
    console.log('PaperDetector 测试失败');
  }
});