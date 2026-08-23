import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The API is a separate process in development. Proxying rather than enabling
// CORS keeps the browser same-origin, so `fetch` paths stay relative and
// production needs no CORS middleware either.
const API = process.env.MEDIASAGE_API_URL ?? 'http://localhost:5765'

export default defineConfig({
  plugins: [react()],
  css: {
    preprocessorOptions: {
      // So a module at any depth writes `@use 'mixins'` rather than counting
      // `../` back to the design system.
      scss: { loadPaths: ['src/design-system'] },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': { target: API, changeOrigin: true },
    },
  },
})
