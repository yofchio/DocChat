import path from "path";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiTarget =
    process.env.API_BASE_URL ||
    env.API_BASE_URL ||
    `http://${process.env.API_HOST || env.API_HOST || "127.0.0.1"}:${process.env.API_PORT || env.API_PORT || "5055"}`;

  const apiProxy = {
    "/api": {
      target: apiTarget,
      changeOrigin: true,
    },
  };

  return {
    plugins: [react()],
    resolve: {
      alias: { "@": path.resolve(__dirname, "./src") },
    },
    server: {
      port: 3000,
      proxy: apiProxy,
    },
    preview: {
      port: Number(process.env.PORT) || 3000,
      strictPort: false,
      host: true,
      // Railway (and other tunnels) send a non-local Host header; Vite 6 blocks it unless listed.
      allowedHosts: [".up.railway.app", "localhost", "127.0.0.1"],
      proxy: apiProxy,
    },
  };
});
