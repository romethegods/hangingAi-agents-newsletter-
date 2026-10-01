"use client";

import { useState } from "react";

import type { DemoKind } from "@/lib/types";

import { RemoteImage } from "./RemoteImage";

/**
 * Plays a tool's demo from its source; nothing is re-hosted.
 *
 * Video files, YouTube players and live apps are click-to-load: until the
 * reader presses play we show the poster only, so the page stays fast (some
 * demo videos are 100 MB+) and no third-party code runs uninvited.
 */
export function DemoPlayer({
  kind,
  url,
  poster,
  posterFallback,
  title,
}: {
  kind: DemoKind;
  url: string;
  poster: string | null;
  posterFallback?: React.ReactNode;
  title: string;
}) {
  const [playing, setPlaying] = useState(false);
  const frame = "relative aspect-video w-full border-[3px] border-ink bg-ink shadow-hard";

  if (kind === "gif" || kind === "image") {
    // Whole image, never cropped: README screenshots and banners come in any shape.
    return (
      <RemoteImage src={url} alt={`${title} demo`} sizes="(min-width: 1024px) 768px, 100vw" fit="contain" priority />
    );
  }

  if (!playing) {
    return (
      <button
        type="button"
        onClick={() => setPlaying(true)}
        className={`${frame} group block overflow-hidden`}
        aria-label={kind === "app" ? `Launch the live ${title} demo` : `Play the ${title} demo`}
      >
        <RemoteImage
          src={poster}
          fallback={posterFallback}
          alt=""
          sizes="(min-width: 1024px) 768px, 100vw"
          className="border-0"
        />
        <span className="absolute inset-0 flex items-center justify-center">
          <span className="kicker flex items-center gap-2 border-[3px] border-ink bg-tomato px-5 py-3 text-sm font-bold text-on-accent shadow-hard transition-transform group-hover:-translate-y-0.5">
            ▶ {kind === "app" ? "Launch live demo" : "Play demo"}
          </span>
        </span>
      </button>
    );
  }

  if (kind === "video") {
    return (
      // README demo clips ship without caption tracks, so there are none to attach.
      <video src={url} controls autoPlay playsInline preload="metadata" className={frame} />
    );
  }

  if (kind === "embed") {
    return (
      <iframe
        src={`${url}?autoplay=1&rel=0`}
        title={`${title} demo video`}
        className={frame}
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
        referrerPolicy="strict-origin-when-cross-origin"
        allowFullScreen
      />
    );
  }

  // Live app (Hugging Face Space): a cross-origin page, sandboxed so it can't
  // navigate our tab away.
  return (
    <iframe
      src={url}
      title={`${title} live demo`}
      className="aspect-[4/3] w-full border-[3px] border-ink bg-paper-raised shadow-hard"
      sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-downloads allow-modals"
      allow="clipboard-write; microphone; camera"
      loading="lazy"
    />
  );
}
