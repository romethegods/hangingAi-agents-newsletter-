"use client"; // Error boundaries must be Client Components

import { useEffect } from "react";

export default function Error({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="mx-auto max-w-md space-y-4 py-16 text-center">
      <p className="kicker text-tomato">Wire down</p>
      <h1 className="font-display text-4xl font-black">Something went wrong</h1>
      <p className="text-muted">We couldn&apos;t load this right now. It&apos;s usually temporary.</p>
      <button
        type="button"
        onClick={() => retry()}
        className="kicker border-2 border-ink bg-tomato px-4 py-2 font-bold text-on-accent shadow-hard-sm"
      >
        Try again
      </button>
    </div>
  );
}
