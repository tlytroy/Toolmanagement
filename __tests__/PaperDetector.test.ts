import { PaperDetector } from '../src/utils/PaperDetector';

describe('PaperDetector', () => {
  test('should create instance without errors', () => {
    expect(() => {
      new PaperDetector();
    }).not.toThrow();
  });

  test('should have detectPaperCorners method', () => {
    const detector = new PaperDetector();
    expect(typeof (detector as any).detectPaperCorners).toBe('function');
  });

  test('should have applyPerspectiveCorrection method', () => {
    const detector = new PaperDetector();
    expect(typeof (detector as any).applyPerspectiveCorrection).toBe('function');
  });
});