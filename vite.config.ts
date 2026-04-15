import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import tailwindcss from "@tailwindcss/vite";

// Port 錯開：DefectAiDoctor 用 5173 / 5487，這裡用 5174 / 5488。
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5174,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:5488",
        changeOrigin: true,
      },
    },
  },
});
