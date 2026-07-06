import { PaperDetector } from '../src/utils/PaperDetector';

describe('PaperDetector Improvements', () => {
  let detector: PaperDetector;

  beforeEach(() => {
    detector = new PaperDetector();
  });

  test('should create instance without errors', () => {
    expect(detector).toBeTruthy();
  });

  test('should have detectPaperCorners method', () => {
    expect(typeof (detector as any).detectPaperCorners).toBe('function');
  });

  test('should have applyPerspectiveCorrection method', () => {
    expect(typeof (detector as any).applyPerspectiveCorrection).toBe('function');
  });

  test('should have shapeRegularity method', () => {
    expect(typeof (detector as any).shapeRegularity).toBe('function');
  });
});