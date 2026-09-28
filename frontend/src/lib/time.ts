import { connection } from "next/server";

/**
 * The request's clock reading, for relative dates like "3 hr. ago".
 *
 * Read once per request and pass it down as a prop, so every component renders
 * the same "now" and stays pure. `connection()` marks the caller as request-time,
 * so the value is never baked into a prerendered page.
 */
export async function requestNow(): Promise<number> {
  await connection();
  return Date.now();
}
