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

// Newsletter edition numbering: No. 1 is launch day, counted in New York time
// so the date doesn't flip at 8pm for US readers when the server runs in UTC.
export const LAUNCH_DATE = "2026-09-28";
export const EDITION_TIME_ZONE = "America/New_York";

function calendarDay(now: number, timeZone: string): number {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(now);
  const get = (type: string) => Number(parts.find((p) => p.type === type)?.value);
  return Date.UTC(get("year"), get("month") - 1, get("day")) / 86_400_000;
}

export function edition(now: number): { volume: number; number: number; dateline: string } {
  const days = calendarDay(now, EDITION_TIME_ZONE) - Date.parse(LAUNCH_DATE) / 86_400_000;
  const dateline = new Intl.DateTimeFormat("en-US", {
    timeZone: EDITION_TIME_ZONE,
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  }).format(now);
  return { volume: Math.floor(days / 365) + 1, number: Math.max(1, days + 1), dateline };
}
