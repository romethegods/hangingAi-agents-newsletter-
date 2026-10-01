"use server";

import { cookies } from "next/headers";
import { refresh } from "next/cache";
import { redirect } from "next/navigation";

import { SESSION_COOKIE, apiFetch, sessionToken } from "./session";
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
async function ensureIdentity(): Promise<void> {
  if (await sessionToken()) return;
  const res = await apiFetch("/api/guest", { method: "POST" }, { auth: "none" });
  if (res.status === 429) throw new Error("Too many new visitors from your network; try again shortly.");
  if (!res.ok) throw new Error(`could not create a guest identity (${res.status})`);
  const session = (await res.json()) as { session_token: string; expires_at: string };
  await setSession(session.session_token, session.expires_at);
}

/** Run an action as the reader; a stale cookie (deleted guest, expired) is replaced once. */
async function asReader(call: () => Promise<Response>): Promise<Response> {
  await ensureIdentity();
  let res = await call();
  if (res.status === 401) {
    (await cookies()).delete(SESSION_COOKIE);
    await ensureIdentity();
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

export async function postComment(formData: FormData): Promise<void> {
  const back = safePath(formData.get("back"), "/");
  const body = {
    target_kind: String(formData.get("target_kind")),
    target_id: Number(formData.get("target_id")),
    body: String(formData.get("body") ?? ""),
    parent_id: formData.get("parent_id") ? Number(formData.get("parent_id")) : null,
  };
  const res = await asReader(() => apiFetch("/api/comments", { method: "POST", body: JSON.stringify(body) }));
  const [path] = back.split("#");
  if (!res.ok) redirect(withQuery(path, { comment_error: await errorMessage(res) }) + "#comments");
  const created = (await res.json()) as { id: number };
  redirect(`${path}#comment-${created.id}`);
}

export async function deleteComment(formData: FormData): Promise<void> {
  await asReader(() => apiFetch(`/api/comments/${Number(formData.get("id"))}`, { method: "DELETE" }));
  refresh();
}

export async function reportComment(formData: FormData): Promise<void> {
  const back = safePath(formData.get("back"), "/");
  await asReader(() =>
    apiFetch(`/api/comments/${Number(formData.get("id"))}/report`, {
      method: "POST",
      body: JSON.stringify({ reason: "reported from the site" }),
    }),
  );
  redirect(withQuery(back.split("#")[0], { reported: 1 }) + "#comments");
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
