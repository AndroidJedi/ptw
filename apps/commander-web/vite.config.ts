import { readFileSync, readdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { loadEnv } from 'vite'
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const liveProduction = env.VITE_LIVE_PRODUCTION === 'true'
  return {
    plugins: [react(), {
      name: 'landing-font-licenses',
      generateBundle() {
        const root = new URL('../../validation_pipeline/studio_assets/fonts/', import.meta.url)
        for (const name of readdirSync(root).filter(name => name.startsWith('OFL-'))) {
          this.emitFile({ type: 'asset', fileName: `font-licenses/${name}`, source: readFileSync(new URL(name, root), 'utf8') })
        }
        this.emitFile({ type: 'asset', fileName: 'font-licenses/OFL-Inter.txt', source: readFileSync(new URL('../../natal/assets/OFL-Inter.txt', import.meta.url), 'utf8') })
      },
    }],
    server: {
      port: 5173,
      fs: { allow: [
        fileURLToPath(new URL('.', import.meta.url)),
        fileURLToPath(new URL('../../validation_pipeline/studio_assets/fonts', import.meta.url)),
        fileURLToPath(new URL('../../natal/assets/inter.ttf', import.meta.url)),
      ] },
      proxy: liveProduction ? {
        '/api/v1/studio': 'http://127.0.0.1:8088',
        '/api': { target: 'https://commander.proove-them-wrong.com', changeOrigin: true, secure: true },
      } : { '/api': 'http://127.0.0.1:8088' },
    },
    test: { environment: 'jsdom', setupFiles: './src/test-setup.ts', exclude: ['e2e/**', 'node_modules/**'] },
  }
})
