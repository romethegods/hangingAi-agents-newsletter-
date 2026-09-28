export function FeedSkeleton({ rows = 8 }: { rows?: number }) {
  return (
    <div aria-busy="true" aria-label="Loading" className="animate-pulse">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="space-y-2 border-b border-border py-4">
          <div className="h-4 w-4/5 rounded bg-border" />
          <div className="h-3 w-3/5 rounded bg-border" />
        </div>
      ))}
    </div>
  );
}

export function CardGridSkeleton({ cards = 6 }: { cards?: number }) {
  return (
    <div aria-busy="true" aria-label="Loading" className="grid animate-pulse gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: cards }, (_, i) => (
        <div key={i} className="h-40 rounded-lg border border-border bg-surface" />
      ))}
    </div>
  );
}
