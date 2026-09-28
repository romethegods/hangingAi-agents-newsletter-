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
    <span className="kicker inline-block bg-teal px-1.5 py-0.5 font-bold whitespace-nowrap text-on-accent">
      ▲ {compactNumber(Math.round(perDay))}/day
    </span>
  );
}

export function ToolCard({ tool, now }: { tool: Tool; now: number }) {
  return (
    <article className="flex flex-col gap-3 border-2 border-ink bg-paper-raised p-4 shadow-hard-sm transition-[transform,box-shadow] hover:-translate-x-0.5 hover:-translate-y-0.5 hover:shadow-hard">
      <div className="flex items-start justify-between gap-3">
        <h2 className="min-w-0 font-semibold break-words">
          <a href={tool.url} target="_blank" rel="noopener" className="hover:text-tomato">
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
                className="inline-block border border-ink px-1.5 py-0.5 font-mono text-[11px] hover:bg-mustard hover:text-[#171614]"
              >
                #{topic}
              </Link>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-auto flex flex-wrap gap-x-3 border-t border-hairline pt-3 font-mono text-[11px] text-muted">
        <span>★ {compactNumber(tool.stars)}</span>
        {tool.language && <span>{tool.language}</span>}
        {tool.pushed_at && <span>updated {timeAgo(tool.pushed_at, now)}</span>}
      </p>
    </article>
  );
}
