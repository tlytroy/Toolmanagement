import React from 'react';
import { render, screen } from '@testing-library/react';
import { CalibrationPage } from '../src/features/calibration/CalibrationPage';

// Mock the store
jest.mock('../src/app/store', () => ({
  useStore: jest.fn(() => ({
    step: 'calibration',
    setStep: jest.fn(),
    imageUrl: null,
    calibratedImageUrl: null,
    setCalibratedImageUrl: jest.fn(),
  })),
}));

// Mock the PaperDetector
jest.mock('../src/utils/PaperDetector', () => {
  return {
    PaperDetector: jest.fn().mockImplementation(() => {
      return {
        init: jest.fn(),
        detectPaperCorners: jest.fn(),
        applyPerspectiveCorrection: jest.fn(),
        calculatePixelRatio: jest.fn(),
      };
    }),
  };
});

describe('CalibrationPage', () => {
  test('should render without crashing', () => {
    render(<CalibrationPage />);
    expect(screen.getByText('纸张检测与标定')).toBeInTheDocument();
  });

  test('should have manual adjustment controls', () => {
    render(<CalibrationPage />);
    expect(screen.getByText('手动调整边界')).toBeInTheDocument();
  });
});