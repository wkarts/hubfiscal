import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3000,
    proxy: {
      '/api': { target: 'http://hubfiscal-api:8080', changeOrigin: true },
      '/docs': { target: 'http://hubfiscal-api:8080', changeOrigin: true },
      '/openapi.json': { target: 'http://hubfiscal-api:8080', changeOrigin: true }
    }
  }
})
