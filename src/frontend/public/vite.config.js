import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

// `base: './'` keeps the built asset paths relative, so FastAPI can mount `dist/` at any prefix.
// The dev proxy lets `npm run dev` on port 5173 reach a backend on 8000 without CORS handling;
// in the built app the page and the API share one origin, so no proxy is involved.
export default defineConfig({
  plugins: [svelte()],
  base: './',
  build: { outDir: 'dist', emptyOutDir: true },
  server: {
    proxy: {
      '/v1': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
    },
  },
});
