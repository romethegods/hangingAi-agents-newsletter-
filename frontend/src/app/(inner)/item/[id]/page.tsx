import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { ArticleMeta, FeedItem } from "@/components/FeedItem";
import { SectionHeader } from "@/components/SectionHeader";
import { ChatSection } from "@/components/ChatSection";
import { RemoteImage } from "@/components/RemoteImage";
import { VoteButton } from "@/components/VoteButton";
import { getVoteState } from "@/lib/session";
import { FeedSkeleton } from "@/components/Skeleton";
import { getArticle } from "@/lib/api";
import { CONTENT_TYPE_LONG, hostname } from "@/lib/format";
import type { ArticleDetail } from "@/lib/types";
import { requestNow } from "@/lib/time";

// Missing items are soft 404s: the shell has already streamed with a 200, so Next
// adds <meta name="robots" content="noindex"> instead. A hard 404 would need a
// proxy-level lookup on every request; not worth it for now.
async function load(params: PageProps<"/item/[id]">["params"]): Promise<ArticleDetail> {
  const id = Number((await params).id);
  const article = Number.isSafeInteger(id) && id > 0 ? await getArticle(id) : null;
  if (!article) notFound();
  return article;
}

export async function generateMetadata({ params }: PageProps<"/item/[id]">): Promise<Metadata> {
  const article = await load(params);
  return {
    title: article.title,
    description: article.summary ?? `${article.title}, via ${article.source.name}`,
    openGraph: { title: article.title, type: "article", publishedTime: article.published_at },
  };
}

export default function ItemPage({ params }: PageProps<"/item/[id]">) {
  return (
    <Suspense fallback={<FeedSkeleton rows={3} />}>
      <Item params={params} />
    </Suspense>
  );
}

async function Item({ params }: Pick<PageProps<"/item/[id]">, "params">) {
  const article = await load(params);
  const [now, vote] = await Promise.all([requestNow(), getVoteState("article", article.id)]);
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": article.content_type === "paper" ? "ScholarlyArticle" : "NewsArticle",
    headline: article.title,
    datePublished: article.published_at,
    url: article.url,
    ...(article.author && { author: { "@type": "Person", name: article.author } }),
  };

  return (
    <article className="mx-auto max-w-3xl">
      <script
        type="application/ld+json"
        // JSON.stringify output with "<" escaped cannot break out of the script tag.
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd).replace(/</g, "\\u003c") }}
      />
      <Link href="/" className="kicker font-semibold text-muted hover:text-tomato">
        ← Front page
      </Link>
      <header className="mt-6 space-y-5 border-b-[3px] border-ink pb-6">
        <p className="kicker text-tomato">{CONTENT_TYPE_LONG[article.content_type]}</p>
        <h1 className="font-display text-4xl leading-[1.05] font-black tracking-tight sm:text-5xl">
          {article.title}
        </h1>
        <ArticleMeta article={article} now={now} full />
      </header>
      {article.image_url && (
        <div className="mt-6">
          <RemoteImage
            src={article.image_url}
            alt=""
            sizes="(min-width: 768px) 768px, 100vw"
            position={article.content_type === "paper" ? "top" : "center"}
            priority
          />
        </div>
      )}
      {article.summary && (
        // Drop cap only on a real paragraph; on "text-classification" it just breaks the word.
        <p
          className={`mt-6 flow-root text-lg leading-relaxed ${
            article.summary.length > 160
              ? "first-letter:float-left first-letter:mt-1 first-letter:mr-3 first-letter:font-display first-letter:text-6xl first-letter:leading-[0.8] first-letter:font-black first-letter:text-tomato"
              : ""
          }`}
        >
          {article.summary}
        </p>
      )}
      <div className="mt-8 flex flex-wrap items-center gap-4">
      <VoteButton kind="article" id={article.id} votes={vote.votes} voted={vote.voted} />
      <a
        href={article.url}
        target="_blank"
        rel="noopener"
        className="kicker inline-block border-2 border-ink bg-tomato px-5 py-3 text-[0.8rem] font-bold text-on-accent shadow-hard transition-[transform,box-shadow] hover:-translate-x-0.5 hover:-translate-y-0.5 hover:shadow-[6px_6px_0_0_var(--shadow-ink)]"
      >
        Read the original on {hostname(article.url)} ↗
      </a>
      </div>

      {article.coverage.length > 0 && (
        <section aria-labelledby="coverage-heading" className="mt-12">
          <SectionHeader number={2} title="Also covered by" id="coverage-heading" />
          {article.coverage.map((other) => (
            <FeedItem key={other.id} article={other} now={now} />
          ))}
        </section>
      )}

      <ChatSection kind="article" id={article.id} title={article.title} number={article.coverage.length > 0 ? 3 : 2} />
    </article>
  );
}
