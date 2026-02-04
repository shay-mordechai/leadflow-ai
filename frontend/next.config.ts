import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  output: "standalone",

  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://127.0.0.1:8000/api/:path*',
      },
      {
        source: '/webhooks/:path*',
        destination: 'http://127.0.0.1:8000/webhooks/:path*',
      },
      {
        source: '/docs',
        destination: 'http://127.0.0.1:8000/docs',
      },
      {
        source: '/openapi.json',
        destination: 'http://127.0.0.1:8000/openapi.json',
      }
    ];
  },
};

export default nextConfig;
