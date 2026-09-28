"""Near-duplicate headlines with MinHash + LSH.

The same story appears on many sites with small wording changes. MinHash turns
a headline's word set into a signature whose positions agree with probability
equal to the Jaccard similarity of the two word sets, so one extra word in a
12-word headline barely moves it (SimHash, built for long documents, flips
many bits on text that short).

MinHashLSH avoids comparing a new item against every stored one: the
signature is cut into bands, and only items sharing an entire band with the
query become candidates (dict lookups instead of a linear scan). With 32 bands
of 4 rows, pairs above ~0.45 similarity are very likely to collide; candidates
are then checked against the real threshold.

Reworded coverage ("Gates: A.I. could cause 1B deaths") shares too few words
for this; catching those is a job for embeddings (M2).
"""

import hashlib
import random
import re
from collections import defaultdict

NUM_PERM = 128
BANDS = 32
ROWS = NUM_PERM // BANDS
_PRIME = (1 << 61) - 1  # values stay below 2**61, so they fit in Postgres BIGINT

# Fixed seed: signatures are stored, so they must be identical across processes and deploys.
_rng = random.Random(0x48414E47)
_PERMUTATIONS = [(_rng.randrange(1, _PRIME), _rng.randrange(0, _PRIME)) for _ in range(NUM_PERM)]

_TOKEN = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    """a an and are as at be by for from has have in is it its of on or says that the this
    to was were will with""".split()  # noqa: SIM905
)

Signature = list[int]


def tokens(text: str) -> set[str]:
    return {t for t in _TOKEN.findall(text.lower()) if t not in _STOPWORDS}


def _hash64(token: str) -> int:
    return int.from_bytes(hashlib.blake2b(token.encode(), digest_size=8).digest(), "big")


def minhash(text: str) -> Signature | None:
    hashes = [_hash64(t) for t in tokens(text)]
    if not hashes:
        return None
    return [min((a * h + b) % _PRIME for h in hashes) for a, b in _PERMUTATIONS]


def similarity(a: Signature, b: Signature) -> float:
    """Estimated Jaccard similarity of the two underlying word sets."""
    return sum(x == y for x, y in zip(a, b, strict=True)) / len(a)


class MinHashLSH:
    def __init__(self, threshold: float = 0.75) -> None:
        self.threshold = threshold
        self._buckets: list[dict[tuple[int, ...], list[tuple[int, Signature]]]] = [
            defaultdict(list) for _ in range(BANDS)
        ]

    @staticmethod
    def _bands(signature: Signature):
        for band in range(BANDS):
            yield band, tuple(signature[band * ROWS : (band + 1) * ROWS])

    def add(self, item_id: int, signature: Signature) -> None:
        for band, key in self._bands(signature):
            self._buckets[band][key].append((item_id, signature))

    def find_near(self, signature: Signature) -> int | None:
        """Id of the most similar stored item at or above the threshold, or None."""
        best: tuple[float, int] | None = None
        checked: set[int] = set()
        for band, key in self._bands(signature):
            for item_id, other in self._buckets[band].get(key, ()):
                if item_id in checked:
                    continue
                checked.add(item_id)
                score = similarity(signature, other)
                if score >= self.threshold and (best is None or score > best[0]):
                    best = (score, item_id)
        return best[1] if best else None
