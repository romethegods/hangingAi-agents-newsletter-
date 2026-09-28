from selectolax.parser import HTMLParser

from app.scraping.parsers._html import int_of, parse_iso, text_of
from app.scraping.types import ParseResult, RawTool


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
