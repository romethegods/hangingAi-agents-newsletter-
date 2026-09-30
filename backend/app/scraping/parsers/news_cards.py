"""Config-driven parser for news homepages built from repeated "cards".

Adding a news outlet should be a CardSelectors entry in the registry, not new code.
"""

from dataclasses import dataclass

from selectolax.parser import HTMLParser

from app.scraping.parsers._html import absolute, date_from_url, text_of
from app.scraping.types import ContentType, ParseResult, RawItem


@dataclass(frozen=True, slots=True)
class CardSelectors:
    card: str = "article"
    link: str = "a[href]"
    title: str = "h1, h2, h3, h4"
    summary: str | None = None
    image: str | None = "img[src]"
    # Only keep links whose absolute URL contains this (e.g. "/2026/" style article paths).
    link_must_contain: str | None = None
    # (old, new) substring swap to request a larger image size, e.g. ("_xs.", "_md.").
    image_size: tuple[str, str] | None = None


def parse_cards(html: str, base_url: str, selectors: CardSelectors) -> ParseResult:
    result = ParseResult()
    seen: set[str] = set()
    for card in HTMLParser(html).css(selectors.card):
        link = card.css_first(selectors.link)
        url = absolute(base_url, link.attributes.get("href") if link else None)
        title = text_of(card.css_first(selectors.title), limit=300)
        if not url or not title or url in seen:
            continue
        if selectors.link_must_contain and selectors.link_must_contain not in url:
            continue
        seen.add(url)
        image = card.css_first(selectors.image) if selectors.image else None
        image_url = absolute(base_url, image.attributes.get("src") if image else None)
        if image_url and selectors.image_size:
            image_url = image_url.replace(*selectors.image_size)
        result.items.append(
            RawItem(
                url=url,
                title=title,
                content_type=ContentType.NEWS,
                summary=text_of(card.css_first(selectors.summary), limit=400)
                if selectors.summary
                else None,
                image_url=image_url,
                published_at=date_from_url(url),
            )
        )
    return result
