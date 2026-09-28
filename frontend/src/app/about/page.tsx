import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "About",
  description: "What HangingAi is, where its content comes from, and how our crawler behaves.",
};

const SOURCES = [
  ["Hugging Face", "Daily Papers and trending models"],
  ["GitHub", "Trending repositories and the ai-agents, llm, mcp and rag topics"],
  ["News outlets", "AI stories only, filtered from general coverage"],
];

export default function AboutPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-10 leading-relaxed">
      <section className="space-y-3">
        <h1 className="text-3xl font-bold tracking-tight">About HangingAi</h1>
        <p>
          AI moves fast, and the good stuff is spread across research hubs, GitHub and the news.
          HangingAi collects the papers, models, news and open-source agent tools that matter,
          removes duplicates, and ranks them so you can catch up in minutes.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Where content comes from</h2>
        <ul className="list-disc space-y-1 pl-5">
          {SOURCES.map(([name, detail]) => (
            <li key={name}>
              <strong>{name}</strong>: {detail}
            </li>
          ))}
        </ul>
        <p className="text-muted">
          We store headlines, short summaries and links. Every item points back to the original
          publisher; we never republish full articles.
        </p>
      </section>

      <section id="crawler" className="scroll-mt-20 space-y-3">
        <h2 className="text-xl font-semibold">Our crawler</h2>
        <p>
          HangingAi&apos;s crawler identifies itself with this token in its user agent:
        </p>
        <pre className="overflow-x-auto rounded-md border border-border bg-surface p-3 font-mono text-sm">
          HangingAiBot/0.1 (+https://hangingai.com/bot)
        </pre>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            It obeys <code className="font-mono">robots.txt</code>, including{" "}
            <code className="font-mono">Crawl-delay</code>.
          </li>
          <li>It loads a handful of listing pages per site, at most once every few seconds.</li>
          <li>It does not attempt to get around logins, paywalls or bot protection.</li>
        </ul>
        <p>To opt out, add this to your robots.txt. We pick up changes within 12 hours:</p>
        <pre className="overflow-x-auto rounded-md border border-border bg-surface p-3 font-mono text-sm">
          {"User-agent: HangingAiBot\nDisallow: /"}
        </pre>
      </section>
    </div>
  );
}
