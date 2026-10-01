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
  votes: number;
  comments: number;
}

export interface ArticleDetail extends Article {
  duplicate_of_id: number | null;
  coverage: Article[];
}

export interface FeedPage {
  items: Article[];
  next_cursor: string | null;
}

export type Platform = "github" | "huggingface";
export type DemoKind = "video" | "embed" | "gif" | "image" | "app";

export interface Tool {
  id: number;
  platform: Platform;
  full_name: string;
  title: string | null;
  url: string;
  description: string | null;
  language: string | null;
  stars: number;
  star_velocity: number;
  topics: string[];
  pushed_at: string | null;
  preview_image_url: string | null;
  demo_url: string | null;
  demo_kind: DemoKind | null;
  votes: number;
  comments: number;
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

export interface User {
  id: number;
  handle: string;
  email: string | null;
  is_guest: boolean;
  brief_enabled: boolean;
  brief_hour: number;
  timezone: string;
}

export interface Follows {
  tools: Tool[];
  topics: string[];
}

export interface Release {
  id: number;
  tag: string;
  name: string | null;
  url: string;
  published_at: string | null;
  notes: string | null;
  tool: Tool;
}

export interface BriefArticle extends Article {
  matched: boolean;
}

export interface Brief {
  personalized: boolean;
  followed_topics: string[];
  releases: Release[];
  rising: Tool[];
  reads: BriefArticle[];
  demo: Tool | null;
}

export interface Comment {
  id: number;
  parent_id: number | null;
  author: string;
  body: string | null; // null when hidden or removed
  status: "visible" | "hidden" | "removed";
  created_at: string;
  votes: number;
  voted: boolean;
  mine: boolean;
  replies: Comment[];
}

export interface CommentThread {
  count: number;
  comments: Comment[];
  here: number;
}

export interface VoteState {
  voted: boolean;
  votes: number;
}

export interface ModerationItem {
  id: number;
  target_kind: "article" | "tool";
  target_id: number;
  author: string;
  author_id: number;
  body: string;
  status: "visible" | "hidden";
  report_count: number;
  created_at: string;
}

export interface ArenaModel {
  slug: string;
  name: string;
  maker: string;
  open_weights: boolean;
}

export interface Battle {
  id: number;
  prompt: string;
  status: "pending" | "streaming" | "ready" | "voted" | "failed";
  response_a: string | null;
  response_b: string | null;
  error: string | null;
  vote: "a" | "b" | "tie" | "bad" | null;
  created_at: string;
  mine: boolean;
  public: boolean;
  model_a: ArenaModel | null; // revealed after the vote
  model_b: ArenaModel | null;
  rating_change_a: number | null;
  rating_change_b: number | null;
  identity_leak: boolean;
}

export interface Standing extends ArenaModel {
  rating: number;
  battles: number;
  wins: number;
  losses: number;
  ties: number;
  win_rate: number | null;
  provisional: boolean;
}

export interface ArenaStatus {
  open: boolean;
  models: number;
  battles_left: number | null;
  battles_per_day: number;
}

export interface GalleryBattle {
  id: number;
  prompt: string;
  vote: "a" | "b" | "tie" | "bad";
  model_a: ArenaModel;
  model_b: ArenaModel;
  voted_at: string;
}
