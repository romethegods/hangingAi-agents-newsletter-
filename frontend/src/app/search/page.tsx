import type { Metadata } from "next";
import { Suspense } from "react";

import { EmptyState } from "@/components/EmptyState";
import { FeedItem } from "@/components/FeedItem";
import { FeedSkeleton } from "@/components/Skeleton";
import { searchArticles } from "@/lib/api";
import { requestNow } from "@/lib/time";
import { param } from "@/lib/url";

export const metadata: Metadata = {
  title: "Search",
  robots: { index: false }, // endless query permutations shouldn't be indexed
};

export default function SearchPage({ searchParams }: PageProps<"/search">) {
  return (
    <Suspense fallback={<FeedSkeleton />}>
      <Results searchParams={searchParams} />
    </Suspense>
  );
}

async function Results({ searchParams }: Pick<PageProps<"/search">, "searchParams">) {
  const q = (param(await searchParams, "q") ?? "").trim().slice(0, 200);
  if (q.length < 2) {
    return (
      <EmptyState title="Search HangingAi">
        Try “agent memory”, “diffusion” or “open-source voice”.
      </EmptyState>
    );
  }

  const results = await searchArticles(q);
  const now = await requestNow();
  return (
    <section className="space-y-4">
      <h1 className="text-xl font-semibold">
        {results.length} result{results.length === 1 ? "" : "s"} for “{q}”
      </h1>
      {results.length === 0 ? (
        <EmptyState title="No matches">Try fewer or different words.</EmptyState>
      ) : (
        <div>
          {results.map((article) => (
            <FeedItem key={article.id} article={article} now={now} />
          ))}
        </div>
      )}
    </section>
  );
}
