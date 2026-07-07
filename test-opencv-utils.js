// 测试 opencvUtils.ts 中的函数
async function testOpenCVUtils() {
  console.log('Testing opencvUtils functions...');

  try {
    // 测试OpenCV加载
    console.log('1. Loading OpenCV...');
    const cvModule = await import('@techstark/opencv-js');
    const cv = cvModule.default || cvModule;
    console.log('   ✓ OpenCV loaded successfully');

    // 测试opencvUtils函数导入
    console.log('2. Testing opencvUtils imports...');
    const opencvUtilsModule = await import('./src/lib/opencvUtils.ts');
    const { detectPaperCorners, perspectiveWarp, extractToolContours } = opencvUtilsModule;
    console.log('   ✓ opencvUtils functions imported successfully');
    console.log('   - detectPaperCorners:', typeof detectPaperCorners);
    console.log('   - perspectiveWarp:', typeof perspectiveWarp);
    console.log('   - extractToolContours:', typeof extractToolContours);

    console.log('All opencvUtils tests passed!');
  } catch (error) {
    console.error('Test failed:', error);
  }
}

testOpenCVUtils();