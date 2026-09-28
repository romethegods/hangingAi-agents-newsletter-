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
    <div className="mx-auto max-w-md space-y-3 py-16 text-center">
      <h1 className="text-2xl font-bold">Something went wrong</h1>
      <p className="text-muted">We couldn&apos;t load this right now. It&apos;s usually temporary.</p>
      <button
        type="button"
        onClick={() => retry()}
        className="rounded-md bg-accent px-4 py-2 font-medium text-white hover:opacity-90"
      >
        Try again
      </button>
    </div>
  );
}
