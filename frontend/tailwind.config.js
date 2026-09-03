/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        brand: {
          dark: '#060911',
          card: 'rgba(14, 22, 39, 0.75)',
          border: 'rgba(255, 255, 255, 0.08)',
          glow: 'rgba(59, 130, 246, 0.25)',
          bull: '#10b981',
          bear: '#f43f5e',
          warn: '#f59e0b',
          accent: '#3b82f6',
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      }
    },
  },
  plugins: [],
}
