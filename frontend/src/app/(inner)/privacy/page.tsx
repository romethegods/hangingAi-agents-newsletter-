import type { Metadata } from "next";

import { PageHeader } from "@/components/PageHeader";
import { SectionHeader } from "@/components/SectionHeader";
import { CONTACT_EMAIL, POLICY_UPDATED } from "@/lib/site";

export const metadata: Metadata = { title: "Privacy policy", description: "What HangingAi collects, why, and your choices." };

export default function PrivacyPage() {
  return (
    <article className="mx-auto max-w-3xl space-y-8 leading-relaxed">
      <PageHeader kicker={`Last updated ${POLICY_UPDATED}`} title="Privacy policy">
        Short version: we collect as little as we can, we never sell data, and there are no ads or
        third-party trackers.
      </PageHeader>

      <section className="space-y-3">
        <SectionHeader number={1} title="What we collect" />
        <ul className="list-[square] space-y-2 pl-5 marker:text-tomato">
          <li>
            <strong>Reading needs nothing.</strong> Browsing HangingAi doesn&apos;t create an account
            or set a tracking cookie.
          </li>
          <li>
            <strong>When you follow, vote, comment or use the Arena</strong>, we create a guest
            account with a random name (like hanging-1234) and store a session cookie so we recognize
            you. The cookie is httpOnly and is used only for HangingAi.
          </li>
          <li>
            <strong>What you post:</strong> comments, votes, follows, your chosen name and Arena
            prompts and votes. Comments and your name are public.
          </li>
          <li>
            <strong>Your email, only if you add one</strong>, to send the daily brief and sign-in
            links. We store only a fingerprint (hash) of sign-in links, never the links themselves.
          </li>
          <li>
            <strong>IP addresses</strong> are used briefly, in memory, to rate-limit abuse, and appear
            in server logs that rotate after a few days.
          </li>
        </ul>
      </section>

      <section className="space-y-3">
        <SectionHeader number={2} title="Who else sees data" />
        <ul className="list-[square] space-y-2 pl-5 marker:text-tomato">
          <li>
            <strong>Arena prompts are sent to AI model providers</strong> to generate the answers
            (Anthropic for Claude; open models through Hugging Face and its inference partners). Don&apos;t
            put personal or confidential information in Arena prompts. A battle is private unless you
            press Share.
          </li>
          <li>
            <strong>Email delivery</strong> goes through our email provider (Resend), which receives
            your address and the message.
          </li>
          <li>
            <strong>Embedded media:</strong> thumbnails and demos load from the sites that publish
            them (GitHub, Hugging Face, YouTube via its privacy-enhanced youtube-nocookie.com player,
            news sites). Video players and live demo apps load only when you press play.
          </li>
          <li>We don&apos;t sell or rent personal data, and we don&apos;t use advertising or analytics trackers.</li>
        </ul>
      </section>

      <section className="space-y-3">
        <SectionHeader number={3} title="Your choices" />
        <ul className="list-[square] space-y-2 pl-5 marker:text-tomato">
          <li>Turn the email brief off from your brief page, or with the one-click unsubscribe link in any email.</li>
          <li>Delete any of your comments yourself, and change your name anytime.</li>
          <li>&ldquo;Forget me on this device&rdquo; on your brief page removes the guest cookie.</li>
          <li>
            To get a copy of your data or have your account and its content deleted, email{" "}
            <a className="font-semibold underline" href={`mailto:${CONTACT_EMAIL}`}>
              {CONTACT_EMAIL}
            </a>
            . We respond within 30 days.
          </li>
        </ul>
      </section>

      <section className="space-y-3">
        <SectionHeader number={4} title="Security, retention, children" />
        <p>
          Data is stored on our own server and database in Google Cloud, which encrypts its disks
          and storage at rest. Nightly backups are kept for 14 days. Arena battles and comments are kept until you delete them or ask us to. HangingAi isn&apos;t
          directed at children under 13, and we don&apos;t knowingly collect their data.
        </p>
        <p className="text-sm text-muted">
          We&apos;ll post changes here and update the date above. Questions:{" "}
          <a className="underline" href={`mailto:${CONTACT_EMAIL}`}>
            {CONTACT_EMAIL}
          </a>
          .
        </p>
      </section>
    </article>
  );
}
