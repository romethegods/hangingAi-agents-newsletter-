/** Newsletter section heading: "§01 — Top stories" over a thick ink rule. */
export function SectionHeader({
  number,
  title,
  id,
  aside,
}: {
  number: number;
  title: string;
  id?: string;
  aside?: React.ReactNode;
}) {
  return (
    <div className="mb-4 flex items-end justify-between gap-4 border-b-[3px] border-ink pb-2">
      <h2 id={id} className="flex items-baseline gap-3">
        <span className="kicker text-tomato">§{String(number).padStart(2, "0")}</span>
        <span className="font-display text-xl font-semibold tracking-tight">{title}</span>
      </h2>
      {aside}
    </div>
  );
}
