import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: "standalone",
  allowedDevOrigins: [
    "localhost",
    "127.0.0.1",
    "192.168.15.199",
    "100.93.146.98",
  ],
};

export default nextConfig;
