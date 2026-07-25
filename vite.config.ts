import { readFileSync } from 'node:fs'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

const packageMetadata = JSON.parse(
  readFileSync(new URL('./package.json', import.meta.url), 'utf8'),
) as { version?: unknown }

if (typeof packageMetadata.version !== 'string') {
  throw new Error('package.json must define a string version')
}

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/gdpval-realworks/',
  define: {
    __APP_VERSION__: JSON.stringify(packageMetadata.version),
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})
