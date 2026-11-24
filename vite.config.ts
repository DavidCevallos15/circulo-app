import { readFileSync } from 'node:fs';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const packageMeta = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf-8')) as {
  version?: string;
};

export default defineConfig({
  base: './',
  plugins: [react()],
  root: '.',
  define: {
    __APP_VERSION__: JSON.stringify(packageMeta.version || '0.4.0'),
  },
  // assetsInlineLimit 0: nada de data: URIs (fuentes incluidas), compatible con font-src 'self' del CSP de davidcevallos.me.
  build: { outDir: 'dist', emptyOutDir: true, assetsInlineLimit: 0 },
  server: { proxy: { '/api': 'http://127.0.0.1:8765' } },
});
