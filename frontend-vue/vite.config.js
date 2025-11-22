import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      // Proxy API requests to the backend
      '/api': {
        target: 'http://localhost:8888',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: '../frontend-dist',
    emptyOutDir: true,
  },
})
