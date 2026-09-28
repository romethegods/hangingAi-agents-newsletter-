import Link from "next/link";

import { compactNumber, timeAgo } from "@/lib/format";
import type { Tool } from "@/lib/types";
import { withQuery } from "@/lib/url";

export function ToolName({ fullName }: { fullName: string }) {
  const [owner, repo] = fullName.split("/");
  return (
    <>
      <span className="font-normal text-muted">{owner}/</span>
      {repo}
    </>
  );
}

export function StarVelocity({ perDay }: { perDay: number }) {
  if (perDay < 1) return null;
  return (
    <span className="rounded bg-accent-soft px-1.5 py-0.5 text-xs font-medium text-accent">
      +{compactNumber(Math.round(perDay))}/day
    </span>
  );
}

export function ToolCard({ tool, now }: { tool: Tool; now: number }) {
  return (
    <article className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4">
      <div className="flex items-start justify-between gap-3">
        <h2 className="min-w-0 font-semibold break-words">
          <a href={tool.url} target="_blank" rel="noopener" className="hover:text-accent">
            <ToolName fullName={tool.full_name} />
          </a>
        </h2>
        <StarVelocity perDay={tool.star_velocity} />
      </div>
      {tool.description && <p className="line-clamp-3 text-sm text-muted">{tool.description}</p>}
      {tool.topics.length > 0 && (
        <ul className="flex flex-wrap gap-1.5">
          {tool.topics.slice(0, 5).map((topic) => (
            <li key={topic}>
              <Link
                href={withQuery("/tools", { topic })}
                className="rounded-full border border-border px-2 py-0.5 text-xs text-muted hover:border-accent hover:text-accent"
              >
                {topic}
              </Link>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-auto flex flex-wrap gap-x-3 text-xs text-muted">
        <span>★ {compactNumber(tool.stars)}</span>
        {tool.language && <span>{tool.language}</span>}
        {tool.pushed_at && <span>updated {timeAgo(tool.pushed_at, now)}</span>}
      </p>
    </article>
  );
}
