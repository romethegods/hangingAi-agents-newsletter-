import { describe, expect, it } from "vitest";

import { compactNumber, edition, engagementLabel, hostname, timeAgo } from "./format";
import { displayName, hasPlayableDemo, popularity, previewImage } from "./tools";
import type { Tool } from "./types";
import { oneOf, param, positiveInt, withQuery } from "./url";

const NOW = Date.parse("2026-09-28T12:00:00Z");

describe("withQuery", () => {
  it("drops empty values so equivalent URLs are identical", () => {
    expect(withQuery("/tools", { sort: undefined, topic: "", page: null })).toBe("/tools");
    expect(withQuery("/", { tab: "papers", cursor: "a b" })).toBe("/?tab=papers&cursor=a+b");
    expect(withQuery("/api/tools", { limit: 30, offset: 0 })).toBe("/api/tools?limit=30&offset=0");
  });
});

describe("query param parsing", () => {
  it("takes the first of repeated params", () => {
    expect(param({ q: ["a", "b"] }, "q")).toBe("a");
    expect(param({}, "q")).toBeUndefined();
  });

  it("rejects values outside the allowed set", () => {
    expect(oneOf("stars", ["trending", "stars"] as const, "trending")).toBe("stars");
    expect(oneOf("<script>", ["trending", "stars"] as const, "trending")).toBe("trending");
    expect(oneOf(undefined, ["trending"] as const, "trending")).toBe("trending");
  });

  it("clamps page numbers", () => {
    expect(positiveInt("3")).toBe(3);
    expect(positiveInt("0")).toBe(1);
    expect(positiveInt("-4")).toBe(1);
    expect(positiveInt("abc")).toBe(1);
    expect(positiveInt("999999", 50)).toBe(50);
  });
});

describe("formatting", () => {
  it("formats relative times", () => {
    expect(timeAgo("2026-09-28T11:59:30Z", NOW)).toBe("just now");
    expect(timeAgo("2026-09-28T09:00:00Z", NOW)).toBe("3 hr. ago");
    expect(timeAgo("2026-09-27T12:00:00Z", NOW)).toBe("yesterday");
    expect(timeAgo("2026-09-14T12:00:00Z", NOW)).toBe("2 wk. ago");
  });

  it("formats counts and hosts", () => {
    expect(compactNumber(42444)).toBe("42.4K");
    expect(compactNumber(999)).toBe("999");
    expect(hostname("https://www.tmz.com/2026/09/27/x/")).toBe("tmz.com");
    expect(hostname("not a url")).toBe("not a url");
  });

  it("labels engagement by what the source actually measures", () => {
    expect(engagementLabel({ content_type: "paper", engagement: 110 })).toBe("▲ 110 upvotes");
    expect(engagementLabel({ content_type: "model", engagement: 4227 })).toBe("♥ 4.2K likes");
    expect(engagementLabel({ content_type: "news", engagement: 50 })).toBeNull();
    expect(engagementLabel({ content_type: "paper", engagement: null })).toBeNull();
  });
});

describe("edition", () => {
  it("numbers issues by New York calendar day from launch", () => {
    expect(edition(Date.parse("2026-09-28T16:00:00Z"))).toEqual({
      volume: 1,
      number: 1,
      dateline: "Monday, September 28, 2026",
    });
    // 01:00 UTC on the 29th is still the evening of the 28th in New York.
    expect(edition(Date.parse("2026-09-29T01:00:00Z")).number).toBe(1);
    expect(edition(Date.parse("2026-09-29T12:00:00Z")).number).toBe(2);
    expect(edition(Date.parse("2027-09-28T12:00:00Z"))).toMatchObject({ volume: 2, number: 366 });
  });
});

describe("tool helpers", () => {
  const base: Tool = {
    id: 1,
    platform: "github",
    full_name: "acme/agent",
    title: null,
    url: "https://github.com/acme/agent",
    description: null,
    language: null,
    stars: 42444,
    star_velocity: 0,
    topics: [],
    pushed_at: null,
    preview_image_url: null,
    demo_url: null,
    demo_kind: null,
  };

  it("uses real previews only, never GitHub's generated text cards", () => {
    expect(previewImage(base)).toBeNull(); // caller shows our ToolPoster
    expect(previewImage({ ...base, preview_image_url: "https://x/p.png" })).toBe("https://x/p.png");
    expect(
      previewImage({ ...base, preview_image_url: "https://opengraph.githubassets.com/abc/acme/agent" }),
    ).toBeNull();
    expect(
      previewImage({
        ...base,
        demo_kind: "embed",
        demo_url: "https://www.youtube-nocookie.com/embed/1p-SMEiK6Kg",
      }),
    ).toBe("https://i.ytimg.com/vi/1p-SMEiK6Kg/hqdefault.jpg");
  });

  it("labels popularity by platform and treats screenshots as non-playable", () => {
    expect(popularity(base)).toBe("★ 42.4K");
    expect(popularity({ ...base, platform: "huggingface" })).toBe("♥ 42.4K");
    expect(displayName({ ...base, title: "🤖 Acme" })).toBe("🤖 Acme");
    expect(displayName(base)).toBe("agent");
    expect(hasPlayableDemo({ ...base, demo_kind: "image" })).toBe(false);
    expect(hasPlayableDemo({ ...base, demo_kind: "embed" })).toBe(true);
    expect(hasPlayableDemo(base)).toBe(false);
  });
});
