import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 开发时前端跑在 5173，API 跑在 8000；通过 proxy 转发 /api。
// 生产（Docker）由 FastAPI 托管 dist，无需 proxy。
export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
    // ECharts 体积较大，单独拆包避免主 chunk 超过 1MB
    rollupOptions: {
      output: {
        manualChunks: {
          echarts: ["echarts", "echarts-for-react"],
          react: ["react", "react-dom"],
        },
      },
    },
    chunkSizeWarningLimit: 800,
  },
});
