import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev server on 5173; strictPort so the preview tooling can rely on it.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true, host: true },
})
