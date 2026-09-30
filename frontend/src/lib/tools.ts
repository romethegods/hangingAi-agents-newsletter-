import { compactNumber } from "./format";
import type { DemoKind, Tool } from "./types";

const YOUTUBE_EMBED = /youtube-nocookie\.com\/embed\/([\w-]{11})/;

/**
 * Card/poster image: an owner-uploaded preview (or HF Space thumbnail), else the
 * YouTube demo's own thumbnail, else null (the caller shows our ToolPoster).
 * GitHub's generated cards only repeat the repo name, so they're never used.
 */
export function previewImage(tool: Tool): string | null {
  const preview = tool.preview_image_url;
  if (preview && !preview.includes("opengraph.githubassets.com")) return preview;
  const youtube = tool.demo_kind === "embed" ? tool.demo_url?.match(YOUTUBE_EMBED) : null;
  return youtube ? `https://i.ytimg.com/vi/${youtube[1]}/hqdefault.jpg` : null;
}

export function displayName(tool: Tool): string {
  return tool.title ?? tool.full_name.split("/")[1] ?? tool.full_name;
}

/** Stars for GitHub repos, likes for Hugging Face Spaces. */
export function popularity(tool: Tool): string {
  const n = compactNumber(tool.stars);
  return tool.platform === "huggingface" ? `♥ ${n}` : `★ ${n}`;
}

export const PLATFORM_LABEL: Record<Tool["platform"], string> = {
  github: "GitHub repo",
  huggingface: "Hugging Face Space",
};

export const DEMO_LABEL: Record<DemoKind, string> = {
  video: "▶ Video demo",
  embed: "▶ Video demo",
  gif: "▶ GIF demo",
  image: "Screenshot",
  app: "▶ Live app",
};

/** The demo kinds worth a "watch" call to action (screenshots aren't). */
export function hasPlayableDemo(tool: Tool): boolean {
  return tool.demo_kind !== null && tool.demo_kind !== "image";
}
