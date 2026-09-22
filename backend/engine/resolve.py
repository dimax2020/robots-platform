"""Лестница достоверности: паспорт → медиана по классу → норматив-допущение (ТЗ 7.5, Дополнения §4).

Подстановки выполняются в момент расчёта и никогда не записываются в product.attrs.
Если ни одна ступень не сработала — возвращаем None: вызывающий шаг сам пишет trace.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

from .models import (
    AttrValue,
    CalcNorm,
    Catalog,
    Product,
    Reliability,
    Source,
    SourceKind,
)

_KIND_RELIABILITY: dict[SourceKind, Reliability] = {
    "vendor": "A",
    "dealer": "B",
    "media": "B",
    "catalog": "B",
    "analogue": "C",
    "assumption": "D",
}

_DEFAULT_MIN_SAMPLE = 3


@dataclass(frozen=True)
class Resolved:
    key: str
    value: float
    unit: str | None
    reliability: Reliability
    origin: Literal["vendor", "analogue_median", "assumption_norm"]
    source_id: int | None
    source_label: str
    message: str


def _fmt(value: float) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _parse_number(value: object) -> tuple[float, tuple[float, float] | None] | None:
    """Привести AttrValue.value к float. bool не число. Диапазон из двух чисел → середина."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value), None
    if isinstance(value, list):
        if len(value) != 2:
            return None
        try:
            lo, hi = float(value[0]), float(value[1])
        except (TypeError, ValueError):
            return None
        return (lo + hi) / 2.0, (lo, hi)
    if isinstance(value, str):
        parsed = _parse_number_str(value)
        if parsed is None:
            return None
        return parsed, None
    return None


def _parse_number_str(raw: str) -> float | None:
    s = raw.strip().replace("\u00a0", " ").replace("\u202f", " ")
    if not s:
        return None
    compact = s.replace(" ", "")
    if not compact:
        return None
    if "," in compact and "." in compact:
        return None
    if "," in compact:
        compact = compact.replace(",", ".")
    try:
        return float(compact)
    except ValueError:
        return None


def _brief_url(url: str) -> str:
    s = url.strip()
    for prefix in ("https://", "http://"):
        if s.lower().startswith(prefix):
            s = s[len(prefix) :]
            break
    if s.lower().startswith("www."):
        s = s[4:]
    return s.rstrip("/")


class Resolver:
    def __init__(self, catalog: Catalog, norms: list[CalcNorm]) -> None:
        self._family_of: dict[str, str] = {st.code: st.family for st in catalog.solution_types}
        self._sources: dict[int, Source] = {s.id: s for s in catalog.sources}
        self._norms: dict[str, CalcNorm] = {n.key: n for n in norms}
        self._attr_units: dict[str, str | None] = {d.key: d.unit for d in catalog.attribute_defs}

        min_sample = self.norm("analogue_min_sample")
        self._min_sample = int(min_sample) if min_sample is not None else _DEFAULT_MIN_SAMPLE

        by_type: dict[tuple[str, str], list[float]] = defaultdict(list)
        by_family: dict[tuple[str, str], list[float]] = defaultdict(list)
        for product in catalog.products:
            family = self._family_of.get(product.solution_type_code)
            for key, attr in product.attrs.items():
                if attr.status != "known":
                    continue
                parsed = _parse_number(attr.value)
                if parsed is None:
                    continue
                number, _ = parsed
                by_type[(product.solution_type_code, key)].append(number)
                if family is not None:
                    by_family[(family, key)].append(number)

        self._values_type: dict[tuple[str, str], list[float]] = dict(by_type)
        self._values_family: dict[tuple[str, str], list[float]] = dict(by_family)
        self._median_type: dict[tuple[str, str], float] = {
            scope_key: statistics.median(vals) for scope_key, vals in self._values_type.items()
        }
        self._median_family: dict[tuple[str, str], float] = {
            scope_key: statistics.median(vals) for scope_key, vals in self._values_family.items()
        }

    def robot(self, product: Product, key: str) -> Resolved | None:
        vendor = self._from_vendor(product, key)
        if vendor is not None:
            return vendor
        analogue = self._from_analogue(product, key)
        if analogue is not None:
            return analogue
        return self._from_assumption(product, key)

    def site(self, field: str, value: float | None, object_type_code: str) -> Resolved | None:
        if value is not None:
            number = float(value)
            unit = self._site_unit(field, object_type_code)
            return Resolved(
                key=field,
                value=number,
                unit=unit,
                reliability="B",
                origin="vendor",
                source_id=None,
                source_label="[B] датасет площадки",
                message=(
                    f"Поле площадки «{field}» задано в датасете площадки: "
                    f"{_with_unit(number, unit)}."
                ),
            )
        for norm_key in (f"default.site.{field}.{object_type_code}", f"default.site.{field}"):
            n = self._norms.get(norm_key)
            if n is None:
                continue
            return Resolved(
                key=field,
                value=n.value,
                unit=n.unit,
                reliability="D",
                origin="assumption_norm",
                source_id=n.source_id,
                source_label=f"[D] допущение: {norm_key} = {_fmt(n.value)}",
                message=f"Допущение: норматив {norm_key} = {_with_unit(n.value, n.unit)}.",
            )
        return None

    def norm(self, key: str) -> float | None:
        n = self._norms.get(key)
        return None if n is None else n.value

    def reliability_of(self, product: Product, key: str) -> Reliability | None:
        resolved = self.robot(product, key)
        return None if resolved is None else resolved.reliability

    def _from_vendor(self, product: Product, key: str) -> Resolved | None:
        attr = product.attrs.get(key)
        if attr is None or attr.status != "known":
            return None
        parsed = _parse_number(attr.value)
        if parsed is None:
            return None
        number, bounds = parsed
        source = self._source(attr.source_id)
        reliability = _reliability_of_source(source)
        unit = self._unit(key, attr=attr)
        if bounds is not None:
            lo, hi = bounds
            message = (
                f"Значение «{key}» — середина диапазона {_fmt(lo)}–{_fmt(hi)} "
                f"= {_with_unit(number, unit)}."
            )
        else:
            message = f"Значение «{key}» взято из паспорта продукта: {_with_unit(number, unit)}."
        return Resolved(
            key=key,
            value=number,
            unit=unit,
            reliability=reliability,
            origin="vendor",
            source_id=attr.source_id,
            source_label=_vendor_source_label(reliability, source),
            message=message,
        )

    def _from_analogue(self, product: Product, key: str) -> Resolved | None:
        found = self._median_for(self._values_type, self._median_type, product.solution_type_code, key)
        scope = product.solution_type_code
        if found is None:
            family = self._family_of.get(product.solution_type_code)
            if family is None:
                return None
            found = self._median_for(self._values_family, self._median_family, family, key)
            scope = family
        if found is None:
            return None
        median, n = found
        unit = self._unit(key, norm=self._default_norm(key, product))
        return Resolved(
            key=key,
            value=median,
            unit=unit,
            reliability="C",
            origin="analogue_median",
            source_id=None,
            source_label=f"[C] медиана по классу {scope}, {n} позиций",
            message=f"Медиана «{key}» по классу {scope}, {n} позиций: {_with_unit(median, unit)}.",
        )

    def _from_assumption(self, product: Product, key: str) -> Resolved | None:
        n = self._default_norm(key, product)
        if n is None:
            return None
        unit = self._unit(key, norm=n)
        return Resolved(
            key=key,
            value=n.value,
            unit=unit,
            reliability="D",
            origin="assumption_norm",
            source_id=n.source_id,
            source_label=f"[D] допущение: {n.key} = {_fmt(n.value)}",
            message=f"Допущение: норматив {n.key} = {_with_unit(n.value, unit)}.",
        )

    def _default_norm(self, key: str, product: Product) -> CalcNorm | None:
        family = self._family_of.get(product.solution_type_code)
        candidates = []
        if family is not None:
            candidates.append(f"default.{key}.{family}")
        candidates.append(f"default.{key}")
        for norm_key in candidates:
            n = self._norms.get(norm_key)
            if n is not None:
                return n
        return None

    def _median_for(
        self,
        values: dict[tuple[str, str], list[float]],
        medians: dict[tuple[str, str], float],
        scope: str,
        key: str,
    ) -> tuple[float, int] | None:
        sample = values.get((scope, key))
        if sample is None or len(sample) < self._min_sample:
            return None
        return medians[(scope, key)], len(sample)

    def _unit(
        self,
        key: str,
        *,
        attr: AttrValue | None = None,
        norm: CalcNorm | None = None,
    ) -> str | None:
        if attr is not None and attr.unit:
            return attr.unit
        defn_unit = self._attr_units.get(key)
        if defn_unit:
            return defn_unit
        if norm is not None and norm.unit:
            return norm.unit
        fallback = self._norms.get(f"default.{key}")
        if fallback is not None and fallback.unit:
            return fallback.unit
        return None

    def _site_unit(self, field: str, object_type_code: str) -> str | None:
        for norm_key in (f"default.site.{field}.{object_type_code}", f"default.site.{field}"):
            n = self._norms.get(norm_key)
            if n is not None and n.unit:
                return n.unit
        return None

    def _source(self, source_id: int | None) -> Source | None:
        if source_id is None:
            return None
        return self._sources.get(source_id)


def _reliability_of_source(source: Source | None) -> Reliability:
    if source is None:
        return "D"
    return _KIND_RELIABILITY.get(source.kind, "D")


def _vendor_source_label(reliability: Reliability, source: Source | None) -> str:
    brief = ""
    if source is not None:
        if source.url:
            brief = _brief_url(source.url)
        elif source.publisher:
            brief = source.publisher
        elif source.title:
            brief = source.title
    if not brief:
        brief = "источник не указан"
    return f"[{reliability}] {brief}"


def _with_unit(value: float, unit: str | None) -> str:
    formatted = _fmt(value)
    return f"{formatted} {unit}" if unit else formatted
