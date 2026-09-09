import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const isRelease = process.env.NFL_VIDEO_INTEL_RELEASE === '1';

export default defineConfig({
  root: 'source',
  base: './',
  publicDir: '../public',
  plugins: [react()],
  build: {
    outDir: isRelease ? '../.release-dist' : '../preview-dist',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        entryFileNames: 'assets/app.js',
        chunkFileNames: 'assets/[name].js',
        assetFileNames: ({ names }) => names?.some((name) => name.endsWith('.css')) ? 'assets/app.css' : 'assets/[name][extname]',
      },
    },
  },
  server: {
    host: '127.0.0.1',
    port: 4173,
  },
});
