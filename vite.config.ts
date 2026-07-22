import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    outDir: "dist",
  },
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        // DO NOT set changeOrigin: true — FastAPI's CSRF check compares the
        // Origin header against the Host header it receives. With changeOrigin,
        // the Host becomes localhost:8000, which won't match the browser's
        // Origin (localhost:3000 or 5173), causing silent 403s on all mutating
        // requests (mark-read, refresh, settings, console backup, etc.).
      },
    },
  },
});
