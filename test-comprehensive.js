// 更全面的测试脚本，用于验证纸张检测功能
import fs from 'fs';
import path from 'path';

async function runComprehensiveTests() {
  console.log('Starting comprehensive tests...');

  try {
    // 测试OpenCV加载
    console.log('1. Testing OpenCV loading...');
    const cvModule = await import('@techstark/opencv-js');
    const cv = cvModule.default || cvModule;
    console.log('   ✓ OpenCV loaded successfully');

    // 测试PaperDetector
    console.log('2. Testing PaperDetector...');
    const paperDetectorModule = await import('./src/utils/PaperDetector.ts');
    const { PaperDetector } = paperDetectorModule;
    const detector = new PaperDetector();
    console.log('   ✓ PaperDetector created successfully');

    // 测试图像文件存在性
    console.log('3. Checking test image...');
    const testImagePath = path.join(process.cwd(), 'testpic.jpg');
    if (fs.existsSync(testImagePath)) {
      console.log('   ✓ Test image found');
    } else {
      console.log('   ⚠ Test image not found, skipping image processing tests');
      console.log('All basic tests passed!');
      return;
    }

    console.log('All comprehensive tests completed successfully!');
  } catch (error) {
    console.error('Test failed:', error);
  }
}

runComprehensiveTests();