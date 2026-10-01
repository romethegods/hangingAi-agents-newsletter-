import type { Standing } from "@/lib/types";

/** Arena standings. Provisional (under 30 battles) ratings are marked: they still move a lot. */
export function ArenaLeaderboard({ rows, limit }: { rows: Standing[]; limit?: number }) {
  const shown = limit ? rows.slice(0, limit) : rows;
  if (shown.length === 0) return <p className="text-sm text-muted">No battles yet. Be the first.</p>;
  return (
    <table className="w-full border-collapse text-left text-sm">
      <thead>
        <tr className="kicker border-b-[3px] border-ink text-muted">
          <th className="py-2 pr-2">#</th>
          <th className="py-2 pr-2">Model</th>
          <th className="py-2 pr-2 text-right">Rating</th>
          <th className="py-2 pr-2 text-right">Win rate</th>
          <th className="py-2 text-right">Battles</th>
        </tr>
      </thead>
      <tbody>
        {shown.map((row, i) => (
          <tr key={row.slug} className="border-b border-hairline">
            <td className="py-2.5 pr-2 font-mono text-muted">{String(i + 1).padStart(2, "0")}</td>
            <td className="py-2.5 pr-2">
              <span className="font-semibold">{row.name}</span>
              <span className="block font-mono text-[11px] text-muted">
                {row.maker}
                {row.open_weights ? " · open weights" : ""}
              </span>
            </td>
            <td className="py-2.5 pr-2 text-right font-mono font-bold tabular-nums">
              {Math.round(row.rating)}
              {row.provisional && (
                <span title="Fewer than 30 battles: this rating will still move" className="ml-1 text-muted">
                  ?
                </span>
              )}
            </td>
            <td className="py-2.5 pr-2 text-right font-mono tabular-nums">
              {row.win_rate === null ? "–" : `${Math.round(row.win_rate * 100)}%`}
            </td>
            <td className="py-2.5 text-right font-mono tabular-nums">{row.battles}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
