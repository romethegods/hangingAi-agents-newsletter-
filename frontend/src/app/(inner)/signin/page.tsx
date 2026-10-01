import type { Metadata } from "next";
import { Suspense } from "react";

import { PageHeader } from "@/components/PageHeader";
import { requestSignInLink } from "@/lib/actions";
import { param } from "@/lib/url";

export const metadata: Metadata = { title: "Add your email", robots: { index: false } };

const ERRORS: Record<string, string> = {
  "invalid-email": "That doesn't look like an email address.",
  "slow-down": "Too many sign-in requests. Wait a minute and try again.",
  "expired-link": "That sign-in link was already used or has expired. Request a new one.",
};

export default function SignInPage({ searchParams }: PageProps<"/signin">) {
  return (
    <div className="mx-auto max-w-xl">
      <PageHeader kicker="Optional" title="Add your email">
        You don&apos;t need an account to follow, vote or comment. An email only lets us send your
        brief each morning, and lets you use your name and follows on another device.
      </PageHeader>
      <Suspense>
        <SignInForm searchParams={searchParams} />
      </Suspense>
    </div>
  );
}

async function SignInForm({ searchParams }: Pick<PageProps<"/signin">, "searchParams">) {
  const query = await searchParams;
  const sent = param(query, "sent");
  const error = ERRORS[param(query, "error") ?? ""];

  if (sent) {
    return (
      <div className="border-[3px] border-ink bg-paper-raised p-6 shadow-hard">
        <p className="kicker text-tomato">Check your inbox</p>
        <p className="mt-2 text-lg">
          We sent a sign-in link to <strong>{sent}</strong>. It works once and expires in 20 minutes.
        </p>
        <p className="mt-3 text-sm text-muted">No email? Check spam, or try again in a minute.</p>
      </div>
    );
  }

  return (
    <form action={requestSignInLink} className="space-y-4 border-[3px] border-ink bg-paper-raised p-6 shadow-hard">
      <input type="hidden" name="next" value={param(query, "next") ?? "/brief"} />
      <label htmlFor="email" className="kicker block font-bold">
        Email address
      </label>
      <input
        id="email"
        name="email"
        type="email"
        required
        autoComplete="email"
        defaultValue={param(query, "email")}
        placeholder="you@example.com"
        className="w-full border-2 border-ink bg-paper px-3 py-2.5 text-base"
      />
      {error && (
        <p role="alert" className="text-sm font-semibold text-tomato">
          {error}
        </p>
      )}
      <button
        type="submit"
        className="kicker border-2 border-ink bg-tomato px-5 py-3 text-[0.8rem] font-bold text-on-accent shadow-hard-sm hover:opacity-90"
      >
        Email me a sign-in link
      </button>
      <p className="text-sm text-muted">No password. Already used this email? You&apos;ll pick up where you left off. Unsubscribe anytime.</p>
    </form>
  );
}
