import re
from datetime import UTC, datetime
from urllib.parse import urljoin

from selectolax.parser import Node

_WS = re.compile(r"\s+")
_NUMBER = re.compile(r"\d[\d,]*")
_DATE_IN_PATH = re.compile(r"/(20\d{2})/(\d{2})/(\d{2})/")


def text_of(node: Node | None, limit: int | None = None) -> str | None:
    if node is None:
        return None
    text = _WS.sub(" ", node.text(separator=" ", strip=True)).strip()
    if limit and len(text) > limit:
        text = text[: limit - 1].rsplit(" ", 1)[0] + "…"
    return text or None


def int_of(text: str | None) -> int | None:
    match = _NUMBER.search(text or "")
    return int(match.group().replace(",", "")) if match else None


def absolute(base_url: str, href: str | None) -> str | None:
    return urljoin(base_url, href) if href else None


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def date_from_url(url: str) -> datetime | None:
    match = _DATE_IN_PATH.search(url)
    if not match:
        return None
    try:
        return datetime(*map(int, match.groups()), tzinfo=UTC)
    except ValueError:
        return None
