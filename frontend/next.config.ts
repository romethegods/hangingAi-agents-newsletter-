import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  cacheComponents: true,
  // Third-party thumbnails and demos load straight from their source. We never
  // proxy or cache other people's media on our server (no re-hosting, and no
  // image-optimizer bandwidth on the VM).
  images: { unoptimized: true },
  async redirects() {
    // The scraper's user agent points site owners at hangingai.com/bot.
    return [{ source: "/bot", destination: "/about#crawler", permanent: true }];
  },
};

export default nextConfig;
