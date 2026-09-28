import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-md space-y-3 py-16 text-center">
      <h1 className="text-2xl font-bold">Not found</h1>
      <p className="text-muted">That page or story doesn&apos;t exist, or it has aged out.</p>
      <Link href="/" className="inline-block font-medium text-accent hover:underline">
        Back to the feed
      </Link>
    </div>
  );
}
