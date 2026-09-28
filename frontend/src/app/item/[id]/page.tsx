import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { ArticleMeta, FeedItem } from "@/components/FeedItem";
import { FeedSkeleton } from "@/components/Skeleton";
import { getArticle } from "@/lib/api";
import { hostname } from "@/lib/format";
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
  const now = await requestNow();
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": article.content_type === "paper" ? "ScholarlyArticle" : "NewsArticle",
    headline: article.title,
    datePublished: article.published_at,
    url: article.url,
    ...(article.author && { author: { "@type": "Person", name: article.author } }),
  };

  return (
    <article className="mx-auto max-w-3xl space-y-6">
      <script
        type="application/ld+json"
        // JSON.stringify output with "<" escaped cannot break out of the script tag.
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd).replace(/</g, "\\u003c") }}
      />
      <Link href="/" className="text-sm text-muted hover:text-foreground">
        ← Back to feed
      </Link>
      <header className="space-y-3">
        <h1 className="text-3xl leading-tight font-bold tracking-tight">{article.title}</h1>
        <ArticleMeta article={article} now={now} />
      </header>
      {article.summary && <p className="text-lg leading-relaxed">{article.summary}</p>}
      <a
        href={article.url}
        target="_blank"
        rel="noopener"
        className="inline-block rounded-md bg-accent px-4 py-2 font-medium text-white hover:opacity-90"
      >
        Read on {hostname(article.url)} ↗
      </a>

      {article.coverage.length > 0 && (
        <section aria-labelledby="coverage-heading" className="border-t border-border pt-6">
          <h2 id="coverage-heading" className="text-sm font-semibold tracking-wide text-muted uppercase">
            Also covered by
          </h2>
          {article.coverage.map((other) => (
            <FeedItem key={other.id} article={other} now={now} />
          ))}
        </section>
      )}
    </article>
  );
}
