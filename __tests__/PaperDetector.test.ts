import { PaperDetector } from '../src/utils/PaperDetector';

describe('PaperDetector', () => {
  test('should create instance without errors', () => {
    expect(() => {
      new PaperDetector();
    }).not.toThrow();
  });

  test('should have isRectangle method', () => {
    const detector = new PaperDetector();
    expect(typeof (detector as any).isRectangle).toBe('function');
  });

  test('should have getShapeRegularityScore method', () => {
    const detector = new PaperDetector();
    expect(typeof (detector as any).getShapeRegularityScore).toBe('function');
  });
});