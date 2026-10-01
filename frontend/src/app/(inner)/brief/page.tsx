import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { FeedItem } from "@/components/FeedItem";
import { FollowButton } from "@/components/FollowButton";
import { PageHeader } from "@/components/PageHeader";
import { SectionHeader } from "@/components/SectionHeader";
import { FeedSkeleton } from "@/components/Skeleton";
import { DemoReelCard, StarVelocity, ToolName } from "@/components/ToolCard";
import { renameMe, requestSignInLink, saveSettings, signOut } from "@/lib/actions";
import { timeAgo } from "@/lib/format";
import { getBrief, getFollows, getMe } from "@/lib/session";
import { requestNow } from "@/lib/time";
import { param } from "@/lib/url";

export const metadata: Metadata = { title: "Your daily brief", robots: { index: false } };

const POPULAR_TOPICS = ["ai-agents", "llm", "mcp", "rag", "claude-code", "computer-vision"];

export default function BriefPage({ searchParams }: PageProps<"/brief">) {
  return (
    <Suspense fallback={<FeedSkeleton />}>
      <BriefView searchParams={searchParams} />
    </Suspense>
  );
}

/** First visit: nothing exists yet. Following a topic creates the guest identity. */
function StarterView() {
  return (
    <div className="mx-auto max-w-3xl space-y-10">
      <PageHeader kicker="The daily brief" title="Your AI morning brief">
        Follow tools and topics and this page shows what shipped in your stack, what&apos;s rising
        and the must-reads. No sign-up: just pick a few.
      </PageHeader>
      <section className="border-[3px] border-ink bg-paper-raised p-6 shadow-hard">
        <p className="kicker text-tomato">Start here</p>
        <p className="mt-2 font-display text-xl font-semibold">Follow a topic or two</p>
        <div className="mt-4 flex flex-wrap gap-2">
          {POPULAR_TOPICS.map((topic) => (
            <FollowButton key={topic} kind="topic" target={topic} following={false} back="/brief" label={`#${topic}`} />
          ))}
        </div>
        <p className="mt-4 text-sm text-muted">
          You&apos;ll get a name like hanging-1234 (change it anytime). Want it by email, or already
          use HangingAi on another device?{" "}
          <Link href="/signin" className="font-semibold underline">
            Add your email
          </Link>
          .
        </p>
      </section>
    </div>
  );
}

function hourLabel(hour: number): string {
  return `${hour % 12 || 12}:00 ${hour < 12 ? "am" : "pm"}`;
}

async function BriefView({ searchParams }: Pick<PageProps<"/brief">, "searchParams">) {
  const [me, brief, follows, query] = await Promise.all([getMe(), getBrief(), getFollows(), searchParams]);
  if (!me || !brief || !follows) return <StarterView />;
  const now = await requestNow();
  const followedTopics = new Set(follows.topics);
  let n = 0;

  return (
    <div className="grid gap-14 lg:grid-cols-[minmax(0,1fr)_300px]">
      <div className="space-y-12">
        <PageHeader kicker={`Your brief · ${new Date(now).toDateString()}`} title="Good morning">
          {brief.personalized
            ? me.is_guest
              ? "What moved in the tools and topics you follow. Add an email to get it each morning."
              : "What moved in the tools and topics you follow. The same brief lands in your inbox each morning."
            : "Follow a few tools or topics and this page (and your morning email) becomes yours."}
        </PageHeader>

        {!brief.personalized && (
          <section className="border-[3px] border-ink bg-paper-raised p-6 shadow-hard">
            <p className="kicker text-tomato">Start here</p>
            <p className="mt-2 font-display text-xl font-semibold">Follow a topic or two</p>
            <div className="mt-4 flex flex-wrap gap-2">
              {POPULAR_TOPICS.map((topic) => (
                <FollowButton
                  key={topic}
                  kind="topic"
                  target={topic}
                  following={followedTopics.has(topic)}
                  back="/brief"
                  label={`#${topic}`}
                />
              ))}
            </div>
            <p className="mt-4 text-sm text-muted">
              Or open any tool and press <strong>+ Follow</strong> to get its releases.{" "}
              <Link href="/tools" className="font-semibold underline">
                Browse tools →
              </Link>
            </p>
          </section>
        )}

        {brief.releases.length > 0 && (
          <section>
            <SectionHeader number={++n} title="Your stack shipped" />
            <ul className="divide-y divide-hairline">
              {brief.releases.map((r) => (
                <li key={r.id} className="py-4">
                  <a href={r.url} target="_blank" rel="noopener" className="font-display text-lg font-semibold hover:text-tomato">
                    {r.tool.full_name} <span className="font-mono text-base">{r.tag}</span>
                  </a>
                  <p className="font-mono text-[11px] text-muted">
                    Release{r.published_at ? ` · ${timeAgo(r.published_at, now)}` : ""}
                  </p>
                  {r.notes && <p className="mt-1 line-clamp-2 text-sm text-muted">{r.notes}</p>}
                </li>
              ))}
            </ul>
          </section>
        )}

        {brief.rising.length > 0 && (
          <section>
            <SectionHeader
              number={++n}
              title={brief.followed_topics.length ? `Rising in ${brief.followed_topics.map((t) => `#${t}`).join(", ")}` : "Rising tools"}
            />
            <ul className="divide-y divide-hairline">
              {brief.rising.map((tool) => (
                <li key={tool.id} className="flex items-start justify-between gap-4 py-4">
                  <div className="min-w-0">
                    <Link href={`/tools/${tool.id}`} className="font-semibold hover:text-tomato">
                      <ToolName fullName={tool.full_name} />
                    </Link>
                    {tool.description && <p className="line-clamp-2 text-sm text-muted">{tool.description}</p>}
                  </div>
                  <StarVelocity perDay={tool.star_velocity} />
                </li>
              ))}
            </ul>
          </section>
        )}

        {brief.reads.length > 0 && (
          <section>
            <SectionHeader number={++n} title="Must-reads" />
            {brief.reads.map((article) => (
              <div key={article.id}>
                {article.matched && <p className="kicker -mb-4 pt-4 font-bold text-tomato">For you</p>}
                <FeedItem article={article} now={now} />
              </div>
            ))}
          </section>
        )}

        {brief.demo && (
          <section>
            <SectionHeader number={++n} title="Demo to try" />
            <div className="max-w-md">
              <DemoReelCard tool={brief.demo} />
            </div>
          </section>
        )}
      </div>

      <aside className="space-y-10">
        <section id="name" className="scroll-mt-20">
          <SectionHeader number={++n} title="Your name" />
          <form action={renameMe} className="flex gap-2">
            <input type="hidden" name="back" value="/brief#name" />
            <label htmlFor="handle" className="sr-only">
              Your public name
            </label>
            <input
              id="handle"
              name="handle"
              defaultValue={me.handle}
              required
              minLength={3}
              maxLength={24}
              className="w-full min-w-0 border-2 border-ink bg-paper-raised px-2 py-1.5 font-mono text-sm"
            />
            <button type="submit" className="kicker border-2 border-ink bg-ink px-3 font-bold text-paper hover:bg-tomato">
              Save
            </button>
          </form>
          {param(query, "renamed") && <p className="mt-2 text-sm font-semibold text-teal">Name saved.</p>}
          {param(query, "name_error") && (
            <p role="alert" className="mt-2 text-sm font-semibold text-tomato">
              {param(query, "name_error")}
            </p>
          )}
          <p className="mt-2 font-mono text-[11px] text-muted">Shown on your comments. Letters, digits, - and _.</p>
        </section>

        {me.is_guest ? (
          <section id="email" className="scroll-mt-20">
            <SectionHeader number={++n} title="Get it by email" />
            <p className="mb-3 text-sm text-muted">
              Optional. Add an email to get this brief each morning and to use your name, follows and
              comments on another device.
            </p>
            <form action={requestSignInLink} className="space-y-2">
              <input type="hidden" name="next" value="/brief" />
              <label htmlFor="brief-email" className="sr-only">
                Email address
              </label>
              <input
                id="brief-email"
                name="email"
                type="email"
                required
                autoComplete="email"
                placeholder="you@example.com"
                className="w-full border-2 border-ink bg-paper-raised px-2 py-1.5 text-sm"
              />
              <button type="submit" className="kicker border-2 border-ink bg-tomato px-3 py-2 font-bold text-on-accent">
                Email me a link
              </button>
            </form>
          </section>
        ) : (
        <section id="settings" className="scroll-mt-20">
          <SectionHeader number={++n} title="Delivery" />
          {param(query, "saved") && <p className="mb-3 text-sm font-semibold text-teal">Saved.</p>}
          <form action={saveSettings} className="space-y-4 text-sm">
            <label className="flex items-center gap-2 font-semibold">
              <input type="checkbox" name="brief_enabled" defaultChecked={me.brief_enabled} className="h-4 w-4 accent-[var(--tomato)]" />
              Email me the brief each morning
            </label>
            <label className="block">
              <span className="kicker mb-1 block">Arrives at</span>
              <select name="brief_hour" defaultValue={me.brief_hour} className="w-full border-2 border-ink bg-paper-raised px-2 py-1.5">
                {Array.from({ length: 24 }, (_, h) => (
                  <option key={h} value={h}>
                    {hourLabel(h)}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="kicker mb-1 block">Time zone</span>
              <select name="timezone" defaultValue={me.timezone} className="w-full border-2 border-ink bg-paper-raised px-2 py-1.5">
                {Intl.supportedValuesOf("timeZone").map((tz) => (
                  <option key={tz} value={tz}>
                    {tz.replaceAll("_", " ")}
                  </option>
                ))}
              </select>
            </label>
            <button type="submit" className="kicker border-2 border-ink bg-ink px-4 py-2 font-bold text-paper hover:bg-tomato">
              Save
            </button>
          </form>
          <p className="mt-3 font-mono text-[11px] text-muted">Emailed to {me.email}</p>
        </section>
        )}

        <section>
          <SectionHeader number={++n} title="Following" />
          {follows.tools.length === 0 && follows.topics.length === 0 ? (
            <p className="text-sm text-muted">Nothing yet.</p>
          ) : (
            <ul className="space-y-2">
              {follows.topics.map((topic) => (
                <li key={topic} className="flex items-center justify-between gap-2">
                  <Link href={`/tools?topic=${topic}`} className="font-mono text-sm hover:text-tomato">
                    #{topic}
                  </Link>
                  <FollowButton kind="topic" target={topic} following back="/brief" />
                </li>
              ))}
              {follows.tools.map((tool) => (
                <li key={tool.id} className="flex items-center justify-between gap-2">
                  <Link href={`/tools/${tool.id}`} className="truncate text-sm font-semibold hover:text-tomato">
                    {tool.full_name}
                  </Link>
                  <FollowButton kind="tool" target={String(tool.id)} following back="/brief" />
                </li>
              ))}
            </ul>
          )}
        </section>

        <form action={signOut}>
          <button type="submit" className="kicker font-semibold text-muted underline hover:text-ink">
            {me.is_guest ? "Forget me on this device" : "Sign out"}
          </button>
        </form>
      </aside>
    </div>
  );
}
