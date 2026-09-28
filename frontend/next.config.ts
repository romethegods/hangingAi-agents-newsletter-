import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  cacheComponents: true,
  async redirects() {
    // The scraper's user agent points site owners at hangingai.com/bot.
    return [{ source: "/bot", destination: "/about#crawler", permanent: true }];
  },
};

export default nextConfig;
