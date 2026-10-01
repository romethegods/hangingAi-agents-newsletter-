"use client";

import Link from "next/link";
import { useEffect, useRef, useState, useTransition } from "react";

import { shareBattle, voteBattle } from "@/lib/actions";
import type { ArenaModel, Battle } from "@/lib/types";

import { Markdown } from "./Markdown";

type Side = "a" | "b";
type Choice = "a" | "b" | "tie" | "bad";
type SideState = { text: string; done: boolean; error?: string; note?: string };

const SIDE_STYLE: Record<Side, { label: string; bar: string }> = {
  a: { label: "Model A", bar: "bg-tomato text-on-accent" },
  b: { label: "Model B", bar: "bg-cobalt text-on-accent" },
};

/**
 * One Arena battle. Both answers stream in side by side (no names), then the
 * reader votes and the models are revealed with how their ratings moved.
 */
export function BattleView({ initial }: { initial: Battle }) {
  const [battle, setBattle] = useState(initial);
  const [sides, setSides] = useState<Record<Side, SideState>>({
    a: { text: initial.response_a ?? "", done: initial.status !== "pending" },
    b: { text: initial.response_b ?? "", done: initial.status !== "pending" },
  });
  const [phase, setPhase] = useState<Battle["status"]>(initial.status);
  const [error, setError] = useState<string | null>(initial.error);
  const [pending, startTransition] = useTransition();
  const [copied, setCopied] = useState(false);
  const started = useRef(false);

  useEffect(() => {
    if (initial.status !== "pending" || !initial.mine || started.current) return;
    started.current = true;
    const source = new EventSource(`/arena/stream/${initial.id}`);
    source.onmessage = (message) => {
      const event = JSON.parse(message.data) as {
        side?: Side;
        text?: string;
        done?: boolean;
        error?: string;
        note?: string;
        status?: "ready" | "failed";
      };
      if (event.status) {
        setPhase(event.status);
        source.close();
        return;
      }
      const side = event.side;
      if (!side) return;
      setSides((prev) => ({
        ...prev,
        [side]: {
          text: prev[side].text + (event.text ?? ""),
          done: prev[side].done || Boolean(event.done || event.error),
          error: event.error ?? prev[side].error,
          note: event.note ?? prev[side].note,
        },
      }));
    };
    source.onerror = () => {
      source.close();
      setPhase((current) => (current === "pending" || current === "streaming" ? "failed" : current));
      setError((current) => current ?? "the connection dropped before both answers finished");
    };
    return () => source.close();
  }, [initial.id, initial.mine, initial.status]);

  const streaming = phase === "pending" || phase === "streaming";

  function cast(choice: Choice) {
    startTransition(async () => {
      const result = await voteBattle(battle.id, choice);
      if (!result.ok) setError(result.error);
      else {
        setBattle(result.battle);
        setPhase("voted");
      }
    });
  }

  function share() {
    startTransition(async () => {
      const result = await shareBattle(battle.id);
      if (!result.ok) return setError(result.error);
      setBattle(result.battle);
      await navigator.clipboard?.writeText(window.location.href).catch(() => undefined);
      setCopied(true);
    });
  }

  const reveal = phase === "voted" ? { a: battle.model_a, b: battle.model_b } : null;

  return (
    <div className="space-y-8">
      <section className="border-[3px] border-ink bg-paper-raised p-5 shadow-hard">
        <p className="kicker text-tomato">The prompt</p>
        <p className="mt-2 text-lg whitespace-pre-line">{battle.prompt}</p>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        {(["a", "b"] as const).map((side) => (
          <Answer
            key={side}
            side={side}
            state={sides[side]}
            model={reveal?.[side] ?? null}
            change={side === "a" ? battle.rating_change_a : battle.rating_change_b}
            won={phase === "voted" && battle.vote === side}
          />
        ))}
      </div>

      {error && (
        <p role="alert" className="border-2 border-tomato bg-paper-raised p-3 text-sm font-semibold text-tomato">
          {error}.{" "}
          <Link href="/arena" className="underline">
            Start another battle
          </Link>
        </p>
      )}

      {battle.mine && phase === "ready" && (
        <section aria-label="Vote" className="space-y-3 text-center">
          <p className="font-display text-2xl font-black">Which answer is better?</p>
          <p className="text-sm text-muted">The model names are revealed after you vote.</p>
          <div className="flex flex-wrap justify-center gap-3">
            <VoteButton onClick={() => cast("a")} disabled={pending} className="bg-tomato text-on-accent">
              ◀ A is better
            </VoteButton>
            <VoteButton onClick={() => cast("tie")} disabled={pending}>
              It&apos;s a tie
            </VoteButton>
            <VoteButton onClick={() => cast("b")} disabled={pending} className="bg-cobalt text-on-accent">
              B is better ▶
            </VoteButton>
            <VoteButton onClick={() => cast("bad")} disabled={pending}>
              Both are bad
            </VoteButton>
          </div>
        </section>
      )}

      {streaming && (
        <p className="text-center font-mono text-sm text-muted" aria-live="polite">
          Both models are answering…
        </p>
      )}

      {phase === "voted" && (
        <section className="space-y-4 border-t-[3px] border-ink pt-6 text-center">
          <p className="font-display text-2xl font-black">
            {battle.vote === "tie" || battle.vote === "bad"
              ? battle.vote === "tie"
                ? "You called it a tie."
                : "Neither impressed you."
              : `You picked ${(battle.vote === "a" ? battle.model_a : battle.model_b)?.name}.`}
          </p>
          {battle.identity_leak && (
            <p className="text-sm text-muted">
              One answer revealed which model it was, so this vote is saved but doesn&apos;t count toward ratings.
            </p>
          )}
          <div className="flex flex-wrap justify-center gap-3">
            <Link
              href="/arena"
              className="kicker border-2 border-ink bg-tomato px-5 py-3 font-bold text-on-accent shadow-hard-sm hover:opacity-90"
            >
              New battle →
            </Link>
            <Link href="/arena/leaderboard" className="kicker border-2 border-ink px-5 py-3 font-bold hover:bg-mustard">
              Leaderboard
            </Link>
            {battle.mine && (
              <button
                type="button"
                onClick={share}
                disabled={pending}
                className="kicker border-2 border-ink px-5 py-3 font-bold hover:bg-mustard"
              >
                {copied ? "✓ Link copied" : battle.public ? "Copy share link" : "Share this battle"}
              </button>
            )}
          </div>
        </section>
      )}
    </div>
  );
}

function VoteButton({
  children,
  className = "bg-paper-raised",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      className={`kicker border-2 border-ink px-5 py-3 text-[0.8rem] font-bold shadow-hard-sm transition-transform hover:-translate-y-0.5 disabled:opacity-50 ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}

function Answer({
  side,
  state,
  model,
  change,
  won,
}: {
  side: Side;
  state: SideState;
  model: ArenaModel | null;
  change: number | null;
  won: boolean;
}) {
  const style = SIDE_STYLE[side];
  return (
    <article
      aria-label={model ? `${style.label}: ${model.name}` : style.label}
      className={`flex min-h-64 flex-col border-[3px] border-ink bg-paper-raised ${won ? "shadow-[6px_6px_0_0_var(--mustard)]" : "shadow-hard-sm"}`}
    >
      <header className={`flex items-center justify-between gap-3 border-b-[3px] border-ink px-4 py-2 ${style.bar}`}>
        <span className="kicker font-bold">
          {style.label}
          {won && " · 🏆 your pick"}
        </span>
        {model ? (
          <span className="font-mono text-xs font-bold">
            {model.name} · {model.maker}
            {model.open_weights && " · open"}
            {change !== null && ` · ${change >= 0 ? "+" : ""}${change.toFixed(1)}`}
          </span>
        ) : (
          <span className="font-mono text-xs opacity-80">{state.done ? "anonymous" : "typing…"}</span>
        )}
      </header>
      <div className="flex-1 p-4" aria-live="polite" aria-busy={!state.done}>
        {state.text ? <Markdown>{state.text}</Markdown> : !state.error && <p className="font-mono text-sm text-muted">▍</p>}
        {state.error && <p className="mt-3 font-mono text-sm font-semibold text-tomato">✗ {state.error}</p>}
        {state.note && <p className="mt-3 font-mono text-[11px] text-muted">({state.note})</p>}
      </div>
    </article>
  );
}
