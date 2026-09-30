/**
 * Server-side client for the HangingAi API.
 *
 * Every fetcher is cached with `use cache` for about a minute (cacheLife
 * "minutes"), so a burst of visitors costs the API one request per distinct
 * query. Callers must reach these from request-time code (after reading
 * params/searchParams or `await connection()`), so `next build` never needs
 * the API to be up.
 */
import { cacheLife } from "next/cache";

import type {
  ArticleDetail,
  ContentType,
  FeedPage,
  FeedSort,
  Platform,
  Tool,
  ToolPage,
  ToolSort,
  Article,
  TopicCount,
} from "./types";
import { type QueryValue, withQuery } from "./url";

const API_URL = (process.env.API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    readonly status: number,
    path: string,
  ) {
    super(`HangingAi API returned ${status} for ${path}`);
  }
}

async function get<T>(path: string, query: Record<string, QueryValue> = {}): Promise<T> {
  const target = withQuery(path, query);
  const res = await fetch(`${API_URL}${target}`, { headers: { accept: "application/json" } });
  if (!res.ok) throw new ApiError(res.status, target);
  return (await res.json()) as T;
}

export async function getFeed(query: {
  sort: FeedSort;
  content_type?: ContentType;
  cursor?: string;
  limit?: number;
}): Promise<FeedPage> {
  "use cache";
  cacheLife("minutes");
  return get<FeedPage>("/api/feed", query);
}

export async function getArticle(id: number): Promise<ArticleDetail | null> {
  "use cache";
  cacheLife("minutes");
  try {
    return await get<ArticleDetail>(`/api/articles/${id}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export async function searchArticles(q: string): Promise<Article[]> {
  "use cache";
  cacheLife("minutes");
  return get<Article[]>("/api/search", { q, limit: 30 });
}

export async function getTools(query: {
  sort: ToolSort;
  platform?: Platform;
  has_demo?: boolean;
  topic?: string;
  language?: string;
  limit?: number;
  offset?: number;
}): Promise<ToolPage> {
  "use cache";
  cacheLife("minutes");
  return get<ToolPage>("/api/tools", { ...query, has_demo: query.has_demo ? "true" : undefined });
}

export async function getTool(id: number): Promise<Tool | null> {
  "use cache";
  cacheLife("minutes");
  try {
    return await get<Tool>(`/api/tools/${id}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export async function getTopics(limit = 16): Promise<TopicCount[]> {
  "use cache";
  cacheLife("hours");
  return get<TopicCount[]>("/api/topics", { limit });
}
