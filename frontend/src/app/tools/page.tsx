import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { EmptyState } from "@/components/EmptyState";
import { CardGridSkeleton } from "@/components/Skeleton";
import { Tabs } from "@/components/Tabs";
import { ToolCard } from "@/components/ToolCard";
import { getTools, getTopics } from "@/lib/api";
import type { ToolSort } from "@/lib/types";
import { oneOf, param, positiveInt, withQuery } from "@/lib/url";
import { requestNow } from "@/lib/time";

export const metadata: Metadata = {
  title: "Open-source AI tools",
  description:
    "Trending open-source AI agents, LLM frameworks, MCP servers and RAG tools, ranked by how fast they're gaining stars.",
};

const PAGE_SIZE = 30;
const SORTS: { key: ToolSort; label: string }[] = [
  { key: "trending", label: "Trending" },
  { key: "stars", label: "Most stars" },
  { key: "new", label: "Newly added" },
];

export default function ToolsPage({ searchParams }: PageProps<"/tools">) {
  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight">Open-source AI tools</h1>
        <p className="text-muted">
          Agents, LLM frameworks, MCP servers and more, ranked by stars gained per day.
        </p>
      </header>
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
  const page = positiveInt(param(query, "page"));

  const [tools, topics] = await Promise.all([
    getTools({ sort, topic, limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE }),
    getTopics(),
  ]);
  const now = await requestNow();
  const pages = Math.max(1, Math.ceil(tools.total / PAGE_SIZE));
  const href = (overrides: Record<string, string | number | undefined>) =>
    withQuery("/tools", {
      sort: sort === "trending" ? undefined : sort,
      topic,
      ...overrides,
    });

  return (
    <>
      <Tabs
        label="Sort tools"
        active={sort}
        tabs={SORTS.map((s) => ({
          key: s.key,
          label: s.label,
          href: href({ sort: s.key === "trending" ? undefined : s.key, page: undefined }),
        }))}
      />

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
            {t.topic} <span className="text-muted">{t.count}</span>
          </TopicChip>
        ))}
      </nav>

      {tools.items.length === 0 ? (
        <EmptyState title="No tools match">
          <Link href="/tools" className="text-accent hover:underline">
            Clear filters
          </Link>
        </EmptyState>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {tools.items.map((tool) => (
            <ToolCard key={tool.id} tool={tool} now={now} />
          ))}
        </div>
      )}

      {pages > 1 && (
        <nav aria-label="Pagination" className="flex items-center justify-between text-sm">
          {page > 1 ? (
            <Link href={href({ page: page - 1 === 1 ? undefined : page - 1 })} className="text-accent hover:underline">
              ← Previous
            </Link>
          ) : (
            <span />
          )}
          <span className="text-muted">
            Page {page} of {pages}
          </span>
          {page < pages ? (
            <Link href={href({ page: page + 1 })} className="text-accent hover:underline">
              Next →
            </Link>
          ) : (
            <span />
          )}
        </nav>
      )}
    </>
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
      className={`rounded-full border px-3 py-1 text-sm ${
        active
          ? "border-accent bg-accent-soft text-accent"
          : "border-border text-foreground hover:border-accent"
      }`}
    >
      {children}
    </Link>
  );
}
