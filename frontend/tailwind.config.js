/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        dark: {
          900: '#0B0F17',
          800: '#131926',
          700: '#1D263B',
          600: '#2A3654',
          500: '#3E4E77'
        },
        brand: {
          red: '#E53E3E',
          purple: '#7C3AED',
          cyan: '#06B6D4',
          amber: '#F59E0B'
        }
      }
    },
  },
  plugins: [],
}
