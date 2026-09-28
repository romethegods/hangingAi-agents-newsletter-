import type { MetadataRoute } from "next";

const SITE_URL = process.env.SITE_URL ?? "https://hangingai.com";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/", disallow: "/search" },
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
