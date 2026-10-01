import Link from "next/link";

import { compactNumber, timeAgo } from "@/lib/format";
import { DEMO_LABEL, displayName, popularity, previewImage } from "@/lib/tools";
import type { Tool } from "@/lib/types";
import { withQuery } from "@/lib/url";

import { RemoteImage } from "./RemoteImage";
import { ToolPoster } from "./ToolPoster";

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
    <span className="font-mono text-[11px] font-bold whitespace-nowrap text-teal">
      ▲ {compactNumber(Math.round(perDay))}/day
    </span>
  );
}

export function DemoBadge({ tool }: { tool: Tool }) {
  if (!tool.demo_kind) return null;
  const live = tool.demo_kind !== "image";
  return (
    <span
      className={`kicker inline-block border-2 border-ink px-1.5 py-0.5 font-bold ${
        live ? "bg-mustard text-[#171614]" : "bg-paper-raised text-ink"
      }`}
    >
      {DEMO_LABEL[tool.demo_kind]}
    </span>
  );
}

export function ToolCard({ tool, now }: { tool: Tool; now: number }) {
  const href = `/tools/${tool.id}`;
  return (
    <article className="flex flex-col border-2 border-ink bg-paper-raised transition-[transform,box-shadow] hover:-translate-x-0.5 hover:-translate-y-0.5 hover:shadow-hard">
      <Link href={href} className="relative block" tabIndex={-1} aria-hidden="true">
        <RemoteImage
          src={previewImage(tool)}
          fallback={<ToolPoster tool={tool} />}
          alt=""
          sizes="(min-width: 1024px) 380px, (min-width: 640px) 50vw, 100vw"
          className="border-0 border-b-2"
        />
        <span className="absolute top-2 left-2">
          <DemoBadge tool={tool} />
        </span>
      </Link>
      <div className="flex flex-1 flex-col gap-3 p-4">
        <div className="flex items-start justify-between gap-3">
          <h2 className="min-w-0 font-semibold break-words">
            <Link href={href} className="hover:text-tomato">
              {tool.title ? tool.title : <ToolName fullName={tool.full_name} />}
            </Link>
          </h2>
          <StarVelocity perDay={tool.star_velocity} />
        </div>
        {tool.description && <p className="line-clamp-3 text-sm text-muted">{tool.description}</p>}
        {tool.topics.length > 0 && (
          <ul className="flex flex-wrap gap-1.5">
            {tool.topics.slice(0, 3).map((topic) => (
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
          <span>{popularity(tool)}</span>
          {tool.votes > 0 && <span>▲ {tool.votes}</span>}
          {tool.comments > 0 && <span>💬 {tool.comments}</span>}
          {tool.language && <span>{tool.language}</span>}
          {tool.platform === "huggingface" && <span>HF Space</span>}
          {tool.pushed_at && <span>updated {timeAgo(tool.pushed_at, now)}</span>}
        </p>
      </div>
    </article>
  );
}

/** Compact media card for the front page's demo reel. */
export function DemoReelCard({ tool }: { tool: Tool }) {
  return (
    <Link href={`/tools/${tool.id}`} className="group block space-y-2">
      <div className="relative transition-[transform,box-shadow] group-hover:-translate-x-0.5 group-hover:-translate-y-0.5 group-hover:shadow-hard">
        <RemoteImage
          src={previewImage(tool)}
          fallback={<ToolPoster tool={tool} />}
          alt=""
          sizes="(min-width: 640px) 420px, 100vw"
        />
        <span className="absolute top-2 left-2">
          <DemoBadge tool={tool} />
        </span>
      </div>
      <p className="font-display text-lg leading-snug font-semibold group-hover:text-tomato">
        {displayName(tool)}
      </p>
      <p className="font-mono text-[11px] text-muted">
        {popularity(tool)} · {tool.platform === "huggingface" ? "HF Space" : tool.full_name.split("/")[0]}
      </p>
    </Link>
  );
}
