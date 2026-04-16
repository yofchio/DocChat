import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  devIndicators: false,
  async rewrites() {
    return {
      beforeFiles: [],
      afterFiles: [],
      fallback: [
        {
          source: "/api/:path*",
          destination: `http://api:${process.env.API_PORT || "5055"}/api/:path*`,
        },
      ],
    };
  },
};

export default nextConfig;
