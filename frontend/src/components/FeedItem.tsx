import Link from "next/link";

import { CONTENT_TYPE_LABEL, engagementLabel, hostname, timeAgo } from "@/lib/format";
import type { Article } from "@/lib/types";

import { RemoteImage } from "./RemoteImage";

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

/**
 * Story metadata. Lists get the short form (type, source, age, engagement);
 * `full` adds the author and a link to the original, for story pages and the lead.
 */
export function ArticleMeta({
  article,
  now,
  full = false,
}: {
  article: Article;
  now: number;
  full?: boolean;
}) {
  const parts = [
    article.source.name,
    full ? article.author : null,
    timeAgo(article.published_at, now),
    engagementLabel(article),
  ].filter(Boolean);
  return (
    <p className="flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-[11px] text-muted">
      <TypeBadge type={article.content_type} />
      {parts.map((part, i) => (
        <span key={i} className="after:ml-2 after:content-['·'] last:after:content-none">
          {part}
        </span>
      ))}
      {full && (
        <a
          href={article.url}
          target="_blank"
          rel="noopener"
          className="underline decoration-hairline underline-offset-2 hover:text-ink hover:decoration-ink"
        >
          {hostname(article.url)} ↗
        </a>
      )}
    </p>
  );
}

function StoryImage({ article, sizes, priority = false }: { article: Article; sizes: string; priority?: boolean }) {
  return (
    <Link href={`/item/${article.id}`} tabIndex={-1} aria-hidden="true" className="block">
      <RemoteImage
        src={article.image_url}
        alt=""
        sizes={sizes}
        priority={priority}
        // Paper previews are the first page; the top shows its title, the middle is dense text.
        position={article.content_type === "paper" ? "top" : "center"}
      />
    </Link>
  );
}

/** The day's top story: display headline beside a large image, in a hard-edged frame. */
export function LeadStory({ article, now }: { article: Article; now: number }) {
  return (
    <article className="relative border-[3px] border-ink bg-paper-raised p-6 shadow-hard sm:p-8">
      <span
        aria-hidden="true"
        className="absolute -top-[3px] -right-[3px] h-10 w-10 border-[3px] border-ink bg-tomato"
      />
      <div className={article.image_url ? "grid items-center gap-8 md:grid-cols-2" : ""}>
        {article.image_url && <StoryImage article={article} sizes="(min-width: 768px) 420px, 100vw" priority />}
        <div className="space-y-4">
          <p className="kicker text-tomato">No. 01 · The lead</p>
          <h2 className="font-display text-3xl leading-[1.1] font-bold tracking-tight sm:text-4xl">
            <Link
              href={`/item/${article.id}`}
              className="hover:underline hover:decoration-tomato hover:decoration-4"
            >
              {article.title}
            </Link>
          </h2>
          {article.summary && <p className="line-clamp-3 leading-relaxed text-muted">{article.summary}</p>}
          <ArticleMeta article={article} now={now} />
        </div>
      </div>
    </article>
  );
}

/** Grid card for "In this issue": full-width image on top. */
export function StoryCard({ article, rank, now }: { article: Article; rank: number; now: number }) {
  return (
    <article className="space-y-3">
      {article.image_url && <StoryImage article={article} sizes="(min-width: 768px) 420px, 100vw" />}
      <p className="kicker text-muted">No. {String(rank).padStart(2, "0")}</p>
      <h3 className="font-display text-xl leading-snug font-semibold">
        <Link href={`/item/${article.id}`} className="hover:text-tomato">
          {article.title}
        </Link>
      </h3>
      {article.summary && <p className="line-clamp-2 text-sm leading-relaxed text-muted">{article.summary}</p>}
      <ArticleMeta article={article} now={now} />
    </article>
  );
}

/** List row: headline and summary with a thumbnail on the right. */
export function FeedItem({ article, now }: { article: Article; now: number }) {
  return (
    <article className="flex gap-6 border-b border-hairline py-6 last:border-none">
      <div className="min-w-0 flex-1 space-y-2">
        <h3 className="font-display text-xl leading-snug font-semibold">
          <Link href={`/item/${article.id}`} className="hover:text-tomato">
            {article.title}
          </Link>
        </h3>
        {article.summary && <p className="line-clamp-2 text-sm leading-relaxed text-muted">{article.summary}</p>}
        <ArticleMeta article={article} now={now} />
      </div>
      {article.image_url && (
        <div className="hidden w-56 shrink-0 self-start sm:block">
          <StoryImage article={article} sizes="224px" />
        </div>
      )}
    </article>
  );
}
