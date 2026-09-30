import type { Tool } from "@/lib/types";

const COLORS = ["var(--tomato)", "var(--cobalt)", "var(--mustard)", "var(--teal)"];

/** Deterministic per tool, so the same repo always gets the same poster. */
function pick(seed: string, n: number): number {
  let hash = 0;
  for (const char of seed) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return hash % n;
}

/**
 * Our own cover for tools without an uploaded preview: flat 90s shapes and the
 * tool's name, instead of GitHub's generated card that repeats the text around it.
 * Name sits bottom-left so a centered play button never covers it.
 */
export function ToolPoster({ tool }: { tool: Tool }) {
  const [owner, repo = owner] = tool.full_name.split("/");
  const name = tool.title ?? repo;
  const i = pick(tool.full_name, COLORS.length);
  const shape = pick(repo, 3);
  const [main, second] = [COLORS[i], COLORS[(i + 1) % COLORS.length]];

  return (
    <div className="halftone absolute inset-0 bg-paper-raised">
      <svg viewBox="0 0 160 90" aria-hidden="true" className="absolute inset-0 h-full w-full" preserveAspectRatio="xMaxYMid slice">
        {shape === 0 && <circle cx="128" cy="30" r="22" fill={main} stroke="var(--ink)" strokeWidth="1.5" />}
        {shape === 1 && (
          <rect x="106" y="10" width="40" height="40" fill={main} stroke="var(--ink)" strokeWidth="1.5" transform="rotate(10 126 30)" />
        )}
        {shape === 2 && <polygon points="104,54 128,8 152,54" fill={main} stroke="var(--ink)" strokeWidth="1.5" />}
        <rect x="140" y="52" width="14" height="14" fill={second} stroke="var(--ink)" strokeWidth="1.5" />
      </svg>
      <div className="absolute inset-x-0 bottom-0 p-3 sm:p-4">
        <p className="font-mono text-[10px] tracking-wide text-muted uppercase">{owner}</p>
        <p className="line-clamp-2 font-display text-lg leading-tight font-black break-words text-ink sm:text-xl">
          {name}
        </p>
      </div>
    </div>
  );
}
