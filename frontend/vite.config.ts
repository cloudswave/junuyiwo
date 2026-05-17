import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 开发模式后端端口：默认 8000（生产），可设 VITE_BACKEND_PORT=8001 切到开发环境
const backendPort = process.env.VITE_BACKEND_PORT || '8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: `http://127.0.0.1:${backendPort}`,
        changeOrigin: true,
      },
      '/static': {
        target: `http://127.0.0.1:${backendPort}`,
        changeOrigin: true,
      },
    },
  },
  css: {
    preprocessorOptions: {
      less: {
        javascriptEnabled: true,
      },
    },
  },
})
