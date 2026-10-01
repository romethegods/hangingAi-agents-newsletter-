import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { BattleView } from "@/components/BattleView";
import { FeedSkeleton } from "@/components/Skeleton";
import { getBattle } from "@/lib/session";

export const metadata: Metadata = { title: "Arena battle", robots: { index: false } };

export default function BattlePage({ params }: PageProps<"/arena/b/[id]">) {
  return (
    <div className="space-y-6">
      <Link href="/arena" className="kicker font-semibold text-muted hover:text-tomato">
        ← The Arena
      </Link>
      <Suspense fallback={<FeedSkeleton rows={4} />}>
        <Battle params={params} />
      </Suspense>
    </div>
  );
}

async function Battle({ params }: Pick<PageProps<"/arena/b/[id]">, "params">) {
  const id = Number((await params).id);
  const battle = Number.isSafeInteger(id) && id > 0 ? await getBattle(id) : null;
  if (!battle) notFound(); // also: someone else's battle that wasn't shared
  return <BattleView initial={battle} />;
}
