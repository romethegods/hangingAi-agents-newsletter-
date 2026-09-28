/**
 * Flat 90s-style geometric marks. Decorative only (aria-hidden); every shape
 * uses a 2px ink stroke so it reads as print, not as a glowing UI element.
 */

const STROKE = { stroke: "var(--ink)", strokeWidth: 2 } as const;

export function MastheadArt({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 220 110" aria-hidden="true" className={className}>
      <circle cx="44" cy="58" r="34" fill="var(--tomato)" {...STROKE} />
      <rect
        x="84"
        y="20"
        width="54"
        height="54"
        fill="var(--cobalt)"
        transform="rotate(12 111 47)"
        {...STROKE}
      />
      <polygon points="150,96 184,30 214,96" fill="var(--mustard)" {...STROKE} />
      <path
        d="M8 104 q12 -12 24 0 t24 0 t24 0 t24 0 t24 0"
        fill="none"
        stroke="var(--ink)"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
      {[0, 1, 2].map((row) =>
        [0, 1, 2, 3].map((col) => (
          <circle key={`${row}-${col}`} cx={160 + col * 10} cy={8 + row * 8} r="1.8" fill="var(--ink)" />
        )),
      )}
    </svg>
  );
}

/** Rank badge for leaderboards: 1 = circle, 2 = square, 3 = triangle, then plain numerals. */
export function RankMark({ rank }: { rank: number }) {
  const label = String(rank).padStart(2, "0");
  if (rank > 3) {
    return <span className="kicker inline-block w-8 text-center text-muted">{label}</span>;
  }
  const shape = {
    1: <circle cx="16" cy="16" r="13" fill="var(--tomato)" {...STROKE} />,
    2: <rect x="4" y="4" width="24" height="24" fill="var(--cobalt)" {...STROKE} />,
    3: <polygon points="16,3 30,28 2,28" fill="var(--mustard)" {...STROKE} />,
  }[rank];
  return (
    <span className="relative inline-flex h-8 w-8 shrink-0 items-center justify-center">
      <svg viewBox="0 0 32 32" aria-hidden="true" className="absolute inset-0">
        {shape}
      </svg>
      <span
        className={`relative font-mono text-[11px] font-bold ${rank === 3 ? "pt-2 text-[#171614]" : "text-on-accent"}`}
      >
        {rank}
      </span>
    </span>
  );
}

export function Squiggle({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 120 12" aria-hidden="true" className={className} preserveAspectRatio="none">
      <path
        d="M2 6 q7.5 -8 15 0 t15 0 t15 0 t15 0 t15 0 t15 0 t15 0 t15 0"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}
