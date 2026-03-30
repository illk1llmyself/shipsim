import { fileURLToPath, URL } from "node:url";

import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  base: "/static/",
  build: {
    outDir: fileURLToPath(new URL("../shipsim/web", import.meta.url)),
    emptyOutDir: true,
    assetsDir: "",
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/health": "http://127.0.0.1:8000",
      "/simulation": "http://127.0.0.1:8000",
      "/fleet": "http://127.0.0.1:8000",
      "/telemetry": "http://127.0.0.1:8000",
      "/ws": {
        target: "ws://127.0.0.1:8000",
        ws: true,
      },
    },
  },
});
