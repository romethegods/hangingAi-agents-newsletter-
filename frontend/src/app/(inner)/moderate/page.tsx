import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { PageHeader } from "@/components/PageHeader";
import { FeedSkeleton } from "@/components/Skeleton";
import { moderate } from "@/lib/actions";
import { timeAgo } from "@/lib/format";
import { getModerationQueue } from "@/lib/session";
import { requestNow } from "@/lib/time";

export const metadata: Metadata = { title: "Moderation", robots: { index: false } };

export default function ModeratePage() {
  return (
    <Suspense fallback={<FeedSkeleton />}>
      <Queue />
    </Suspense>
  );
}

function Action({ name, label, hidden }: { name: string; label: string; hidden: Record<string, string | number> }) {
  return (
    <form action={moderate}>
      <input type="hidden" name="action" value={name} />
      {Object.entries(hidden).map(([k, v]) => (
        <input key={k} type="hidden" name={k} value={v} />
      ))}
      <button type="submit" className="kicker border-2 border-ink px-2.5 py-1 font-bold hover:bg-mustard">
        {label}
      </button>
    </form>
  );
}

async function Queue() {
  const [items, now] = await Promise.all([getModerationQueue(), requestNow()]);
  if (items === null) {
    return (
      <div className="mx-auto max-w-md py-12 text-center">
        <h1 className="font-display text-3xl font-black">Moderators only</h1>
        <p className="mt-2 text-muted">Sign in with a moderator email to review reported comments.</p>
      </div>
    );
  }
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader kicker="Moderation" title="Review queue">
        Hidden comments (3+ reports) first, then anything reported. Restore, remove, or ban the author.
      </PageHeader>
      {items.length === 0 ? (
        <p className="text-muted">Nothing to review. 🎉</p>
      ) : (
        <ul className="divide-y divide-hairline">
          {items.map((item) => (
            <li key={item.id} className="space-y-2 py-5">
              <p className="font-mono text-[11px] text-muted">
                <strong className="text-ink">{item.author}</strong> · {timeAgo(item.created_at, now)} ·{" "}
                <span className={item.status === "hidden" ? "font-bold text-tomato" : ""}>
                  {item.status === "hidden" ? "HIDDEN" : "visible"} · {item.report_count} report
                  {item.report_count === 1 ? "" : "s"}
                </span>{" "}
                ·{" "}
                <Link href={`/${item.target_kind === "tool" ? "tools" : "item"}/${item.target_id}#comment-${item.id}`} className="underline">
                  view in context
                </Link>
              </p>
              <p className="whitespace-pre-line break-words">{item.body}</p>
              <div className="flex flex-wrap gap-2">
                <Action name="restore" label="Restore" hidden={{ id: item.id }} />
                <Action name="remove" label="Remove" hidden={{ id: item.id }} />
                <Action name="ban" label={`Ban ${item.author}`} hidden={{ user_id: item.author_id }} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
