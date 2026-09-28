"""URL canonicalization for exact-duplicate detection.

Two URLs that point at the same story ("http://www.x.com/a/?utm_source=tw" and
"https://x.com/a") must hash to the same key, so that the unique index on
articles.url_hash rejects the second copy.
"""

import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING_PARAMS = frozenset(
    {"fbclid", "gclid", "dclid", "msclkid", "mc_cid", "mc_eid", "ref", "ref_src", "cmpid", "igshid"}
)
_DEFAULT_PORTS = {"http": 80, "https": 443}


def canonicalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    if scheme in _DEFAULT_PORTS:
        scheme = "https"

    host = (parts.hostname or "").lower().removeprefix("www.")
    port = parts.port
    netloc = (
        host
        if port is None or port == _DEFAULT_PORTS.get(parts.scheme.lower())
        else f"{host}:{port}"
    )

    path = parts.path or "/"
    if len(path) > 1:
        path = path.rstrip("/")

    query = sorted(
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in _TRACKING_PARAMS
    )
    return urlunsplit((scheme, netloc, path, urlencode(query), ""))


def url_hash(canonical_url: str) -> str:
    return hashlib.sha256(canonical_url.encode()).hexdigest()
