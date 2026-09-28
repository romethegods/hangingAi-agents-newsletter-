import { Squiggle } from "./Geometry";

export function EmptyState({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="halftone border-2 border-dashed border-ink px-6 py-12 text-center">
      <p className="font-display text-xl font-semibold">{title}</p>
      <Squiggle className="mx-auto my-3 h-3 w-24 text-tomato" />
      {children && <div className="text-sm text-muted">{children}</div>}
    </div>
  );
}
