/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        police: {
          900: '#0a0f1d',
          800: '#0f172a',
          700: '#1e293b',
          600: '#334155',
          accent: '#00f0ff',
          alert: '#ef4444',
          warning: '#f59e0b',
          terminal: '#a855f7',
          success: '#10b981',
        },
      },
    },
  },
  plugins: [],
}
