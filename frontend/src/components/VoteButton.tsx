import { toggleVote } from "@/lib/actions";

/** Upvote toggle. The first vote quietly creates the reader's guest identity. */
export function VoteButton({
  kind,
  id,
  votes,
  voted,
  size = "md",
}: {
  kind: "article" | "tool" | "comment";
  id: number;
  votes: number;
  voted: boolean;
  size?: "sm" | "md";
}) {
  return (
    <form action={toggleVote}>
      <input type="hidden" name="kind" value={kind} />
      <input type="hidden" name="id" value={id} />
      <button
        type="submit"
        aria-pressed={voted}
        aria-label={voted ? `Remove upvote (${votes})` : `Upvote (${votes})`}
        className={`inline-flex items-center gap-1.5 border-2 border-ink font-mono font-bold transition-colors ${
          size === "sm" ? "px-1.5 py-0.5 text-[11px]" : "px-3 py-2 text-sm"
        } ${voted ? "bg-teal text-on-accent" : "bg-paper-raised hover:bg-mustard hover:text-[#171614]"}`}
      >
        ▲ {votes}
      </button>
    </form>
  );
}
