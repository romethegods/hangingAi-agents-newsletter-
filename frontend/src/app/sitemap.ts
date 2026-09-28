import type { MetadataRoute } from "next";

const SITE_URL = process.env.SITE_URL ?? "https://hangingai.com";

// Static sections only for now; item pages get discovered through the feed.
// Listing recent /item URLs here is a follow-up once traffic justifies it.
export default function sitemap(): MetadataRoute.Sitemap {
  return [
    { url: `${SITE_URL}/`, changeFrequency: "hourly", priority: 1 },
    { url: `${SITE_URL}/tools`, changeFrequency: "daily", priority: 0.8 },
    { url: `${SITE_URL}/about`, changeFrequency: "monthly", priority: 0.3 },
  ];
}
