import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { EmptyState } from "@/components/EmptyState";
import { PageHeader } from "@/components/PageHeader";
import { CardGridSkeleton } from "@/components/Skeleton";
import { Tabs } from "@/components/Tabs";
import { ToolCard } from "@/components/ToolCard";
import { getTools, getTopics } from "@/lib/api";
import type { Platform, ToolSort } from "@/lib/types";
import { oneOf, param, positiveInt, withQuery } from "@/lib/url";
import { requestNow } from "@/lib/time";

export const metadata: Metadata = {
  title: "Open-source AI tools",
  description:
    "Trending open-source AI agents, LLM frameworks, MCP servers and RAG tools, ranked by how fast they're gaining stars.",
};

const PAGE_SIZE = 30;
const SOURCES: { key: "all" | Platform; label: string }[] = [
  { key: "all", label: "All sources" },
  { key: "github", label: "GitHub" },
  { key: "huggingface", label: "HF Spaces" },
];
const SORTS: { key: ToolSort; label: string }[] = [
  { key: "trending", label: "Trending" },
  { key: "stars", label: "Most stars" },
  { key: "new", label: "Newly added" },
];

export default function ToolsPage({ searchParams }: PageProps<"/tools">) {
  return (
    <div>
      <PageHeader kicker="Section B · The tools desk" title="Open-source AI tools">
        Agents, LLM frameworks, MCP servers and live demo apps, ranked by the stars and likes
        they&apos;re gaining each day. Press play on any demo.
      </PageHeader>
      <Suspense fallback={<CardGridSkeleton />}>
        <ToolsDirectory searchParams={searchParams} />
      </Suspense>
    </div>
  );
}

async function ToolsDirectory({ searchParams }: Pick<PageProps<"/tools">, "searchParams">) {
  const query = await searchParams;
  const sort = oneOf(
    param(query, "sort"),
    SORTS.map((s) => s.key),
    "trending",
  );
  const topic = param(query, "topic")?.toLowerCase();
  const source = oneOf(
    param(query, "source"),
    SOURCES.map((s) => s.key),
    "all",
  );
  const demos = param(query, "demos") === "1";
  const page = positiveInt(param(query, "page"));

  const [tools, topics] = await Promise.all([
    getTools({
      sort,
      topic,
      platform: source === "all" ? undefined : source,
      has_demo: demos,
      limit: PAGE_SIZE,
      offset: (page - 1) * PAGE_SIZE,
    }),
    getTopics(),
  ]);
  const now = await requestNow();
  const pages = Math.max(1, Math.ceil(tools.total / PAGE_SIZE));
  const href = (overrides: Record<string, string | number | undefined>) =>
    withQuery("/tools", {
      sort: sort === "trending" ? undefined : sort,
      source: source === "all" ? undefined : source,
      demos: demos ? 1 : undefined,
      topic,
      ...overrides,
    });

  return (
    <div className="space-y-6">
      <Tabs
        label="Sort tools"
        active={sort}
        tabs={SORTS.map((s) => ({
          key: s.key,
          label: s.label,
          href: href({ sort: s.key === "trending" ? undefined : s.key, page: undefined }),
        }))}
      />

      <div className="flex flex-wrap items-center gap-3">
        <Tabs
          label="Filter by source"
          active={source}
          tabs={SOURCES.map((s) => ({
            key: s.key,
            label: s.label,
            href: href({ source: s.key === "all" ? undefined : s.key, page: undefined }),
          }))}
        />
        <TopicChip href={href({ demos: demos ? undefined : 1, page: undefined })} active={demos}>
          ▶ With demos only
        </TopicChip>
      </div>

      <nav aria-label="Filter by topic" className="flex flex-wrap gap-2">
        <TopicChip href={href({ topic: undefined, page: undefined })} active={!topic}>
          All
        </TopicChip>
        {topics.map((t) => (
          <TopicChip
            key={t.topic}
            href={href({ topic: t.topic, page: undefined })}
            active={t.topic === topic}
          >
            #{t.topic} <span className="opacity-60">{t.count}</span>
          </TopicChip>
        ))}
      </nav>

      {tools.items.length === 0 ? (
        <EmptyState title="No tools match">
          <Link href="/tools" className="font-semibold hover:text-tomato">
            Clear filters
          </Link>
        </EmptyState>
      ) : (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {tools.items.map((tool) => (
            <ToolCard key={tool.id} tool={tool} now={now} />
          ))}
        </div>
      )}

      {pages > 1 && (
        <nav aria-label="Pagination" className="kicker flex items-center justify-between border-t-2 border-ink pt-4">
          {page > 1 ? (
            <Link href={href({ page: page - 1 === 1 ? undefined : page - 1 })} className="font-semibold hover:text-tomato">
              ← Previous
            </Link>
          ) : (
            <span />
          )}
          <span className="text-muted">
            Page {page} of {pages}
          </span>
          {page < pages ? (
            <Link href={href({ page: page + 1 })} className="font-semibold hover:text-tomato">
              Next →
            </Link>
          ) : (
            <span />
          )}
        </nav>
      )}
    </div>
  );
}

function TopicChip({
  href,
  active,
  children,
}: {
  href: string;
  active: boolean;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={`inline-block border-2 border-ink px-2.5 py-1 font-mono text-xs ${
        active ? "bg-ink text-paper" : "bg-paper-raised hover:bg-mustard hover:text-[#171614]"
      }`}
    >
      {children}
    </Link>
  );
}
