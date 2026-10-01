import { toggleFollow } from "@/lib/actions";

/**
 * Works without JavaScript: a plain form posting to a server action. Signed-out
 * readers are sent to sign in and brought back here afterwards.
 */
export function FollowButton({
  kind,
  target,
  following,
  back,
  label,
}: {
  kind: "tool" | "topic";
  target: string;
  following: boolean;
  back: string;
  label?: string;
}) {
  return (
    <form action={toggleFollow}>
      <input type="hidden" name="kind" value={kind} />
      <input type="hidden" name="target" value={target} />
      <input type="hidden" name="following" value={following ? "1" : "0"} />
      <input type="hidden" name="back" value={back} />
      <button
        type="submit"
        aria-pressed={following}
        className={`kicker border-2 border-ink px-3 py-2 font-bold whitespace-nowrap transition-colors ${
          following ? "bg-ink text-paper hover:bg-tomato hover:text-on-accent" : "bg-paper-raised hover:bg-mustard hover:text-[#171614]"
        }`}
      >
        {following ? "✓ Following" : `+ Follow${label ? ` ${label}` : ""}`}
      </button>
    </form>
  );
}
