import Link from "next/link";

import { CONTENT_TYPE_LABEL, engagementLabel, hostname, timeAgo } from "@/lib/format";
import type { Article } from "@/lib/types";

// Flat ink-on-color blocks, one color per content type.
const BADGE_STYLE: Record<Article["content_type"], string> = {
  news: "bg-cobalt text-on-accent",
  paper: "bg-tomato text-on-accent",
  model: "bg-mustard text-[#171614]",
};

export function TypeBadge({ type }: { type: Article["content_type"] }) {
  return (
    <span className={`kicker inline-block px-1.5 py-0.5 font-bold ${BADGE_STYLE[type]}`}>
      {CONTENT_TYPE_LABEL[type]}
    </span>
  );
}

export function ArticleMeta({
  article,
  now,
  compact = false,
}: {
  article: Article;
  now: number;
  compact?: boolean;
}) {
  const engagement = engagementLabel(article);
  const parts = [
    article.source.name,
    compact ? null : article.author,
    timeAgo(article.published_at, now),
    engagement,
  ].filter(
    Boolean,
  );
  return (
    <p className="flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-[11px] text-muted">
      <TypeBadge type={article.content_type} />
      {parts.map((part, i) => (
        <span key={i} className="after:ml-2 after:content-['/'] last:after:content-none">
          {part}
        </span>
      ))}
      <a
        href={article.url}
        target="_blank"
        rel="noopener"
        className="underline decoration-hairline underline-offset-2 hover:text-ink hover:decoration-ink"
      >
        {hostname(article.url)} ↗
      </a>
    </p>
  );
}

/** The day's top story: big display headline in a hard-edged frame. */
export function LeadStory({ article, now }: { article: Article; now: number }) {
  return (
    <article className="relative border-[3px] border-ink bg-paper-raised p-6 shadow-hard sm:p-8">
      <span
        aria-hidden="true"
        className="absolute -top-[3px] -right-[3px] h-10 w-10 border-[3px] border-ink bg-tomato"
      />
      <p className="kicker mb-3 text-tomato">No. 01 · The lead</p>
      <h2 className="font-display text-3xl leading-[1.1] font-bold tracking-tight sm:text-4xl">
        <Link href={`/item/${article.id}`} className="hover:underline hover:decoration-tomato hover:decoration-4">
          {article.title}
        </Link>
      </h2>
      {article.summary && (
        <p className="mt-4 line-clamp-4 max-w-2xl leading-relaxed text-muted">{article.summary}</p>
      )}
      <div className="mt-5">
        <ArticleMeta article={article} now={now} />
      </div>
    </article>
  );
}

export function FeedItem({
  article,
  rank,
  now,
  compact = false,
}: {
  article: Article;
  rank?: number;
  now: number;
  compact?: boolean;
}) {
  return (
    <article className="flex gap-4 border-b border-hairline py-5 last:border-none">
      {rank !== undefined && (
        // Outlined numerals: an ink stroke with a hollow center, like 90s print.
        <span className="w-9 shrink-0 font-display text-3xl leading-none font-black text-transparent tabular-nums [-webkit-text-stroke:1.25px_var(--ink)]">
          {String(rank).padStart(2, "0")}
        </span>
      )}
      <div className="min-w-0 space-y-2">
        <h3 className="font-display text-lg leading-snug font-semibold">
          <Link href={`/item/${article.id}`} className="hover:text-tomato">
            {article.title}
          </Link>
        </h3>
        {article.summary && <p className="line-clamp-2 text-sm text-muted">{article.summary}</p>}
        <ArticleMeta article={article} now={now} compact={compact} />
      </div>
    </article>
  );
}
