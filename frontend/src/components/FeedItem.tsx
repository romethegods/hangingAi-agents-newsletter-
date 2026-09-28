import Link from "next/link";

import { CONTENT_TYPE_LABEL, engagementLabel, hostname, timeAgo } from "@/lib/format";
import type { Article } from "@/lib/types";

const BADGE_STYLE: Record<Article["content_type"], string> = {
  news: "bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300",
  paper: "bg-violet-100 text-violet-800 dark:bg-violet-950 dark:text-violet-300",
  model: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300",
};

export function TypeBadge({ type }: { type: Article["content_type"] }) {
  return (
    <span className={`rounded px-1.5 py-0.5 text-[11px] font-medium ${BADGE_STYLE[type]}`}>
      {CONTENT_TYPE_LABEL[type]}
    </span>
  );
}

export function ArticleMeta({ article, now }: { article: Article; now: number }) {
  const engagement = engagementLabel(article);
  const parts = [
    article.source.name,
    article.author,
    timeAgo(article.published_at, now),
    engagement,
  ].filter(Boolean);
  return (
    <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
      <TypeBadge type={article.content_type} />
      {parts.map((part, i) => (
        <span key={i} className="after:ml-2 after:content-['·'] last:after:content-none">
          {part}
        </span>
      ))}
      <a
        href={article.url}
        target="_blank"
        rel="noopener"
        className="underline-offset-2 hover:text-foreground hover:underline"
      >
        {hostname(article.url)} ↗
      </a>
    </p>
  );
}

export function FeedItem({ article, rank, now }: { article: Article; rank?: number; now: number }) {
  return (
    <article className="flex gap-3 border-b border-border py-4 last:border-none">
      {rank !== undefined && (
        <span className="w-6 shrink-0 pt-0.5 text-right font-mono text-sm text-muted tabular-nums">
          {rank}
        </span>
      )}
      <div className="min-w-0 space-y-1.5">
        <h2 className="leading-snug font-semibold">
          <Link href={`/item/${article.id}`} className="hover:text-accent">
            {article.title}
          </Link>
        </h2>
        {article.summary && <p className="line-clamp-2 text-sm text-muted">{article.summary}</p>}
        <ArticleMeta article={article} now={now} />
      </div>
    </article>
  );
}
