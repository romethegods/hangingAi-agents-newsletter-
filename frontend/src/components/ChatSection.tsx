import { getComments, getMe } from "@/lib/session";

import { ChatRoom } from "./ChatRoom";
import { SectionHeader } from "./SectionHeader";

/** "#browser-use", "#new-mcp-server-spec": an IRC-style channel name for a post. */
export function roomName(title: string): string {
  const slug = title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .split("-")
    .filter(Boolean)
    .slice(0, 4)
    .join("-");
  return (slug || "chat").slice(0, 28);
}

/** Every post gets its own room: rendered on the server with the current messages,
 *  then the client window takes over live updates once someone opens it. */
export async function ChatSection({
  kind,
  id,
  title,
  number,
}: {
  kind: "article" | "tool";
  id: number;
  title: string;
  number: number;
}) {
  const [thread, me] = await Promise.all([getComments(kind, id), getMe()]);
  return (
    <section id="comments" aria-labelledby="chat-heading" className="mt-14 scroll-mt-20">
      <SectionHeader number={number} title="Chat room" id="chat-heading" />
      <ChatRoom kind={kind} id={id} room={roomName(title)} initial={thread} me={me?.handle ?? null} />
      <p className="mt-2 font-mono text-[11px] text-muted">
        No sign-up: your first message gives you a name like hanging-1234. Be kind, stay on topic,
        max two links. <a href="/about#community" className="underline hover:text-ink">Rules</a>
      </p>
    </section>
  );
}
