import type { Metadata } from "next";
import { Suspense } from "react";

import { completeSignIn } from "@/lib/actions";
import { param } from "@/lib/url";

export const metadata: Metadata = { title: "Sign in", robots: { index: false } };

/**
 * The emailed link lands here, and signing in takes one more press. Email security
 * scanners open every link they see; if opening the link signed you in, a scanner
 * would use up the single-use link before you ever clicked it.
 */
export default function VerifyPage({ searchParams }: PageProps<"/auth/verify">) {
  return (
    <div className="mx-auto max-w-md py-8 text-center">
      <Suspense>
        <Confirm searchParams={searchParams} />
      </Suspense>
    </div>
  );
}

async function Confirm({ searchParams }: Pick<PageProps<"/auth/verify">, "searchParams">) {
  const query = await searchParams;
  return (
    <form action={completeSignIn} className="space-y-5">
      <input type="hidden" name="token" value={param(query, "token") ?? ""} />
      <input type="hidden" name="next" value={param(query, "next") ?? "/brief"} />
      <p className="kicker text-tomato">One last step</p>
      <h1 className="font-display text-4xl font-black">Welcome to HangingAi</h1>
      <button
        type="submit"
        className="kicker border-2 border-ink bg-tomato px-6 py-3 text-sm font-bold text-on-accent shadow-hard hover:opacity-90"
      >
        Continue to my brief →
      </button>
    </form>
  );
}
