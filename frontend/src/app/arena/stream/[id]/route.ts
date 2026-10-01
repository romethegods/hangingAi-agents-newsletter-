/**
 * Live answers for a battle, as server-sent events. Proxies the API's stream
 * with the reader's session (the cookie is httpOnly, so the browser can't send
 * it to the API itself). The body is passed through untouched, chunk by chunk.
 */
import { apiFetch } from "@/lib/session";

export async function GET(_request: Request, ctx: RouteContext<"/arena/stream/[id]">) {
  const { id } = await ctx.params;
  if (!/^\d+$/.test(id)) return Response.json({ detail: "not found" }, { status: 404 });
  const res = await apiFetch(`/api/arena/battles/${id}/stream`, { headers: { accept: "text/event-stream" } }, { auth: "optional" });
  if (!res.ok || !res.body) {
    return new Response(await res.text(), { status: res.status, headers: { "content-type": "application/json" } });
  }
  return new Response(res.body, {
    headers: {
      "content-type": "text/event-stream",
      "cache-control": "no-cache, no-transform",
      "x-accel-buffering": "no", // tell proxies (Caddy, nginx) not to buffer
    },
  });
}
