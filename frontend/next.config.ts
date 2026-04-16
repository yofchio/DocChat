import type { NextConfig } from "next";

// Resolve the backend origin for both local runs and Docker-based development.
const apiOrigin =
  process.env.API_BASE_URL ||
  `http://${process.env.API_HOST || "127.0.0.1"}:${process.env.API_PORT || "5055"}`;

const nextConfig: NextConfig = {
  devIndicators: false,
  async rewrites() {
    return {
      beforeFiles: [],
      afterFiles: [],
      fallback: [
        {
          // Proxy browser-side `/api/*` requests to FastAPI so the frontend
          // can use relative paths without dealing with CORS directly.
          source: "/api/:path*",
          destination: `${apiOrigin}/api/:path*`,
        },
      ],
    };
  },
};

export default nextConfig;
