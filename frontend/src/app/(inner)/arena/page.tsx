import type { Metadata } from "next";
import Link from "next/link";
import { connection } from "next/server";
import { Suspense } from "react";

import { ArenaLeaderboard } from "@/components/Leaderboard";
import { PageHeader } from "@/components/PageHeader";
import { SectionHeader } from "@/components/SectionHeader";
import { FeedSkeleton } from "@/components/Skeleton";
import { startBattle } from "@/lib/actions";
import { getGallery, getLeaderboard } from "@/lib/api";
import { getArenaStatus } from "@/lib/session";
import { param } from "@/lib/url";

export const metadata: Metadata = {
  title: "Arena: blind AI model battles",
  description: "Two anonymous AI models answer your prompt side by side. Vote for the better one; the names are revealed after.",
};

const EXAMPLES = [
  "Explain RAG to a junior developer in 5 sentences",
  "Write a Python function that retries an HTTP call with exponential backoff",
  "What's the best way to give an AI agent long-term memory?",
  "Review this idea: an app that summarizes GitHub issues every morning",
];

export default function ArenaPage({ searchParams }: PageProps<"/arena">) {
  return (
    <div className="grid gap-14 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div className="space-y-10">
        <PageHeader kicker="The Arena" title="Two AIs. One prompt. You judge.">
          Ask anything. Two anonymous models answer side by side, live. Vote for the better answer and
          we reveal who they were. Every vote moves the public leaderboard.
        </PageHeader>
        <Suspense fallback={<div className="h-48 animate-pulse bg-hairline" />}>
          <PromptBox searchParams={searchParams} />
        </Suspense>
        <section>
          <SectionHeader number={2} title="Recent shared battles" />
          <Suspense fallback={<FeedSkeleton rows={3} />}>
            <Gallery />
          </Suspense>
        </section>
      </div>
      <aside>
        <SectionHeader
          number={3}
          title="Leaderboard"
          aside={
            <Link href="/arena/leaderboard" className="kicker font-semibold hover:text-tomato">
              Full →
            </Link>
          }
        />
        <Suspense fallback={<FeedSkeleton rows={5} />}>
          <TopModels />
        </Suspense>
      </aside>
    </div>
  );
}

async function PromptBox({ searchParams }: Pick<PageProps<"/arena">, "searchParams">) {
  const [query, status] = await Promise.all([searchParams, getArenaStatus()]);
  const error = param(query, "error");
  if (!status.open) {
    return (
      <div className="border-2 border-dashed border-ink p-6">
        <p className="font-display text-xl font-semibold">The Arena opens soon</p>
        <p className="mt-2 text-sm text-muted">We&apos;re lining up the models. Check back shortly.</p>
      </div>
    );
  }
  return (
    <section aria-labelledby="new-battle" className="border-[3px] border-ink bg-paper-raised p-6 shadow-hard">
      <SectionHeader number={1} title="Start a battle" id="new-battle" />
      <form action={startBattle} className="space-y-3">
        <label htmlFor="arena-prompt" className="sr-only">
          Your prompt
        </label>
        <textarea
          id="arena-prompt"
          name="prompt"
          required
          maxLength={2000}
          rows={4}
          defaultValue={param(query, "prompt")}
          placeholder="Ask both models anything: code, explanations, ideas, reviews…"
          className="w-full border-2 border-ink bg-paper px-3 py-2.5 text-base"
        />
        {error && (
          <p role="alert" className="text-sm font-semibold text-tomato">
            {error}
          </p>
        )}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="font-mono text-[11px] text-muted">
            {status.battles_left === null
              ? `${status.battles_per_day} free battles a day · no sign-up`
              : `${status.battles_left} of ${status.battles_per_day} battles left today`}{" "}
            · {status.models} models in the ring
          </p>
          <button
            type="submit"
            className="kicker border-2 border-ink bg-tomato px-5 py-3 text-[0.8rem] font-bold text-on-accent shadow-hard-sm hover:opacity-90"
          >
            Fight! →
          </button>
        </div>
      </form>
      <div className="mt-5 border-t border-hairline pt-4">
        <p className="kicker mb-2 text-muted">Or try one</p>
        <div className="flex flex-wrap gap-2">
          {EXAMPLES.map((example) => (
            <form key={example} action={startBattle}>
              <input type="hidden" name="prompt" value={example} />
              <button type="submit" className="border border-ink px-2.5 py-1 text-left text-xs hover:bg-mustard hover:text-[#171614]">
                {example}
              </button>
            </form>
          ))}
        </div>
      </div>
    </section>
  );
}

async function TopModels() {
  await connection(); // request-time only, so builds don't depend on the API
  return <ArenaLeaderboard rows={await getLeaderboard()} limit={6} />;
}

const VERDICT = { a: "A won", b: "B won", tie: "tie", bad: "both bad" } as const;

async function Gallery() {
  await connection();
  const battles = await getGallery(8);
  if (battles.length === 0) {
    return <p className="text-sm text-muted">No shared battles yet. Finish one and press &ldquo;Share&rdquo;.</p>;
  }
  return (
    <ul className="divide-y divide-hairline">
      {battles.map((b) => (
        <li key={b.id} className="py-4">
          <Link href={`/arena/b/${b.id}`} className="font-display text-lg leading-snug font-semibold hover:text-tomato">
            &ldquo;{b.prompt}&rdquo;
          </Link>
          <p className="mt-1 font-mono text-[11px] text-muted">
            {b.model_a.name} vs {b.model_b.name} · {VERDICT[b.vote]}
          </p>
        </li>
      ))}
    </ul>
  );
}
