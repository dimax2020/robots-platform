"""Монте-Карло по достоверности данных (§8.4)."""

from __future__ import annotations

import random
import re

from .models import AttrValue, CalcNorm, CalcRequest, Catalog, Interval, Reliability, Source

RELIABILITY: dict[str, Reliability] = {
    "vendor": "A",
    "dealer": "B",
    "media": "B",
    "catalog": "B",
    "analogue": "C",
    "assumption": "D",
}

SPREAD: dict[Reliability, float] = {"A": 0.02, "B": 0.10, "C": 0.30, "D": 0.40}


def confirms(value: object, quote: str | None) -> bool:
    norm = lambda s: re.sub(r"[\s ,]", "", str(s)).lower()  # noqa: E731
    return bool(quote) and norm(value) in norm(quote)


def reliability(a: AttrValue, src: Source) -> Reliability:
    """Достоверность выводится из источника, а не хранится (§6.3)."""
    grade = RELIABILITY[src.kind]
    if grade in ("A", "B") and not confirms(a.value, a.quote):
        return "C"
    return grade


def sample(a: AttrValue, src: Source, rng: random.Random) -> float:
    s = SPREAD[reliability(a, src)]
    assert isinstance(a.value, (int, float))
    return a.value * rng.triangular(1 - s, 1 + s, 1.0)


def monte_carlo(req: CalcRequest, catalog: Catalog, norms: list[CalcNorm], n: int = 2000) -> Interval:
    # TODO(E6): n прогонов cost_only с sampler=sample, разложение дисперсии по входам.
    raise NotImplementedError("Монте-Карло реализуется на этапе E6")
