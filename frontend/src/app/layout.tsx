import type { Metadata } from "next";
import { Fraunces, Geist, Geist_Mono } from "next/font/google";
import Form from "next/form";
import Link from "next/link";
import { Suspense } from "react";

import { MastheadArt } from "@/components/Geometry";
import { edition } from "@/lib/format";
import { requestNow } from "@/lib/time";

import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });
const fraunces = Fraunces({ variable: "--font-fraunces", subsets: ["latin"] });

export const metadata: Metadata = {
  metadataBase: new URL(process.env.SITE_URL ?? "https://hangingai.com"),
  title: {
    default: "HangingAi: AI news, papers & open-source agent tools",
    template: "%s · HangingAi",
  },
  description:
    "The AI news, research papers, trending models and open-source agent tools that matter, collected and ranked every hour.",
  openGraph: { siteName: "HangingAi", type: "website" },
};

const NAV = [
  { href: "/", label: "Front page" },
  { href: "/tools", label: "Tools" },
  { href: "/about", label: "About" },
];

async function Dateline() {
  const { volume, number, dateline } = edition(await requestNow());
  return (
    <span>
      Vol. {volume} · No. {number} · {dateline}
    </span>
  );
}

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} ${fraunces.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col font-sans">
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
                <Link href="/" className="font-display text-5xl leading-none font-black tracking-tight sm:text-7xl">
                  Hanging<span className="text-tomato">Ai</span>
                </Link>
                <p className="mt-2 font-display text-base text-muted italic sm:text-lg">
                  Where AI agents of all kinds come to flex their skills.
                </p>
              </div>
              <MastheadArt className="hidden w-52 shrink-0 md:block" />
            </div>
          </div>
        </header>

        <nav
          aria-label="Main"
          className="sticky top-0 z-10 border-b-[3px] border-ink bg-paper/95 backdrop-blur-sm"
        >
          <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-2">
            <ul className="kicker flex gap-5 text-[0.75rem]">
              {NAV.map((item) => (
                <li key={item.href}>
                  <Link href={item.href} className="font-semibold hover:text-tomato">
                    {item.label}
                  </Link>
                </li>
              ))}
            </ul>
            <Form action="/search" className="w-full sm:ml-auto sm:w-auto sm:min-w-72" role="search">
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
          </div>
        </nav>

        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-10">{children}</main>

        <footer className="halftone border-t-[3px] border-ink">
          <div className="mx-auto grid max-w-6xl gap-6 px-4 py-8 sm:grid-cols-[1fr_auto]">
            <div className="space-y-2">
              <p className="font-display text-2xl font-black">
                Hanging<span className="text-tomato">Ai</span>
              </p>
              <p className="max-w-md text-sm text-muted">
                We collect public headlines and link every story to its original publisher. Papers
                from Hugging Face, tools from GitHub, news from around the web.
              </p>
            </div>
            <ul className="kicker space-y-1 text-muted sm:text-right">
              <li>
                <Link href="/tools" className="hover:text-ink">
                  Open-source tools
                </Link>
              </li>
              <li>
                <Link href="/about" className="hover:text-ink">
                  About
                </Link>
              </li>
              <li>
                <Link href="/about#crawler" className="hover:text-ink">
                  Our crawler
                </Link>
              </li>
            </ul>
          </div>
        </footer>
      </body>
    </html>
  );
}
