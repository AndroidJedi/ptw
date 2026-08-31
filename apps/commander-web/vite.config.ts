import { loadEnv } from 'vite'
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const liveProduction = env.VITE_LIVE_PRODUCTION === 'true'
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: liveProduction ? {
        '/api/v1/studio': 'http://127.0.0.1:8088',
        '/api': { target: 'https://commander.proove-them-wrong.com', changeOrigin: true, secure: true },
      } : { '/api': 'http://127.0.0.1:8088' },
    },
    test: { environment: 'jsdom', setupFiles: './src/test-setup.ts', exclude: ['e2e/**', 'node_modules/**'] },
  }
})
