import type { Metadata } from "next";
import { Fraunces, Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";

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

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} ${fraunces.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col font-sans">
        {children}

        <footer className="border-t-[3px] border-ink">
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
