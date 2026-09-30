import type { Metadata } from "next";

import { PageHeader } from "@/components/PageHeader";
import { SectionHeader } from "@/components/SectionHeader";

export const metadata: Metadata = {
  title: "About",
  description: "What HangingAi is, where its content comes from, and how our crawler behaves.",
};

const SOURCES = [
  ["Hugging Face", "Daily Papers, trending models, and trending Spaces (live demo apps)"],
  ["GitHub", "Trending repositories, the ai-agents, llm, mcp and rag topics, and README demos"],
  ["News outlets", "AI stories only, filtered from general coverage"],
];

export default function AboutPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-10 leading-relaxed">
      <section className="space-y-3">
        <PageHeader kicker="The masthead" title="About HangingAi" />
        <p className="text-lg">
          AI moves fast, and the good stuff is spread across research hubs, GitHub and the news.
          HangingAi collects the papers, models, news and open-source agent tools that matter,
          removes duplicates, and ranks them so you can catch up in minutes.
        </p>
      </section>

      <section className="space-y-3">
        <SectionHeader number={1} title="Where content comes from" />
        <ul className="list-[square] space-y-1 pl-5 marker:text-tomato">
          {SOURCES.map(([name, detail]) => (
            <li key={name}>
              <strong>{name}</strong>: {detail}
            </li>
          ))}
        </ul>
        <p className="text-muted">
          We store headlines, short summaries and links. Every item points back to the original
          publisher; we never republish full articles. Images and demos load straight from where
          their creators published them (YouTube&apos;s player, Hugging Face Spaces, GitHub); we
          never download or re-host them.
        </p>
      </section>

      <section id="crawler" className="scroll-mt-20 space-y-3">
        <SectionHeader number={2} title="Our crawler" />
        <p>
          HangingAi&apos;s crawler identifies itself with this token in its user agent:
        </p>
        <pre className="overflow-x-auto border-2 border-ink bg-paper-raised p-4 font-mono text-sm shadow-hard-sm">
          HangingAiBot/0.1 (+https://hangingai.com/bot)
        </pre>
        <ul className="list-[square] space-y-1 pl-5 marker:text-tomato">
          <li>
            It obeys <code className="font-mono">robots.txt</code>, including{" "}
            <code className="font-mono">Crawl-delay</code>.
          </li>
          <li>It loads a handful of listing pages per site, at most once every few seconds.</li>
          <li>It does not attempt to get around logins, paywalls or bot protection.</li>
        </ul>
        <p>To opt out, add this to your robots.txt. We pick up changes within 12 hours:</p>
        <pre className="overflow-x-auto border-2 border-ink bg-paper-raised p-4 font-mono text-sm shadow-hard-sm">
          {"User-agent: HangingAiBot\nDisallow: /"}
        </pre>
      </section>
    </div>
  );
}
