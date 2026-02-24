import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      '/discussions/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
      '/rooms/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
})
