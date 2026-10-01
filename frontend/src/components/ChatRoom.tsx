"use client";

import { useCallback, useEffect, useMemo, useRef, useState, useTransition } from "react";

import { chatDelete, chatNick, chatReport, chatVote, sendChatMessage } from "@/lib/actions";
import type { Comment, CommentThread } from "@/lib/types";

/**
 * Each post's chat room, styled like a 90s IRC client. Collapsed until opened;
 * while open it polls every few seconds (paused in background tabs), so new
 * messages and "N here now" show up on their own. Messages are comments: the
 * same filters, votes, reports and moderation apply.
 */

const POLL_MS = 5000;
const NICK_COLORS = ["#ff8a65", "#8fa6ff", "#f2c14e", "#5ccfb9", "#c9a7ff"];
const SYSTEM = "#8fd18f";
const ERROR = "#ff7b6b";
const HELP = [
  "/nick <name>  change your name (3-24 letters, digits, - and _)",
  "/top · /new   sort by votes or by time",
  "/help         show this",
];

type Line = { kind: "system" | "error"; text: string; at: number };
type Message = Comment & { replyTo?: string };
type TimelineEntry =
  | { type: "message"; message: Message; at: number }
  | { type: "line"; line: Line; at: number };

function nickColor(handle: string): string {
  let hash = 0;
  for (const c of handle) hash = (hash * 31 + c.charCodeAt(0)) >>> 0;
  return NICK_COLORS[hash % NICK_COLORS.length];
}

function clock(iso: string): string {
  const date = new Date(iso);
  const today = new Date().toDateString() === date.toDateString();
  return today
    ? date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false })
    : date.toLocaleDateString([], { month: "short", day: "numeric" });
}

/** IRC is flat: replies become their own lines, tagged with who they answer. */
function flatten(thread: Comment[]): Message[] {
  const out: Message[] = [];
  for (const top of thread) {
    out.push(top);
    for (const reply of top.replies) out.push({ ...reply, replyTo: top.author });
  }
  return out;
}

function viewerId(): string {
  const key = "hai-viewer";
  let id = sessionStorage.getItem(key);
  if (!id) {
    id = `tab-${crypto.randomUUID().replaceAll("-", "").slice(0, 20)}`;
    sessionStorage.setItem(key, id);
  }
  return id;
}

export function ChatRoom({
  kind,
  id,
  room,
  initial,
  me,
}: {
  kind: "article" | "tool";
  id: number;
  room: string;
  initial: CommentThread;
  me: string | null;
}) {
  const [open, setOpen] = useState(false);
  const [thread, setThread] = useState(initial);
  const [handle, setHandle] = useState(me);
  const [sort, setSort] = useState<"new" | "top">("new");
  const [draft, setDraft] = useState("");
  const [replyTo, setReplyTo] = useState<Message | null>(null);
  const [lines, setLines] = useState<Line[]>([]);
  const [pending, startTransition] = useTransition();
  const logRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const say = useCallback((kind: Line["kind"], text: string) => {
    setLines((prev) => [...prev.slice(-20), { kind, text, at: Date.now() }]);
  }, []);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch(`/chat/${kind}/${id}`, { headers: { "x-viewer-id": viewerId() }, cache: "no-store" });
      if (res.ok) setThread((await res.json()) as CommentThread);
    } catch {
      // offline for a moment; the next poll catches up
    }
  }, [kind, id]);

  // Open straight into the room when arriving from a "💬 14" link.
  useEffect(() => {
    if (!/^#comment(s|-\d+)$/.test(window.location.hash)) return;
    const frame = window.requestAnimationFrame(() => setOpen(true));
    return () => window.cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    if (!open) return;
    const first = window.setTimeout(refresh, 0);
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") refresh();
    }, POLL_MS);
    return () => {
      window.clearTimeout(first);
      window.clearInterval(timer);
    };
  }, [open, refresh]);

  const messages = useMemo(() => {
    const flat = flatten(thread.comments);
    return sort === "top" ? [...flat].sort((a, b) => b.votes - a.votes) : flat.sort((a, b) => a.created_at.localeCompare(b.created_at));
  }, [thread, sort]);

  // System lines ("you are now known as…") sit where they happened, like IRC. When
  // sorted by votes they collect at the end instead.
  const timeline = useMemo(() => {
    const entries: TimelineEntry[] = [
      ...messages.map((message) => ({ type: "message" as const, message, at: Date.parse(message.created_at) })),
      ...lines.map((line) => ({ type: "line" as const, line, at: line.at })),
    ];
    if (sort === "top") return entries.sort((a, b) => Number(a.type === "line") - Number(b.type === "line"));
    return entries.sort((a, b) => a.at - b.at);
  }, [messages, lines, sort]);

  // Keep the newest line in view, unless the reader scrolled up to read history.
  useEffect(() => {
    const log = logRef.current;
    if (!log || sort === "top") return;
    if (log.scrollHeight - log.scrollTop - log.clientHeight < 120) log.scrollTop = log.scrollHeight;
  }, [timeline, sort, open]);

  function run(action: () => Promise<{ ok: boolean; error?: string }>, after?: () => void) {
    startTransition(async () => {
      const result = await action();
      if (!result.ok) say("error", result.error ?? "something went wrong");
      else after?.();
      await refresh();
    });
  }

  function submit() {
    const text = draft.trim();
    if (!text || pending) return;
    if (text.startsWith("/")) {
      const [command, ...rest] = text.split(/\s+/);
      setDraft("");
      if (command === "/help") HELP.forEach((h) => say("system", h));
      else if (command === "/top" || command === "/new") setSort(command === "/top" ? "top" : "new");
      else if (command === "/nick" && rest[0])
        startTransition(async () => {
          const result = await chatNick(rest.join("-"));
          if (result.ok) {
            say("system", `you are now known as ${result.handle}`);
            setHandle(result.handle ?? null);
          } else say("error", result.error);
          await refresh();
        });
      else say("error", `unknown command ${command} (try /help)`);
      return;
    }
    const parent = replyTo ? (replyTo.parent_id ?? replyTo.id) : null;
    run(
      () => sendChatMessage(kind, id, text, parent),
      () => {
        setDraft("");
        setReplyTo(null);
        if (!handle) say("system", "you joined as a guest. /nick <name> to pick a name");
      },
    );
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="group flex w-full items-center gap-3 border-2 border-ink bg-[#141311] px-4 py-3 text-left font-mono text-sm text-[#e9e3d6] shadow-hard-sm hover:shadow-hard"
      >
        <span className="text-[#8fd18f]">▶</span>
        <span className="font-bold">#{room}</span>
        <span className="text-[#9a9386]">
          · {thread.count} message{thread.count === 1 ? "" : "s"}
          {thread.here > 0 ? ` · ${thread.here} here now` : ""}
        </span>
        <span className="ml-auto border border-[#e9e3d6] px-2 py-0.5 text-xs font-bold group-hover:bg-[#e9e3d6] group-hover:text-[#141311]">
          JOIN
        </span>
      </button>
    );
  }

  return (
    <section aria-label={`Chat room #${room}`} className="border-2 border-ink bg-[#141311] font-mono text-[13px] text-[#e9e3d6] shadow-hard">
      <header className="flex items-center gap-3 border-b border-[#3a362f] px-3 py-2">
        <span className="font-bold">#{room}</span>
        <span className="text-[#9a9386]">
          {thread.count} msgs · <span className="text-[#8fd18f]">●</span> {Math.max(thread.here, 1)} here now
        </span>
        <span className="ml-auto flex items-center gap-2">
          {(["new", "top"] as const).map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setSort(s)}
              aria-pressed={sort === s}
              className={sort === s ? "text-[#f2c14e] underline" : "text-[#9a9386] hover:text-[#e9e3d6]"}
            >
              [{s}]
            </button>
          ))}
          <button type="button" onClick={() => setOpen(false)} aria-label="Close chat" className="text-[#9a9386] hover:text-[#e9e3d6]">
            [x]
          </button>
        </span>
      </header>

      <div ref={logRef} role="log" aria-live="polite" className="max-h-[26rem] min-h-48 overflow-y-auto px-3 py-2 leading-relaxed">
        <p style={{ color: SYSTEM }}>
          * welcome to #{room}. you are {handle ?? "a guest (you get a name on your first message)"}. /help for commands
        </p>
        {messages.length === 0 && <p style={{ color: SYSTEM }}>* it&apos;s quiet in here. say hi?</p>}
        {timeline.map((entry) =>
          entry.type === "line" ? (
            <p key={`line-${entry.line.at}-${entry.line.text}`} style={{ color: entry.line.kind === "error" ? ERROR : SYSTEM }}>
              * {entry.line.kind === "error" ? `error: ${entry.line.text}` : entry.line.text}
            </p>
          ) : (
            <ChatLine
              key={entry.message.id}
              message={entry.message}
              busy={pending}
              onReply={() => {
                setReplyTo(entry.message);
                inputRef.current?.focus();
              }}
              onVote={() => run(() => chatVote(entry.message.id))}
              onDelete={() => run(() => chatDelete(entry.message.id))}
              onReport={() =>
                run(() => chatReport(entry.message.id), () => say("system", "reported. thanks, a moderator will look"))
              }
            />
          ),
        )}
      </div>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
        className="border-t border-[#3a362f] px-3 py-2"
      >
        {replyTo && (
          <p className="mb-1 text-[#9a9386]">
            ↳ replying to <span style={{ color: nickColor(replyTo.author) }}>{replyTo.author}</span>{" "}
            <button type="button" onClick={() => setReplyTo(null)} className="hover:text-[#e9e3d6]" aria-label="Cancel reply">
              [×]
            </button>
          </p>
        )}
        <div className="flex items-start gap-2">
          <span className="pt-0.5 text-[#8fd18f]" aria-hidden="true">
            &gt;
          </span>
          <label htmlFor={`chat-${kind}-${id}`} className="sr-only">
            Message #{room}
          </label>
          <textarea
            id={`chat-${kind}-${id}`}
            ref={inputRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            rows={1}
            maxLength={2000}
            placeholder="type a message_   (Enter to send, Shift+Enter for a new line)"
            className="min-h-6 flex-1 resize-none bg-transparent text-[#e9e3d6] caret-[#8fd18f] outline-none placeholder:text-[#6b665c] focus-visible:outline-none"
          />
          <button
            type="submit"
            disabled={pending || !draft.trim()}
            className="border border-[#e9e3d6] px-2 py-0.5 text-xs font-bold hover:bg-[#e9e3d6] hover:text-[#141311] disabled:opacity-40"
          >
            {pending ? "…" : "SEND"}
          </button>
        </div>
      </form>
    </section>
  );
}

function ChatLine({
  message: m,
  busy,
  onReply,
  onVote,
  onDelete,
  onReport,
}: {
  message: Message;
  busy: boolean;
  onReply: () => void;
  onVote: () => void;
  onDelete: () => void;
  onReport: () => void;
}) {
  const stamp = <span className="text-[#6b665c]">[{clock(m.created_at)}]</span>;
  if (m.body === null) {
    return (
      <p id={`comment-${m.id}`} className="text-[#6b665c] italic">
        {stamp} * {m.status === "hidden" ? "message hidden while a moderator reviews it" : "message removed"}
      </p>
    );
  }
  const action = "text-[#9a9386] hover:text-[#e9e3d6] disabled:opacity-40";
  return (
    <div id={`comment-${m.id}`} className="group -mx-1 scroll-mt-24 rounded-sm px-1 hover:bg-[#1f1d19]">
      <p className="break-words whitespace-pre-line">
        {stamp} <span style={{ color: nickColor(m.author) }}>&lt;{m.author}&gt;</span>
        {m.mine && <span className="text-[#6b665c]"> (you)</span>}{" "}
        {m.replyTo && <span className="text-[#9a9386]">↳ {m.replyTo}: </span>}
        {m.body}
      </p>
      <p className="flex gap-3 pl-[4.5rem] text-[11px] opacity-0 group-focus-within:opacity-100 group-hover:opacity-100 [@media(hover:none)]:opacity-100">
        <button type="button" onClick={onVote} disabled={busy} className={m.voted ? "text-[#5ccfb9]" : action} aria-pressed={m.voted}>
          ▲{m.votes}
        </button>
        <button type="button" onClick={onReply} className={action}>
          reply
        </button>
        {m.mine ? (
          <button type="button" onClick={onDelete} disabled={busy} className={action}>
            delete
          </button>
        ) : (
          <button type="button" onClick={onReport} disabled={busy} className={action}>
            report
          </button>
        )}
      </p>
    </div>
  );
}
