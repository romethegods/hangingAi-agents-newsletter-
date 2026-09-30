import Link from "next/link";
import { connection } from "next/server";
import { Suspense } from "react";

import { EmptyState } from "@/components/EmptyState";
import { FeedItem, LeadStory, StoryCard } from "@/components/FeedItem";
import { RankMark } from "@/components/Geometry";
import { SectionHeader } from "@/components/SectionHeader";
import { FeedSkeleton } from "@/components/Skeleton";
import { Tabs } from "@/components/Tabs";
import { DemoReelCard, StarVelocity, ToolName } from "@/components/ToolCard";
import { getFeed, getTools } from "@/lib/api";
import { compactNumber } from "@/lib/format";
import { requestNow } from "@/lib/time";
import { hasPlayableDemo } from "@/lib/tools";
import type { ContentType, FeedSort } from "@/lib/types";
import { oneOf, param, withQuery } from "@/lib/url";

const FEED_TABS = {
  top: { label: "Top stories", sort: "hot" },
  latest: { label: "Latest", sort: "latest" },
  papers: { label: "Papers", sort: "latest", content_type: "paper" },
  models: { label: "Models", sort: "hot", content_type: "model" },
  news: { label: "News", sort: "latest", content_type: "news" },
} satisfies Record<string, { label: string; sort: FeedSort; content_type?: ContentType }>;

type TabKey = keyof typeof FEED_TABS;
const TAB_KEYS = Object.keys(FEED_TABS) as TabKey[];

export default function Home({ searchParams }: PageProps<"/">) {
  return (
    <div className="grid gap-14 lg:grid-cols-[minmax(0,1fr)_280px]">
      <section aria-label="AI news feed">
        <Suspense fallback={<FeedSkeleton />}>
          <HomeFeed searchParams={searchParams} />
        </Suspense>
      </section>
      <aside aria-labelledby="leaderboard-heading">
        <SectionHeader number={4} title="The Leaderboard" id="leaderboard-heading" />
        <p className="kicker mb-4 text-muted">Fastest-rising open-source tools</p>
        <Suspense fallback={<FeedSkeleton rows={6} />}>
          <Leaderboard />
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

  const [lead, ...rest] = page.items;
  const showLead = tab === "top" && !cursor && lead;

  return (
    <div className="space-y-14">
      <Tabs tabs={tabs} active={tab} label="Feed sections" />

      {page.items.length === 0 ? (
        <EmptyState title="Nothing here yet">The crawler adds new items every hour.</EmptyState>
      ) : showLead ? (
        <>
          <LeadStory article={lead} now={now} />
          <section aria-labelledby="reel-heading">
            <SectionHeader
              number={2}
              title="Demo reel"
              id="reel-heading"
              aside={
                <Link
                  href="/tools?demos=1"
                  className="kicker font-semibold whitespace-nowrap hover:text-tomato"
                >
                  All demos →
                </Link>
              }
            />
            <Suspense fallback={<div className="h-40 animate-pulse bg-hairline" />}>
              <DemoReel />
            </Suspense>
          </section>
          <section aria-labelledby="issue-heading">
            <SectionHeader number={3} title="In this issue" id="issue-heading" />
            <div className="grid gap-x-8 gap-y-12 md:grid-cols-2">
              {rest.map((article, i) => (
                <StoryCard key={article.id} article={article} now={now} rank={i + 2} />
              ))}
            </div>
          </section>
        </>
      ) : (
        <section aria-labelledby="list-heading">
          <SectionHeader number={1} title={FEED_TABS[tab].label} id="list-heading" />
          {page.items.map((article) => (
            <FeedItem key={article.id} article={article} now={now} />
          ))}
        </section>
      )}

      {(cursor || page.next_cursor) && (
        <nav aria-label="Pagination" className="kicker flex justify-between border-t-2 border-ink pt-4">
          {cursor ? (
            <Link href={withQuery("/", { tab })} className="font-semibold hover:text-tomato">
              ← Newest
            </Link>
          ) : (
            <span />
          )}
          {page.next_cursor && (
            <Link
              href={withQuery("/", { tab, cursor: page.next_cursor })}
              className="font-semibold hover:text-tomato"
            >
              Older →
            </Link>
          )}
        </nav>
      )}
    </div>
  );
}

async function DemoReel() {
  await connection();
  // Two playable GitHub demos (video/GIF) and two live HF apps, hottest first.
  const [github, spaces] = await Promise.all([
    getTools({ sort: "trending", platform: "github", has_demo: true, limit: 24 }),
    getTools({ sort: "trending", platform: "huggingface", has_demo: true, limit: 2 }),
  ]);
  const reel = [...github.items.filter(hasPlayableDemo).slice(0, 2), ...spaces.items];
  if (reel.length === 0) return <p className="text-sm text-muted">Demos appear after the next crawl.</p>;
  return (
    <div className="grid gap-x-8 gap-y-10 sm:grid-cols-2">
      {reel.map((tool) => (
        <DemoReelCard key={tool.id} tool={tool} />
      ))}
    </div>
  );
}

async function Leaderboard() {
  await connection(); // request-time only, so builds don't depend on the API
  const { items } = await getTools({ sort: "trending", limit: 8 });
  if (items.length === 0) return <p className="text-sm text-muted">No tools tracked yet.</p>;
  return (
    <>
      <ol className="space-y-4">
        {items.map((tool, i) => (
          <li key={tool.id} className="flex items-start gap-3">
            <RankMark rank={i + 1} />
            <div className="min-w-0 text-sm">
              <Link
                href={`/tools/${tool.id}`}
                title={tool.full_name}
                className="block truncate font-semibold hover:text-tomato"
              >
                <ToolName fullName={tool.full_name} />
              </Link>
              <div className="mt-1 flex items-center gap-2 font-mono text-[11px] text-muted">
                <span>★ {compactNumber(tool.stars)}</span>
                <StarVelocity perDay={tool.star_velocity} />
              </div>
            </div>
          </li>
        ))}
      </ol>
      <Link
        href="/tools"
        className="kicker mt-6 inline-block border-2 border-ink px-3 py-2 font-semibold shadow-hard-sm hover:bg-mustard hover:text-[#171614]"
      >
        Full leaderboard →
      </Link>
    </>
  );
}
