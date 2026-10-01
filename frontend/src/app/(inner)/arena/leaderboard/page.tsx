import type { Metadata } from "next";
import Link from "next/link";
import { connection } from "next/server";
import { Suspense } from "react";

import { ArenaLeaderboard } from "@/components/Leaderboard";
import { PageHeader } from "@/components/PageHeader";
import { FeedSkeleton } from "@/components/Skeleton";
import { getLeaderboard } from "@/lib/api";

export const metadata: Metadata = {
  title: "Arena leaderboard",
  description: "AI models ranked by blind, side-by-side votes from HangingAi readers.",
};

export default function LeaderboardPage() {
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader kicker="The Arena" title="Leaderboard">
        Ranked by blind votes: readers see two anonymous answers and pick the better one. Ratings use
        Elo, like chess. A <span className="font-mono">?</span> means fewer than 30 battles, so the
        rating is still settling.
      </PageHeader>
      <Suspense fallback={<FeedSkeleton rows={6} />}>
        <Table />
      </Suspense>
      <p className="mt-6 text-sm text-muted">
        Votes where an answer revealed its own model are kept but not counted.{" "}
        <Link href="/arena" className="font-semibold underline">
          Start a battle →
        </Link>
      </p>
    </div>
  );
}

async function Table() {
  await connection(); // request-time only, so builds don't depend on the API
  return <ArenaLeaderboard rows={await getLeaderboard()} />;
}
