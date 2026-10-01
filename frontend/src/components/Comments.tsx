import { deleteComment, postComment, reportComment } from "@/lib/actions";
import { timeAgo } from "@/lib/format";
import { getComments, getMe } from "@/lib/session";
import type { Comment } from "@/lib/types";

import { SectionHeader } from "./SectionHeader";
import { VoteButton } from "./VoteButton";

const FIELD = "w-full border-2 border-ink bg-paper-raised px-3 py-2 text-sm";
const SMALL_BUTTON = "kicker font-semibold text-muted hover:text-ink";

/**
 * Comments under a story or tool. Anyone can read; anyone can post (no sign-up: the
 * first comment creates a hanging-1234 guest name, renameable on /brief).
 * Uncached on purpose: it's live discussion and shows the reader's own votes.
 */
export async function Comments({
  kind,
  id,
  back,
  now,
  error,
  reported,
  number = 3,
}: {
  number?: number;
  kind: "article" | "tool";
  id: number;
  back: string;
  now: number;
  error?: string;
  reported?: boolean;
}) {
  const [thread, me] = await Promise.all([getComments(kind, id), getMe()]);

  return (
    <section id="comments" aria-labelledby="comments-heading" className="mt-14 scroll-mt-20">
      <SectionHeader number={number} title={`Discussion (${thread.count})`} id="comments-heading" />

      <form action={postComment} className="space-y-2">
        <input type="hidden" name="target_kind" value={kind} />
        <input type="hidden" name="target_id" value={id} />
        <input type="hidden" name="back" value={back} />
        <label htmlFor="new-comment" className="sr-only">
          Add a comment
        </label>
        <textarea id="new-comment" name="body" required maxLength={2000} rows={3} placeholder="Share what you think, or how it worked for you…" className={FIELD} />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="font-mono text-[11px] text-muted">
            {me ? (
              <>
                Posting as <strong className="text-ink">{me.handle}</strong> ·{" "}
                <a href="/brief#name" className="underline hover:text-ink">change name</a>
              </>
            ) : (
              <>No sign-up. You&apos;ll get a name like hanging-1234; change it anytime.</>
            )}
          </p>
          <button type="submit" className="kicker border-2 border-ink bg-tomato px-4 py-2 font-bold text-on-accent shadow-hard-sm hover:opacity-90">
            Post comment
          </button>
        </div>
        {error && (
          <p role="alert" className="text-sm font-semibold text-tomato">
            {error}
          </p>
        )}
        {reported && <p className="text-sm font-semibold text-teal">Thanks, we&apos;ll take a look.</p>}
      </form>

      {thread.comments.length === 0 ? (
        <p className="mt-8 text-sm text-muted">No comments yet. Start the conversation.</p>
      ) : (
        <ol className="mt-8 space-y-6">
          {thread.comments.map((comment) => (
            <li key={comment.id}>
              <CommentView comment={comment} kind={kind} targetId={id} back={back} now={now} />
              {comment.replies.length > 0 && (
                <ol className="mt-4 ml-5 space-y-4 border-l-2 border-hairline pl-5">
                  {comment.replies.map((reply) => (
                    <li key={reply.id}>
                      <CommentView comment={reply} kind={kind} targetId={id} back={back} now={now} reply />
                    </li>
                  ))}
                </ol>
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function CommentView({
  comment,
  kind,
  targetId,
  back,
  now,
  reply = false,
}: {
  comment: Comment;
  kind: "article" | "tool";
  targetId: number;
  back: string;
  now: number;
  reply?: boolean;
}) {
  if (comment.status !== "visible" && comment.body === null) {
    return (
      <p id={`comment-${comment.id}`} className="font-mono text-xs text-muted italic">
        {comment.status === "hidden" ? "Hidden while a moderator reviews it." : "Comment removed."}
      </p>
    );
  }
  return (
    <article id={`comment-${comment.id}`} className="scroll-mt-24 space-y-2">
      <p className="flex flex-wrap items-center gap-x-2 font-mono text-[11px] text-muted">
        <strong className={comment.mine ? "text-tomato" : "text-ink"}>{comment.author}</strong>
        {comment.mine && <span>(you)</span>}
        <span>· {timeAgo(comment.created_at, now)}</span>
      </p>
      <p className="text-[15px] leading-relaxed whitespace-pre-line break-words">{comment.body}</p>
      <div className="flex flex-wrap items-center gap-4">
        <VoteButton kind="comment" id={comment.id} votes={comment.votes} voted={comment.voted} size="sm" />
        {!reply && (
          <details className="group">
            <summary className={`${SMALL_BUTTON} cursor-pointer list-none`}>Reply</summary>
            <form action={postComment} className="mt-2 w-full max-w-xl space-y-2">
              <input type="hidden" name="target_kind" value={kind} />
              <input type="hidden" name="target_id" value={targetId} />
              <input type="hidden" name="parent_id" value={comment.id} />
              <input type="hidden" name="back" value={back} />
              <textarea name="body" required maxLength={2000} rows={2} aria-label={`Reply to ${comment.author}`} className={FIELD} />
              <button type="submit" className="kicker border-2 border-ink px-3 py-1.5 font-bold hover:bg-mustard">
                Post reply
              </button>
            </form>
          </details>
        )}
        {comment.mine ? (
          <form action={deleteComment}>
            <input type="hidden" name="id" value={comment.id} />
            <button type="submit" className={SMALL_BUTTON}>
              Delete
            </button>
          </form>
        ) : (
          <form action={reportComment}>
            <input type="hidden" name="id" value={comment.id} />
            <input type="hidden" name="back" value={back} />
            <button type="submit" className={SMALL_BUTTON}>
              Report
            </button>
          </form>
        )}
      </div>
    </article>
  );
}
