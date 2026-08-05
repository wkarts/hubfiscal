import { readFileSync } from 'node:fs'
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

const packageJson = JSON.parse(
  readFileSync(new URL('./package.json', import.meta.url), 'utf8'),
) as { version: string }

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const version = env.VITE_APP_VERSION || packageJson.version
  const buildSha = env.VITE_BUILD_SHA || 'development'
  const buildDate = env.VITE_BUILD_DATE || 'unknown'

  return {
    plugins: [vue()],
    define: {
      __APP_VERSION__: JSON.stringify(version),
      __BUILD_SHA__: JSON.stringify(buildSha),
      __BUILD_DATE__: JSON.stringify(buildDate),
    },
    server: {
      port: 3000,
      proxy: {
        '/api': { target: 'http://hubfiscal-api:8080', changeOrigin: true },
        '/docs': { target: 'http://hubfiscal-api:8080', changeOrigin: true },
        '/openapi.json': { target: 'http://hubfiscal-api:8080', changeOrigin: true },
      },
    },
  }
})
