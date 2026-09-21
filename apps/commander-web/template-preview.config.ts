import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'
export default defineConfig({
  root: fileURLToPath(new URL('./template-preview', import.meta.url)),
  plugins: [react()],
  build: { outDir: '../../../.local/template-preview', emptyOutDir: true },
})
