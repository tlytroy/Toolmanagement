// 简单的测试脚本来验证OpenCV和PaperDetector功能
async function runTests() {
  console.log('Starting tests...');

  try {
    // 测试OpenCV加载
    console.log('Testing OpenCV loading...');
    const cvModule = await import('@techstark/opencv-js');
    const cv = cvModule.default || cvModule;
    console.log('OpenCV loaded successfully');
    console.log('OpenCV version:', cv.getVersionString?.() || 'Unknown');

    // 测试PaperDetector
    console.log('Testing PaperDetector...');
    const paperDetectorModule = await import('./src/utils/PaperDetector.ts');
    const { PaperDetector } = paperDetectorModule;
    const detector = new PaperDetector();
    console.log('PaperDetector created successfully');

    console.log('All tests passed!');
  } catch (error) {
    console.error('Test failed:', error);
  }
}

runTests();