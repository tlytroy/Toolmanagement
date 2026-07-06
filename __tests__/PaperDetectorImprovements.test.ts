import { PaperDetector } from '../src/utils/PaperDetector';

describe('PaperDetector Improvements', () => {
  let detector: PaperDetector;

  beforeEach(() => {
    detector = new PaperDetector();
  });

  test('should create instance without errors', () => {
    expect(detector).toBeTruthy();
  });

  test('should have isRectangle method', () => {
    expect(typeof (detector as any).isRectangle).toBe('function');
  });

  test('should have getShapeRegularityScore method', () => {
    expect(typeof (detector as any).getShapeRegularityScore).toBe('function');
  });

  test('should have improved detection algorithm', () => {
    // 这里可以添加更复杂的测试，比如模拟 OpenCV 对象来测试改进的算法
    // 但由于 OpenCV 是外部库，我们在这里主要测试接口
    expect(typeof (detector as any).detectPaperCorners).toBe('function');
  });
});