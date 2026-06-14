/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Lush "soccer field" turf palette
        turf: {
          50: '#E8F5E9',
          100: '#C8E6C9',
          200: '#A5D6A7',
          400: '#4CAF50',
          600: '#2E7D32',
          800: '#1B5E20',
          900: '#0E3D14',
        },
        // World Cup 2026 brand accent pops
        wc: {
          lime: '#9BE800',
          purple: '#6D28D9',
          red: '#E0003C',
          blue: '#2563EB',
          gold: '#E8C547',
        },
      },
      fontFamily: {
        display: ['"Archivo Black"', 'system-ui', 'sans-serif'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        card: '0 6px 24px -8px rgba(27, 94, 32, 0.25)',
        pill: '0 10px 30px -6px rgba(14, 61, 20, 0.35)',
      },
      keyframes: {
        floaty: { '0%,100%': { transform: 'translateY(0)' }, '50%': { transform: 'translateY(-6px)' } },
      },
      animation: { floaty: 'floaty 5s ease-in-out infinite' },
    },
  },
  plugins: [],
}
