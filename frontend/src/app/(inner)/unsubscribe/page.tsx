import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { confirmUnsubscribe } from "@/lib/actions";
import { param } from "@/lib/url";

export const metadata: Metadata = { title: "Unsubscribe", robots: { index: false } };

// Confirm with a button rather than unsubscribing on page load: mail scanners open links too.
export default function UnsubscribePage({ searchParams }: PageProps<"/unsubscribe">) {
  return (
    <div className="mx-auto max-w-md space-y-5 py-8 text-center">
      <Suspense>
        <Body searchParams={searchParams} />
      </Suspense>
    </div>
  );
}

async function Body({ searchParams }: Pick<PageProps<"/unsubscribe">, "searchParams">) {
  const query = await searchParams;
  if (param(query, "done")) {
    return (
      <>
        <h1 className="font-display text-4xl font-black">You&apos;re unsubscribed</h1>
        <p className="text-muted">No more daily briefs. You can turn them back on from your brief page anytime.</p>
        <Link href="/" className="kicker inline-block border-2 border-ink px-4 py-2 font-semibold hover:bg-mustard">
          Back to the front page
        </Link>
      </>
    );
  }
  if (param(query, "error")) {
    return <p className="font-semibold text-tomato">That unsubscribe link isn&apos;t valid. Sign in to change your settings.</p>;
  }
  return (
    <form action={confirmUnsubscribe} className="space-y-5">
      <input type="hidden" name="u" value={param(query, "u") ?? ""} />
      <input type="hidden" name="t" value={param(query, "t") ?? ""} />
      <h1 className="font-display text-4xl font-black">Stop the daily brief?</h1>
      <button type="submit" className="kicker border-2 border-ink bg-tomato px-5 py-3 font-bold text-on-accent shadow-hard-sm">
        Unsubscribe
      </button>
    </form>
  );
}
