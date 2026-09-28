export type QueryValue = string | number | null | undefined;

/** Build "path?a=1&b=2", dropping empty values so URLs stay canonical. */
export function withQuery(path: string, query: Record<string, QueryValue>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
  }
  const qs = params.toString();
  return qs ? `${path}?${qs}` : path;
}

type SearchParams = Record<string, string | string[] | undefined>;

/** First value of a query param (`?a=1&a=2` gives "1"). */
export function param(searchParams: SearchParams, key: string): string | undefined {
  const value = searchParams[key];
  return Array.isArray(value) ? value[0] : value;
}

/** Query param constrained to an allowed set, falling back to a default. */
export function oneOf<T extends string>(
  value: string | undefined,
  allowed: readonly T[],
  fallback: T,
): T {
  return allowed.includes(value as T) ? (value as T) : fallback;
}

/** Positive integer query param (page numbers), clamped to [1, max]. */
export function positiveInt(value: string | undefined, max = 1000): number {
  const n = Number.parseInt(value ?? "", 10);
  return Number.isFinite(n) && n >= 1 ? Math.min(n, max) : 1;
}
