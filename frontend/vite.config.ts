import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': resolve(__dirname, 'src') },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) {
            return
          }
          if (id.includes('@element-plus/icons-vue')) {
            return 'vendor-icons'
          }
          if (id.includes('element-plus')) {
            return 'vendor-element'
          }
          if (id.includes('pinia') || id.includes('vue-router')) {
            return 'vendor-state'
          }
          if (id.includes('axios')) {
            return 'vendor-network'
          }
          if (id.includes('vue')) {
            return 'vendor-vue'
          }
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
