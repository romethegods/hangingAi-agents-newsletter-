import { describe, expect, it } from "vitest";

import { compactNumber, engagementLabel, hostname, timeAgo } from "./format";
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
