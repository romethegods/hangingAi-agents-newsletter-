// Mirrors backend/app/schemas.py. Keep in sync when the API changes.

export type ContentType = "news" | "paper" | "model";

export interface SourceBrief {
  slug: string;
  name: string;
}

export interface Article {
  id: number;
  title: string;
  url: string;
  summary: string | null;
  author: string | null;
  image_url: string | null;
  content_type: ContentType;
  published_at: string;
  engagement: number | null;
  source: SourceBrief;
}

export interface ArticleDetail extends Article {
  duplicate_of_id: number | null;
  coverage: Article[];
}

export interface FeedPage {
  items: Article[];
  next_cursor: string | null;
}

export interface Tool {
  id: number;
  full_name: string;
  url: string;
  description: string | null;
  language: string | null;
  stars: number;
  star_velocity: number;
  topics: string[];
  pushed_at: string | null;
}

export interface ToolPage {
  items: Tool[];
  total: number;
}

export interface TopicCount {
  topic: string;
  count: number;
}

export type FeedSort = "latest" | "hot";
export type ToolSort = "trending" | "stars" | "new";
