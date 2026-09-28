import type { Article } from "./types";

const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 365 * 24 * 3600],
  ["month", 30 * 24 * 3600],
  ["week", 7 * 24 * 3600],
  ["day", 24 * 3600],
  ["hour", 3600],
  ["minute", 60],
];

const relative = new Intl.RelativeTimeFormat("en", { numeric: "auto", style: "short" });

/** "3 hr. ago", "yesterday". `now` is a parameter so rendering stays deterministic. */
export function timeAgo(iso: string, now: number): string {
  const seconds = Math.round((new Date(iso).getTime() - now) / 1000);
  for (const [unit, size] of UNITS) {
    if (Math.abs(seconds) >= size) return relative.format(Math.trunc(seconds / size), unit);
  }
  return "just now";
}

const compact = new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 });

/** 42444 -> "42.4K" */
export function compactNumber(n: number): string {
  return compact.format(n);
}

export function hostname(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

/** Sources expose different engagement signals; label them honestly. */
export function engagementLabel(article: Pick<Article, "content_type" | "engagement">): string | null {
  if (!article.engagement) return null;
  const n = compactNumber(article.engagement);
  switch (article.content_type) {
    case "paper":
      return `▲ ${n} upvotes`;
    case "model":
      return `♥ ${n} likes`;
    default:
      return null;
  }
}

export const CONTENT_TYPE_LABEL: Record<Article["content_type"], string> = {
  news: "News",
  paper: "Paper",
  model: "Model",
};
