"use client";

import Image from "next/image";
import { useState } from "react";

/**
 * A hotlinked third-party image in a 16:9 ink frame. Hotlinks break (moved
 * files, expired links), so failures fall back to a flat geometric placeholder
 * instead of a broken-image icon.
 */
export function RemoteImage({
  src,
  alt,
  sizes,
  className = "",
  priority = false,
  position = "center",
  fit = "cover",
  fallback,
}: {
  src: string | null;
  alt: string;
  sizes: string;
  className?: string;
  priority?: boolean;
  /** "top" keeps the head of tall images, e.g. a paper's title block. */
  position?: "center" | "top";
  /** "contain" shows the whole image (letterboxed); "cover" fills and crops. */
  fit?: "cover" | "contain";
  /** Shown when there's no image or it fails to load; defaults to flat shapes. */
  fallback?: React.ReactNode;
}) {
  const [failed, setFailed] = useState(false);
  return (
    <div className={`relative aspect-video overflow-hidden border-2 border-ink bg-paper ${className}`}>
      {src && !failed ? (
        <Image
          src={src}
          alt={alt}
          fill
          sizes={sizes}
          priority={priority}
          referrerPolicy="no-referrer"
          className={`${fit === "contain" ? "object-contain" : "object-cover"} ${position === "top" ? "object-top" : ""}`}
          onError={() => setFailed(true)}
        />
      ) : fallback ? (
        fallback
      ) : (
        <div aria-hidden="true" className="halftone absolute inset-0 flex items-center justify-center gap-3">
          <span className="h-8 w-8 rounded-full border-2 border-ink bg-tomato" />
          <span className="h-8 w-8 rotate-12 border-2 border-ink bg-cobalt" />
          <span className="h-0 w-0 border-x-[18px] border-b-[30px] border-x-transparent border-b-mustard" />
        </div>
      )}
    </div>
  );
}
