/**
 * Signed-in requests to the API. Never cached: every call carries the reader's
 * session, so responses are personal.
 *
 * The session lives in an httpOnly cookie (JavaScript in the page can't read it).
 * Account actions forward the visitor's IP so the API can rate-limit per visitor
 * even though the request comes from our own server.
 */
import { cookies, headers } from "next/headers";

import type {
  ArenaStatus,
  Battle,
  Brief,
  CommentThread,
  Follows,
  ModerationItem,
  User,
  VoteState,
} from "./types";

export const SESSION_COOKIE = "hai_session";
const API_URL = (process.env.API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export async function sessionToken(): Promise<string | undefined> {
  return (await cookies()).get(SESSION_COOKIE)?.value;
}

async function visitorIp(): Promise<string | undefined> {
  const h = await headers();
  return h.get("x-forwarded-for")?.split(",")[0]?.trim() || h.get("x-real-ip") || undefined;
}

export class SignInRequired extends Error {}

/**
 * Call the API as the current reader. auth: "required" throws SignInRequired when
 * there's no session, "optional" sends it if present (reading comments, merging a
 * guest at sign-in), "none" never does.
 */
export async function apiFetch(
  path: string,
  init: RequestInit = {},
  { auth = "required" }: { auth?: "required" | "optional" | "none" } = {},
): Promise<Response> {
  const token = auth === "none" ? undefined : await sessionToken();
  if (auth === "required" && !token) throw new SignInRequired();
  const ip = await visitorIp();
  return fetch(`${API_URL}${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      accept: "application/json",
      ...(init.body ? { "content-type": "application/json" } : {}),
      ...(token ? { authorization: `Bearer ${token}` } : {}),
      ...(ip ? { "x-client-ip": ip } : {}),
      ...init.headers,
    },
  });
}

async function getJson<T>(path: string): Promise<T | null> {
  try {
    const res = await apiFetch(path);
    if (res.status === 401) return null; // expired or revoked session
    if (!res.ok) throw new Error(`API ${res.status} for ${path}`);
    return (await res.json()) as T;
  } catch (error) {
    if (error instanceof SignInRequired) return null;
    throw error;
  }
}

async function getPublicJson<T>(path: string): Promise<T> {
  const res = await apiFetch(path, {}, { auth: "optional" });
  if (!res.ok) throw new Error(`API ${res.status} for ${path}`);
  return (await res.json()) as T;
}

export const getMe = () => getJson<User>("/api/me");
/** Comments and votes are public; with a session they also say which are yours. */
export const getComments = (kind: "article" | "tool", id: number) =>
  getPublicJson<CommentThread>(`/api/comments/${kind}/${id}`);
export const getArenaStatus = () => getPublicJson<ArenaStatus>("/api/arena/status");
export async function getBattle(id: number): Promise<Battle | null> {
  const res = await apiFetch(`/api/arena/battles/${id}`, {}, { auth: "optional" });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`API ${res.status} for battle ${id}`);
  return (await res.json()) as Battle;
}
export const getVoteState = (kind: "article" | "tool", id: number) =>
  getPublicJson<VoteState>(`/api/votes/${kind}/${id}`);
export async function getModerationQueue(): Promise<ModerationItem[] | null> {
  try {
    const res = await apiFetch("/api/mod/queue");
    return res.ok ? ((await res.json()) as ModerationItem[]) : null;
  } catch (error) {
    if (error instanceof SignInRequired) return null;
    throw error;
  }
}
export const getFollows = () => getJson<Follows>("/api/me/follows");
export const getBrief = () => getJson<Brief>("/api/me/brief");
