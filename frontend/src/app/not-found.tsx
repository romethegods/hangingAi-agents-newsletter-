import Link from "next/link";

import { MastheadArt } from "@/components/Geometry";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-md space-y-4 py-12 text-center">
      <MastheadArt className="mx-auto w-40" />
      <p className="kicker text-tomato">Error 404 · Stop the presses</p>
      <h1 className="font-display text-4xl font-black">Not in this issue</h1>
      <p className="text-muted">That page or story doesn&apos;t exist, or it has aged out.</p>
      <Link
        href="/"
        className="kicker inline-block border-2 border-ink px-4 py-2 font-semibold shadow-hard-sm hover:bg-mustard hover:text-[#171614]"
      >
        Back to the front page
      </Link>
    </div>
  );
}
