import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { DemoPlayer } from "@/components/DemoPlayer";
import { RemoteImage } from "@/components/RemoteImage";
import { FeedSkeleton } from "@/components/Skeleton";
import { ToolPoster } from "@/components/ToolPoster";
import { StarVelocity } from "@/components/ToolCard";
import { Comments } from "@/components/Comments";
import { FollowButton } from "@/components/FollowButton";
import { VoteButton } from "@/components/VoteButton";
import { getTool } from "@/lib/api";
import { getFollows, getVoteState } from "@/lib/session";
import { hostname, timeAgo } from "@/lib/format";
import { requestNow } from "@/lib/time";
import { DEMO_LABEL, PLATFORM_LABEL, displayName, popularity, previewImage } from "@/lib/tools";
import type { Tool } from "@/lib/types";
import { param, withQuery } from "@/lib/url";

// Soft 404 for unknown ids, same trade-off as /item/[id].
async function load(params: PageProps<"/tools/[id]">["params"]): Promise<Tool> {
  const id = Number((await params).id);
  const tool = Number.isSafeInteger(id) && id > 0 ? await getTool(id) : null;
  if (!tool) notFound();
  return tool;
}

export async function generateMetadata({ params }: PageProps<"/tools/[id]">): Promise<Metadata> {
  const tool = await load(params);
  const image = previewImage(tool);
  return {
    title: `${displayName(tool)} (${tool.full_name})`,
    description: tool.description ?? `${tool.full_name}, an open-source AI tool`,
    openGraph: { title: displayName(tool), images: image ? [image] : undefined },
  };
}

export default function ToolPage({ params, searchParams }: PageProps<"/tools/[id]">) {
  return (
    <Suspense fallback={<FeedSkeleton rows={3} />}>
      <ToolDetail params={params} searchParams={searchParams} />
    </Suspense>
  );
}

async function ToolDetail({ params, searchParams }: Pick<PageProps<"/tools/[id]">, "params" | "searchParams">) {
  const [tool, follows, query] = await Promise.all([load(params), getFollows(), searchParams]);
  const vote = await getVoteState("tool", tool.id);
  const now = await requestNow();
  const following = follows?.tools.some((t) => t.id === tool.id) ?? false;
  const name = displayName(tool);
  const source = tool.platform === "huggingface" ? "Hugging Face" : "GitHub";

  return (
    <article className="mx-auto max-w-4xl">
      <Link href="/tools" className="kicker font-semibold text-muted hover:text-tomato">
        ← All tools
      </Link>

      <header className="mt-6 space-y-4 border-b-[3px] border-ink pb-6">
        <p className="kicker text-tomato">
          {PLATFORM_LABEL[tool.platform]}
          {tool.demo_kind && ` · ${DEMO_LABEL[tool.demo_kind]}`}
        </p>
        <h1 className="font-display text-4xl leading-[1.05] font-black tracking-tight break-words sm:text-5xl">
          {name}
        </h1>
        <p className="font-mono text-sm text-muted">{tool.full_name}</p>
        {tool.description && <p className="max-w-2xl text-lg leading-relaxed">{tool.description}</p>}
        <p className="flex flex-wrap items-center gap-x-4 gap-y-2 font-mono text-xs text-muted">
          <span className="text-sm font-bold text-ink">{popularity(tool)}</span>
          <StarVelocity perDay={tool.star_velocity} />
          {tool.language && <span>{tool.language}</span>}
          {tool.pushed_at && <span>updated {timeAgo(tool.pushed_at, now)}</span>}
        </p>
      </header>

      <section aria-label="Demo" className="mt-8">
        {tool.demo_url && tool.demo_kind ? (
          <DemoPlayer
            kind={tool.demo_kind}
            url={tool.demo_url}
            poster={previewImage(tool)}
            posterFallback={<ToolPoster tool={tool} />}
            title={name}
          />
        ) : (
          <div className="max-w-md">
            <RemoteImage
              src={previewImage(tool)}
              fallback={<ToolPoster tool={tool} />}
              alt={`${name} preview`}
              sizes="448px"
            />
          </div>
        )}
        <p className="mt-3 font-mono text-[11px] text-muted">
          {tool.demo_url
            ? `Demo from ${hostname(tool.demo_url)}, shown as published by the ${source} project.`
            : `No demo published yet. Check the project on ${source} for screenshots.`}
        </p>
      </section>

      <div className="mt-8 flex flex-wrap items-center gap-4">
        <VoteButton kind="tool" id={tool.id} votes={vote.votes} voted={vote.voted} />
        <FollowButton
          kind="tool"
          target={String(tool.id)}
          following={following}
          back={`/tools/${tool.id}`}
        />
        <a
          href={tool.url}
          target="_blank"
          rel="noopener"
          className="kicker inline-block border-2 border-ink bg-tomato px-5 py-3 text-[0.8rem] font-bold text-on-accent shadow-hard transition-[transform,box-shadow] hover:-translate-x-0.5 hover:-translate-y-0.5"
        >
          Open on {source} ↗
        </a>
        {tool.topics.length > 0 && (
          <ul className="flex flex-wrap gap-1.5">
            {tool.topics.map((topic) => (
              <li key={topic}>
                <Link
                  href={withQuery("/tools", { topic })}
                  className="inline-block border border-ink px-1.5 py-0.5 font-mono text-[11px] hover:bg-mustard hover:text-[#171614]"
                >
                  #{topic}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>

      <Comments
        kind="tool"
        id={tool.id}
        back={`/tools/${tool.id}`}
        now={now}
        number={1}
        error={param(query, "comment_error")}
        reported={Boolean(param(query, "reported"))}
      />
    </article>
  );
}
