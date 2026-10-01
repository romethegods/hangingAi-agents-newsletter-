import Link from "next/link";

import { sessionToken } from "@/lib/session";

/** Reads the session cookie, so it renders per request inside a Suspense boundary. */
export async function AccountLink() {
  const signedIn = Boolean(await sessionToken());
  return (
    <Link
      href={signedIn ? "/brief" : "/signin"}
      className="kicker border-2 border-ink bg-tomato px-2.5 py-1 text-[0.7rem] font-bold whitespace-nowrap text-on-accent hover:opacity-90"
    >
      {signedIn ? "My brief" : "Your brief"}
    </Link>
  );
}

export function AccountLinkFallback() {
  return (
    <Link href="/signin" className="kicker border-2 border-ink px-2.5 py-1 text-[0.7rem] font-bold whitespace-nowrap">
      Daily brief
    </Link>
  );
}
