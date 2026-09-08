import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  resolve: { dedupe: ['react', 'react-dom'] },
  plugins: [react(), {
    name: 'natal-public-asset-integrity',
    buildStart() {
      const logo = readFileSync(new URL('../../natal/assets/logo-natal.png', import.meta.url))
      if (createHash('sha256').update(logo).digest('hex') !== 'f465a0e11be3c1ff1943bcc1bcd19246a9a54957fd5c1c6162081aec9a59c8ba') throw new Error('Canonical Natal logo digest mismatch')
    },
  }],
  server: {
    port: 5174,
    fs: { allow: [fileURLToPath(new URL('../..', import.meta.url))] },
    proxy: { '/api': 'http://127.0.0.1:8088' },
  },
  test: { environment: 'jsdom', setupFiles: './src/test-setup.ts', exclude: ['e2e/**', 'node_modules/**'] },
})
