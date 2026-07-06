import { PaperDetector } from './PaperDetector';

// 创建一个简单的测试函数
async function testPaperDetector() {
  console.log('Starting PaperDetector test...');

  try {
    // 创建 PaperDetector 实例
    const detector = new PaperDetector();

    // 等待初始化完成
    await new Promise(resolve => setTimeout(resolve, 1000));

    console.log('PaperDetector initialized successfully');
    console.log('OpenCV version:', (detector as any).cv.getVersionString?.() || 'Unknown');

    console.log('Test completed successfully!');
  } catch (error) {
    console.error('Test failed:', error);
  }
}

// 运行测试
testPaperDetector();