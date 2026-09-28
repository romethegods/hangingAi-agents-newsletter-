import Link from "next/link";
import { connection } from "next/server";
import { Suspense } from "react";

import { EmptyState } from "@/components/EmptyState";
import { FeedItem } from "@/components/FeedItem";
import { FeedSkeleton } from "@/components/Skeleton";
import { Tabs } from "@/components/Tabs";
import { StarVelocity, ToolName } from "@/components/ToolCard";
import { getFeed, getTools } from "@/lib/api";
import type { ContentType, FeedSort } from "@/lib/types";
import { oneOf, param, withQuery } from "@/lib/url";
import { requestNow } from "@/lib/time";

const FEED_TABS = {
  top: { label: "Top", sort: "hot" },
  latest: { label: "Latest", sort: "latest" },
  papers: { label: "Papers", sort: "latest", content_type: "paper" },
  models: { label: "Models", sort: "hot", content_type: "model" },
  news: { label: "News", sort: "latest", content_type: "news" },
} satisfies Record<string, { label: string; sort: FeedSort; content_type?: ContentType }>;

type TabKey = keyof typeof FEED_TABS;
const TAB_KEYS = Object.keys(FEED_TABS) as TabKey[];

export default function Home({ searchParams }: PageProps<"/">) {
  return (
    <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_300px]">
      <section aria-labelledby="feed-heading">
        <h1 id="feed-heading" className="sr-only">
          AI news feed
        </h1>
        <Suspense fallback={<FeedSkeleton />}>
          <HomeFeed searchParams={searchParams} />
        </Suspense>
      </section>
      <aside aria-labelledby="trending-heading" className="lg:pt-1">
        <h2 id="trending-heading" className="mb-3 text-sm font-semibold tracking-wide text-muted uppercase">
          Trending open-source tools
        </h2>
        <Suspense fallback={<FeedSkeleton rows={6} />}>
          <TrendingTools />
        </Suspense>
      </aside>
    </div>
  );
}

async function HomeFeed({ searchParams }: Pick<PageProps<"/">, "searchParams">) {
  const query = await searchParams;
  const tab = oneOf(param(query, "tab"), TAB_KEYS, "top");
  const cursor = param(query, "cursor");
  const config: { sort: FeedSort; content_type?: ContentType } = FEED_TABS[tab];

  const page = await getFeed({
    sort: config.sort,
    content_type: config.content_type,
    cursor: config.sort === "latest" ? cursor : undefined,
    limit: 30,
  });
  const now = await requestNow();
  const tabs = TAB_KEYS.map((key) => ({
    key,
    label: FEED_TABS[key].label,
    href: withQuery("/", { tab: key === "top" ? undefined : key }),
  }));

  return (
    <>
      <Tabs tabs={tabs} active={tab} label="Feed sections" />
      {page.items.length === 0 ? (
        <div className="mt-6">
          <EmptyState title="Nothing here yet">The crawler adds new items every hour.</EmptyState>
        </div>
      ) : (
        <div>
          {page.items.map((article, i) => (
            <FeedItem
              key={article.id}
              article={article}
              now={now}
              rank={tab === "top" ? i + 1 : undefined}
            />
          ))}
        </div>
      )}
      {(cursor || page.next_cursor) && (
        <nav aria-label="Pagination" className="mt-6 flex justify-between text-sm">
          {cursor ? (
            <Link href={withQuery("/", { tab })} className="text-muted hover:text-foreground">
              ← Newest
            </Link>
          ) : (
            <span />
          )}
          {page.next_cursor && (
            <Link
              href={withQuery("/", { tab, cursor: page.next_cursor })}
              className="font-medium text-accent hover:underline"
            >
              Older →
            </Link>
          )}
        </nav>
      )}
    </>
  );
}

async function TrendingTools() {
  await connection(); // request-time only, so builds don't depend on the API
  const { items } = await getTools({ sort: "trending", limit: 8 });
  if (items.length === 0) return <p className="text-sm text-muted">No tools tracked yet.</p>;
  return (
    <>
      <ol className="space-y-3">
        {items.map((tool) => (
          <li key={tool.id} className="text-sm">
            <a href={tool.url} target="_blank" rel="noopener" className="font-medium hover:text-accent">
              <ToolName fullName={tool.full_name} />
            </a>
            <div className="mt-0.5 flex items-center gap-2 text-xs text-muted">
              <span>★ {tool.stars.toLocaleString("en")}</span>
              <StarVelocity perDay={tool.star_velocity} />
            </div>
          </li>
        ))}
      </ol>
      <Link href="/tools" className="mt-4 inline-block text-sm font-medium text-accent hover:underline">
        All tools →
      </Link>
    </>
  );
}
