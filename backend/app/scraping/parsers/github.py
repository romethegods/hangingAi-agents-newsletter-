import re
from dataclasses import dataclass
from urllib.parse import urljoin

from selectolax.parser import HTMLParser

from app.scraping.parsers._html import int_of, parse_iso, text_of
from app.scraping.types import Demo, DemoKind, ParseResult, RawTool


def _repo_path(href: str | None) -> str | None:
    path = (href or "").strip("/")
    return path if path.count("/") == 1 else None


def parse_trending(html: str, base_url: str = "https://github.com/trending") -> ParseResult:
    """github.com/trending: one article.Box-row per repository."""
    result = ParseResult()
    for row in HTMLParser(html).css("article.Box-row"):
        link = row.css_first("h2 a[href]")
        full_name = _repo_path(link.attributes.get("href") if link else None)
        if not full_name:
            continue
        stars = row.css_first('a[href$="/stargazers"]')
        forks = row.css_first('a[href$="/forks"]')
        result.tools.append(
            RawTool(
                full_name=full_name,
                description=text_of(row.css_first("p")),
                language=text_of(row.css_first('[itemprop="programmingLanguage"]')),
                stars=int_of(text_of(stars)) or 0,
                forks=int_of(text_of(forks)),
                stars_today=int_of(text_of(row.css_first("span.float-sm-right"))),
            )
        )
    return result


def parse_topic(html: str, base_url: str = "https://github.com/topics") -> ParseResult:
    """github.com/topics/<topic>: one article card per repository, sorted by stars."""
    result = ParseResult()
    for card in HTMLParser(html).css("article"):
        link = card.css_first("h3 a.text-bold[href]")
        full_name = _repo_path(link.attributes.get("href") if link else None)
        if not full_name:
            continue
        counter = card.css_first("#repo-stars-counter-star")
        stars = int_of(counter.attributes.get("title")) if counter else None
        updated = card.css_first("relative-time")
        result.tools.append(
            RawTool(
                full_name=full_name,
                description=text_of(card.css_first("p")),
                language=text_of(card.css_first('[itemprop="programmingLanguage"]')),
                stars=stars or 0,
                topics=[t for n in card.css("a.topic-tag") if (t := text_of(n))],
                pushed_at=parse_iso(updated.attributes.get("datetime") if updated else None),
            )
        )
    return result


# README media that is never a demo: status badges, shields, charts, sponsor logos.
_NOT_DEMO_HOSTS = (
    "shields.io",
    "badge",
    "trendshift.io",
    "star-history.com",
    "codecov",
    "deepwiki",
)
_DEMO_WORDS = re.compile(
    r"demo|screenshot|screen ?cast|tour|preview|example|showcase|in action", re.I
)
# Brand art, not a demo. Letter-only boundaries so "firecrawl_logo.png" and
# "assets/sponsors/x.png" match (\b treats "_" as part of the word).
_NOT_DEMO_WORDS = re.compile(
    r"(?<![a-z])(logos?|icons?|avatars?|sponsors?|banners?|badges?|waitlist)(?![a-z])", re.I
)
_RAW_PATH = re.compile(r"^/([^/]+)/([^/]+)/raw/(.+)$")
_YOUTUBE_ID = re.compile(
    r"(?:youtube\.com/(?:watch\?(?:.*&)?v=|embed/|shorts/)|youtu\.be/)([\w-]{11})"
)


def youtube_embed_url(href: str | None) -> str | None:
    """Official privacy-enhanced player URL for a YouTube link, or None."""
    match = _YOUTUBE_ID.search(href or "")
    return f"https://www.youtube-nocookie.com/embed/{match.group(1)}" if match else None


def _media_src(node, repo_base: str) -> str | None:
    """Absolute, stable URL for a README image/video, or None if unusable."""
    src = (node.attributes.get("src") or "").strip()
    if not src or src.startswith("data:"):
        return None
    # Signed links expire within minutes; they can't be stored.
    if "private-user-images.githubusercontent.com" in src or "jwt=" in src:
        return None
    # /owner/repo/raw/<ref>/<path> is disallowed for crawlers and just redirects to the CDN.
    if raw := _RAW_PATH.match(src):
        owner, repo, rest = raw.groups()
        return f"https://raw.githubusercontent.com/{owner}/{repo}/{rest}"
    return urljoin(repo_base, src)


@dataclass(frozen=True, slots=True)
class RepoMedia:
    preview_image_url: str | None  # the repo's social card (og:image), light enough for cards
    demo: Demo | None


def parse_repo_media(html: str, base_url: str) -> RepoMedia:
    tree = HTMLParser(html)
    og = tree.css_first('meta[property="og:image"]')
    preview = og.attributes.get("content") if og else None
    # Keep only previews the owner uploaded. GitHub's generated card just repeats the
    # repo name and description, which the site already shows as text.
    if preview and "opengraph.githubassets.com" in preview:
        preview = None
    return RepoMedia(preview_image_url=preview, demo=_pick_demo(tree, base_url))


def _pick_demo(tree: HTMLParser, base_url: str) -> Demo | None:
    """Pick the best demo from a repo page's rendered README.

    Preference: a video file, then a YouTube demo (a README image linking to a
    YouTube video), then an animated GIF, then an image whose alt text or filename
    says demo/screenshot/tour, then the first real content image.
    """
    readme = tree.css_first("article.markdown-body")
    if readme is None:
        return None

    for node in readme.css("video[src], video source[src]"):
        if url := _media_src(node, base_url):
            return Demo(url=url, kind=DemoKind.VIDEO)

    embeds, gifs, described, others = [], [], [], []
    for node in readme.css("img"):
        url = _media_src(node, base_url)
        # Proxied (camo) images keep the original URL here; judge that, not the proxy.
        original = node.attributes.get("data-canonical-src") or url or ""
        alt = node.attributes.get("alt") or ""
        if not url or original.lower().split("?")[0].endswith(".svg"):
            continue
        if any(host in original for host in _NOT_DEMO_HOSTS):
            continue
        if _NOT_DEMO_WORDS.search(alt) or _NOT_DEMO_WORDS.search(original.split("?")[0]):
            continue
        link = next((a for a in _ancestors(node) if a.tag == "a"), None)
        if embed := youtube_embed_url(link.attributes.get("href") if link else None):
            embeds.append(embed)
            continue
        if original.lower().split("?")[0].endswith(".gif"):
            gifs.append(url)
        elif _DEMO_WORDS.search(alt) or _DEMO_WORDS.search(original.rsplit("/", 1)[-1]):
            described.append(url)
        else:
            others.append(url)

    if embeds:
        return Demo(url=embeds[0], kind=DemoKind.EMBED)
    if gifs:
        return Demo(url=gifs[0], kind=DemoKind.GIF)
    if described or others:
        return Demo(url=(described or others)[0], kind=DemoKind.IMAGE)
    return None


def _ancestors(node, depth: int = 3):
    parent = node.parent
    while parent is not None and depth > 0:
        yield parent
        parent, depth = parent.parent, depth - 1
