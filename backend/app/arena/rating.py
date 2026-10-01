"""Elo ratings from pairwise human votes (as in chess, or LMSYS Chatbot Arena).

Each vote moves both ratings by K * (actual - expected). Beating a stronger
model gains more than beating a weaker one. New models use a larger K so they
find their level quickly, then settle.
"""

import math
import random
from collections.abc import Sequence

START_RATING = 1000.0
PROVISIONAL_BATTLES = 30
K_PROVISIONAL = 32.0
K_SETTLED = 16.0

# A vote's outcome for model A: 1 = A won, 0 = B won, 0.5 = tie / both bad.
OUTCOME = {"a": 1.0, "b": 0.0, "tie": 0.5, "bad": 0.5}


def expected_score(rating_a: float, rating_b: float) -> float:
    """Probability A beats B under the Elo model."""
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))


def k_factor(battles: int) -> float:
    return K_PROVISIONAL if battles < PROVISIONAL_BATTLES else K_SETTLED


def update(
    rating_a: float, rating_b: float, outcome_a: float, battles_a: int, battles_b: int
) -> tuple[float, float]:
    """New (rating_a, rating_b) after one vote."""
    expected_a = expected_score(rating_a, rating_b)
    new_a = rating_a + k_factor(battles_a) * (outcome_a - expected_a)
    new_b = rating_b + k_factor(battles_b) * ((1 - outcome_a) - (1 - expected_a))
    return new_a, new_b


def pick_pair[T](
    candidates: Sequence[T], battles: Sequence[int], rng: random.Random | None = None
) -> tuple[T, T]:
    """Two distinct models, favoring those with fewer battles so ratings fill in
    evenly (weight 1/sqrt(battles+1)). Order is random: position bias is real, so
    neither slot systematically gets the newer or stronger model."""
    if len(candidates) < 2:
        raise ValueError("the Arena needs at least two models")
    rng = rng or random.Random()
    weights = [1 / math.sqrt(b + 1) for b in battles]
    first = rng.choices(range(len(candidates)), weights=weights)[0]
    rest = [i for i in range(len(candidates)) if i != first]
    second = rng.choices(rest, weights=[weights[i] for i in rest])[0]
    pair = [candidates[first], candidates[second]]
    rng.shuffle(pair)
    return pair[0], pair[1]
