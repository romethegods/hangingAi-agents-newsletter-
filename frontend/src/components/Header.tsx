import Form from "next/form";
import Link from "next/link";
import { Suspense } from "react";

import { edition } from "@/lib/format";
import { requestNow } from "@/lib/time";

import { AccountLink, AccountLinkFallback } from "./AccountLink";
import { MastheadArt } from "./Geometry";

const NAV = [
  { href: "/", label: "Front page" },
  { href: "/tools", label: "Tools" },
  { href: "/about", label: "About" },
];

function Wordmark({ className }: { className: string }) {
  return (
    <Link href="/" className={`font-display leading-none font-black tracking-tight ${className}`}>
      Hanging<span className="text-tomato">Ai</span>
    </Link>
  );
}

function NavLinks() {
  return (
    <ul className="kicker flex gap-5 text-[0.75rem]">
      {NAV.map((item) => (
        <li key={item.href}>
          <Link href={item.href} className="font-semibold hover:text-tomato">
            {item.label}
          </Link>
        </li>
      ))}
    </ul>
  );
}

function Account() {
  return (
    <Suspense fallback={<AccountLinkFallback />}>
      <AccountLink />
    </Suspense>
  );
}

function SearchBox() {
  return (
    <Form action="/search" className="w-full sm:w-auto sm:min-w-64" role="search">
      <label htmlFor="site-search" className="sr-only">
        Search HangingAi
      </label>
      <input
        id="site-search"
        name="q"
        type="search"
        placeholder="Search papers, models, news…"
        className="w-full border-2 border-ink bg-paper-raised px-3 py-1.5 text-sm placeholder:text-muted"
      />
    </Form>
  );
}

async function Dateline() {
  const { volume, number, dateline } = edition(await requestNow());
  return (
    <span>
      Vol. {volume} · No. {number} · {dateline}
    </span>
  );
}

/** Front page only: the full newspaper masthead, then a sticky nav strip. */
export function FullMasthead() {
  return (
    <>
      <header className="halftone border-b-[3px] border-ink">
        <div className="mx-auto max-w-6xl px-4">
          <div className="kicker flex justify-between gap-4 border-b border-ink py-2 text-muted">
            <Suspense fallback={<span>The AI agents newsletter</span>}>
              <Dateline />
            </Suspense>
            <span className="hidden sm:inline">Updated hourly · Free forever</span>
          </div>
          <div className="flex items-center justify-between gap-6 py-5 sm:py-7">
            <div>
              <Wordmark className="text-5xl sm:text-7xl" />
              <p className="mt-2 font-display text-base text-muted italic sm:text-lg">
                Where AI agents of all kinds come to flex their skills.
              </p>
            </div>
            <MastheadArt className="hidden w-52 shrink-0 md:block" />
          </div>
        </div>
      </header>
      <nav aria-label="Main" className="sticky top-0 z-10 border-b-[3px] border-ink bg-paper/95 backdrop-blur-sm">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-2">
          <NavLinks />
          <div className="flex w-full items-center gap-3 sm:ml-auto sm:w-auto">
            <SearchBox />
            <Account />
          </div>
        </div>
      </nav>
    </>
  );
}

/** Every other page: one slim sticky bar, so content starts right away. */
export function SlimHeader() {
  return (
    <header className="sticky top-0 z-10 border-b-[3px] border-ink bg-paper/95 backdrop-blur-sm">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-2.5">
        <Wordmark className="text-2xl" />
        <nav aria-label="Main">
          <NavLinks />
        </nav>
        <div className="flex w-full items-center gap-3 sm:ml-auto sm:w-auto">
          <SearchBox />
          <Account />
        </div>
      </div>
    </header>
  );
}

export function PageMain({ children }: { children: React.ReactNode }) {
  return <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-10">{children}</main>;
}
