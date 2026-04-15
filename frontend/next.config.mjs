/** @type {import('next').NextConfig} */
const STATIC = process.env.NEXT_PUBLIC_STATIC_MODE === "true" || process.env.NEXT_PUBLIC_STATIC_MODE === "1";

const nextConfig = {
  reactStrictMode: true,
  // 静的モードでは rewrites 不要。public/api/*.json を Vercel がそのまま配信する。
  async rewrites() {
    if (STATIC) return [];
    return [
      {
        source: "/api/:path*",
        destination: "http://127.0.0.1:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
