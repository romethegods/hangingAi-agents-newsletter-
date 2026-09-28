import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Form from "next/form";
import Link from "next/link";

import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

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
  { href: "/", label: "Feed" },
  { href: "/tools", label: "Tools" },
  { href: "/about", label: "About" },
];

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col font-sans">
        <header className="sticky top-0 z-10 border-b border-border bg-background/90 backdrop-blur">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
            <Link href="/" className="text-lg font-bold tracking-tight">
              Hanging<span className="text-accent">Ai</span>
            </Link>
            <nav className="flex gap-4 text-sm">
              {NAV.map((item) => (
                <Link key={item.href} href={item.href} className="text-muted hover:text-foreground">
                  {item.label}
                </Link>
              ))}
            </nav>
            <Form action="/search" className="w-full sm:ml-auto sm:w-auto sm:min-w-72" role="search">
              <label htmlFor="site-search" className="sr-only">
                Search HangingAi
              </label>
              <input
                id="site-search"
                name="q"
                type="search"
                placeholder="Search papers, models, news…"
                className="w-full rounded-md border border-border bg-surface px-3 py-1.5 text-sm placeholder:text-muted"
              />
            </Form>
          </div>
        </header>

        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">{children}</main>

        <footer className="border-t border-border py-6 text-sm text-muted">
          <div className="mx-auto flex max-w-6xl flex-wrap justify-between gap-2 px-4">
            <p>HangingAi collects public headlines; every story links to its original publisher.</p>
            <Link href="/about#crawler" className="hover:text-foreground">
              About our crawler
            </Link>
          </div>
        </footer>
      </body>
    </html>
  );
}
