/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          'Inter',
          'system-ui',
          '-apple-system',
          'PingFang SC',
          'Microsoft YaHei',
          'sans-serif',
        ],
      },
      colors: {
        brand: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
        },
        // 深色画布 / 玻璃面板基调（对标 Figma / Tooltrace 暗色 viewport）
        canvas: {
          DEFAULT: '#0a0a0b',
          950: '#0a0a0b',
          900: '#111113',
          850: '#16161a',
          800: '#1c1c21',
          700: '#27272e',
          600: '#3a3a42',
        },
      },
      boxShadow: {
        card: '0 1px 3px 0 rgba(15, 23, 42, 0.04), 0 8px 24px -8px rgba(15, 23, 42, 0.10)',
        'card-hover': '0 4px 12px 0 rgba(15, 23, 42, 0.06), 0 18px 40px -12px rgba(15, 23, 42, 0.18)',
      },
      borderRadius: {
        '2xl': '1rem',
        '3xl': '1.5rem',
      },
      keyframes: {
        'fade-in': {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'fade-in-slow': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
      },
      animation: {
        'fade-in': 'fade-in 0.45s cubic-bezier(0.22, 1, 0.36, 1) both',
        'fade-in-slow': 'fade-in-slow 0.6s ease-out both',
        'slide-in-right': 'slide-in-right 0.4s cubic-bezier(0.22, 1, 0.36, 1) both',
        'slide-down': 'slide-down 0.35s cubic-bezier(0.22, 1, 0.36, 1) both',
      },
      keyframes: {
        'slide-in-right': {
          '0%': { opacity: '0', transform: 'translateX(16px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        'slide-down': {
          '0%': { opacity: '0', transform: 'translateY(-8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
}
