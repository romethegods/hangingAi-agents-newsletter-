"use server";

import { cookies } from "next/headers";
import { refresh } from "next/cache";
import { redirect } from "next/navigation";

import { SESSION_COOKIE, apiFetch, sessionToken } from "./session";
import type { Battle } from "./types";
import { withQuery } from "./url";

/** Same-site relative paths only, so ?back= / ?next= can't send readers off-site. */
function safePath(value: FormDataEntryValue | null, fallback = "/brief"): string {
  const path = typeof value === "string" ? value : "";
  return path.startsWith("/") && !path.startsWith("//") && !path.includes("\\") ? path : fallback;
}

async function setSession(token: string, expiresAt: string): Promise<void> {
  (await cookies()).set(SESSION_COOKIE, token, {
    httpOnly: true, // page scripts can't read it
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    expires: new Date(expiresAt),
  });
}

/**
 * No sign-up: the first time someone follows, votes or comments they quietly get a
 * guest identity (a hanging-1234 handle) in a long-lived cookie. Created only on a
 * real action, so crawlers browsing the site don't mint accounts.
 */
async function ensureIdentity(): Promise<Response | null> {
  if (await sessionToken()) return null;
  const res = await apiFetch("/api/guest", { method: "POST" }, { auth: "none" });
  if (res.status === 429) {
    // Guest creation is capped per network. Hand back an ordinary error response so
    // every caller shows this message in place instead of an error page.
    const detail = "Too many new visitors from your network right now. Try again in a few minutes.";
    return Response.json({ detail }, { status: 429 });
  }
  if (!res.ok) throw new Error(`could not create a guest identity (${res.status})`);
  const session = (await res.json()) as { session_token: string; expires_at: string };
  await setSession(session.session_token, session.expires_at);
  return null;
}

/** Run an action as the reader; a stale cookie (deleted guest, expired) is replaced once. */
async function asReader(call: () => Promise<Response>): Promise<Response> {
  const refused = await ensureIdentity();
  if (refused) return refused;
  let res = await call();
  if (res.status === 401) {
    (await cookies()).delete(SESSION_COOKIE);
    const refusedAgain = await ensureIdentity();
    if (refusedAgain) return refusedAgain;
    res = await call();
  }
  return res;
}

async function errorMessage(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown };
    return typeof body.detail === "string" ? body.detail : "something went wrong";
  } catch {
    return "something went wrong";
  }
}

// --- email (optional) --------------------------------------------------------------

export async function requestSignInLink(formData: FormData): Promise<void> {
  const email = String(formData.get("email") ?? "").trim();
  const next = safePath(formData.get("next"));
  const res = await apiFetch(
    "/api/auth/request-link",
    { method: "POST", body: JSON.stringify({ email, next }) },
    { auth: "none" },
  );
  if (res.status === 429) redirect(withQuery("/signin", { next, error: "slow-down" }));
  if (!res.ok) redirect(withQuery("/signin", { next, error: "invalid-email", email }));
  redirect(withQuery("/signin", { sent: email }));
}

/** Second step: a button press, so email link scanners can't use up the link.
 *  Sends the guest session along, so a guest's follows, votes and comments carry over. */
export async function completeSignIn(formData: FormData): Promise<void> {
  const token = String(formData.get("token") ?? "");
  const next = safePath(formData.get("next"));
  const res = await apiFetch(
    "/api/auth/verify",
    { method: "POST", body: JSON.stringify({ token }) },
    { auth: "optional" },
  );
  if (!res.ok) redirect(withQuery("/signin", { error: "expired-link", next }));
  const session = (await res.json()) as { session_token: string; expires_at: string };
  await setSession(session.session_token, session.expires_at);
  redirect(next);
}

export async function signOut(): Promise<void> {
  if (await sessionToken()) await apiFetch("/api/auth/logout", { method: "POST" });
  (await cookies()).delete(SESSION_COOKIE);
  redirect("/");
}

// --- participation (no sign-up) ------------------------------------------------------

export async function toggleFollow(formData: FormData): Promise<void> {
  const kind = String(formData.get("kind"));
  const target = String(formData.get("target"));
  const following = formData.get("following") === "1";
  await asReader(() =>
    apiFetch(`/api/me/follows/${encodeURIComponent(kind)}/${encodeURIComponent(target)}`, {
      method: following ? "DELETE" : "PUT",
    }),
  );
  refresh();
}

export async function toggleVote(formData: FormData): Promise<void> {
  const kind = String(formData.get("kind"));
  const id = Number(formData.get("id"));
  await asReader(() => apiFetch(`/api/votes/${encodeURIComponent(kind)}/${id}`, { method: "POST" }));
  refresh();
}

// --- settings ----------------------------------------------------------------------

export async function saveSettings(formData: FormData): Promise<void> {
  const body = {
    brief_enabled: formData.get("brief_enabled") === "on",
    brief_hour: Number(formData.get("brief_hour")),
    timezone: String(formData.get("timezone")),
  };
  await asReader(() => apiFetch("/api/me", { method: "PATCH", body: JSON.stringify(body) }));
  redirect("/brief?saved=1#settings");
}

export async function renameMe(formData: FormData): Promise<void> {
  const back = safePath(formData.get("back"), "/brief");
  const res = await asReader(() =>
    apiFetch("/api/me", { method: "PATCH", body: JSON.stringify({ handle: String(formData.get("handle") ?? "") }) }),
  );
  const [path, hash] = back.split("#");
  const query = res.ok ? { renamed: 1 } : { name_error: await errorMessage(res) };
  redirect(withQuery(path, query) + (hash ? `#${hash}` : ""));
}

export async function confirmUnsubscribe(formData: FormData): Promise<void> {
  const res = await apiFetch(
    "/api/unsubscribe",
    { method: "POST", body: JSON.stringify({ u: Number(formData.get("u")), t: String(formData.get("t")) }) },
    { auth: "none" },
  );
  redirect(res.ok ? "/unsubscribe?done=1" : "/unsubscribe?error=1");
}

// --- moderation --------------------------------------------------------------------

export async function moderate(formData: FormData): Promise<void> {
  const action = String(formData.get("action"));
  const path =
    action === "ban"
      ? `/api/mod/users/${Number(formData.get("user_id"))}/ban`
      : `/api/mod/comments/${Number(formData.get("id"))}/${action === "restore" ? "restore" : "remove"}`;
  await apiFetch(path, { method: "POST" });
  refresh();
}

// --- chat room (called from the client; return results instead of redirecting) ---------

export type ChatResult = { ok: true; handle?: string } | { ok: false; error: string };

export async function sendChatMessage(
  kind: "article" | "tool",
  targetId: number,
  body: string,
  parentId: number | null,
): Promise<ChatResult> {
  const res = await asReader(() =>
    apiFetch("/api/comments", {
      method: "POST",
      body: JSON.stringify({ target_kind: kind, target_id: targetId, body, parent_id: parentId }),
    }),
  );
  return res.ok ? { ok: true } : { ok: false, error: await errorMessage(res) };
}

export async function chatVote(commentId: number): Promise<ChatResult> {
  const res = await asReader(() => apiFetch(`/api/votes/comment/${commentId}`, { method: "POST" }));
  return res.ok ? { ok: true } : { ok: false, error: await errorMessage(res) };
}

export async function chatDelete(commentId: number): Promise<ChatResult> {
  const res = await asReader(() => apiFetch(`/api/comments/${commentId}`, { method: "DELETE" }));
  return res.ok ? { ok: true } : { ok: false, error: await errorMessage(res) };
}

export async function chatReport(commentId: number): Promise<ChatResult> {
  const res = await asReader(() =>
    apiFetch(`/api/comments/${commentId}/report`, {
      method: "POST",
      body: JSON.stringify({ reason: "reported from chat" }),
    }),
  );
  return res.ok ? { ok: true } : { ok: false, error: await errorMessage(res) };
}

/** `/nick newname` in chat. */
export async function chatNick(handle: string): Promise<ChatResult> {
  const res = await asReader(() => apiFetch("/api/me", { method: "PATCH", body: JSON.stringify({ handle }) }));
  if (!res.ok) return { ok: false, error: await errorMessage(res) };
  const me = (await res.json()) as { handle: string };
  return { ok: true, handle: me.handle };
}

// --- arena -----------------------------------------------------------------------------

export async function startBattle(formData: FormData): Promise<void> {
  const prompt = String(formData.get("prompt") ?? "");
  const res = await asReader(() => apiFetch("/api/arena/battles", { method: "POST", body: JSON.stringify({ prompt }) }));
  if (!res.ok) redirect(withQuery("/arena", { error: await errorMessage(res), prompt: prompt.slice(0, 500) }));
  const battle = (await res.json()) as { id: number };
  redirect(`/arena/b/${battle.id}`);
}

// A Battle has its own `error` field, so results are tagged with `ok` rather than
// told apart by key.
export type BattleResult = { ok: true; battle: Battle } | { ok: false; error: string };

export async function voteBattle(battleId: number, choice: "a" | "b" | "tie" | "bad"): Promise<BattleResult> {
  const res = await asReader(() =>
    apiFetch(`/api/arena/battles/${battleId}/vote`, { method: "POST", body: JSON.stringify({ choice }) }),
  );
  return res.ok ? { ok: true, battle: (await res.json()) as Battle } : { ok: false, error: await errorMessage(res) };
}

export async function shareBattle(battleId: number): Promise<BattleResult> {
  const res = await asReader(() => apiFetch(`/api/arena/battles/${battleId}/share`, { method: "POST" }));
  return res.ok ? { ok: true, battle: (await res.json()) as Battle } : { ok: false, error: await errorMessage(res) };
}
