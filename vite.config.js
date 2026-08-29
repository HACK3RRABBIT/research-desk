import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The webui lives in webui/ but the package manifest is at the repo root, so
// this config points Vite at the real app root. `npm run build` therefore emits
// into webui/dist, which research_desk/server.py mounts.
export default defineConfig({
  root: 'webui',
  plugins: [react()],
  server: { host: '0.0.0.0', port: 5173 },
  build: { outDir: 'dist', emptyOutDir: true },
});
