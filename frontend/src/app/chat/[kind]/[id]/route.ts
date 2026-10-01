/**
 * Polled by an open chat window. Proxies to the API with the reader's session
 * (so "mine"/"voted" are right) and their per-tab viewer id (for "N here now").
 * The session cookie is httpOnly, so the browser can't call the API itself.
 */
import { apiFetch } from "@/lib/session";

const KINDS = new Set(["article", "tool"]);

export async function GET(request: Request, ctx: RouteContext<"/chat/[kind]/[id]">) {
  const { kind, id } = await ctx.params;
  if (!KINDS.has(kind) || !/^\d+$/.test(id)) return Response.json({ detail: "not found" }, { status: 404 });
  const viewer = request.headers.get("x-viewer-id") ?? "";
  const res = await apiFetch(
    `/api/comments/${kind}/${id}`,
    { headers: /^[\w-]{8,64}$/.test(viewer) ? { "x-viewer-id": viewer } : {} },
    { auth: "optional" },
  );
  return new Response(res.body, {
    status: res.status,
    headers: { "content-type": "application/json", "cache-control": "no-store" },
  });
}
