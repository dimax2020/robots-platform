"""Сборка каталога из БД: карточки, дерево, снимок для движка.

Иерархия здесь именно собирается джойнами, а не читается из дерева (§6.1): продукт висит
только на типе решения, поэтому его процессы, объекты и отрасли выводятся по цепочке
справочников. Один и тот же продукт законно попадает в несколько ветвей.
"""

from __future__ import annotations

import json
from collections import defaultdict
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.config import get_settings
from api.db.models import (
    AttributeDef,
    CatalogVersion,
    Industry,
    IndustryObject,
    ObjectProcess,
    ObjectType,
    Process,
    Product,
    ProductCase,
    ProcessSolution,
    SolutionType,
    Source,
)
from api.db.models import CalcNorm as DbCalcNorm
from api.schemas.catalog import (
    AttributeDefOut,
    CatalogAttrs,
    CaseOut,
    CompareParamOut,
    ProductCard,
    ProductDetail,
    RefOut,
    SourceOut,
    TreeNodeOut,
)
from engine.mc import RELIABILITY
from engine.models import AttrValue, CalcNorm, Catalog
from engine.models import Product as EngineProduct
from engine.models import SolutionType as EngineSolutionType
from engine.models import Source as EngineSource
from engine.models import AttributeDef as EngineAttributeDef
from engine.rules import validate_rule_spec


def current_version_id(db: Session) -> int:
    """Последняя опубликованная версия каталога (§6.5)."""
    return db.scalar(select(func.max(CatalogVersion.id))) or 0


def auto_match(trl: int | None, availability: str) -> bool:
    """Продукт со статусом rnd или УГТ ниже 5 в автоподбор не попадает."""
    return availability != "rnd" and (trl or 0) >= 5


class Hierarchy:
    """Связи справочников, загруженные один раз: из них выводятся ветви и состав карточки."""

    def __init__(self, db: Session) -> None:
        self.industries = {i.id: i for i in db.scalars(select(Industry)).all()}
        self.object_types = {o.id: o for o in db.scalars(select(ObjectType)).all()}
        self.processes = {p.id: p for p in db.scalars(select(Process)).all()}
        self.solution_types = {s.id: s for s in db.scalars(select(SolutionType)).all()}

        self.objects_of_industry: dict[int, list[int]] = defaultdict(list)
        self.industries_of_object: dict[int, list[int]] = defaultdict(list)
        for link in db.scalars(select(IndustryObject)).all():
            self.objects_of_industry[link.industry_id].append(link.object_type_id)
            self.industries_of_object[link.object_type_id].append(link.industry_id)

        self.processes_of_object: dict[int, list[int]] = defaultdict(list)
        self.objects_of_process: dict[int, list[int]] = defaultdict(list)
        for link in db.scalars(select(ObjectProcess)).all():
            self.processes_of_object[link.object_type_id].append(link.process_id)
            self.objects_of_process[link.process_id].append(link.object_type_id)

        self.solutions_of_process: dict[int, list[int]] = defaultdict(list)
        self.processes_of_solution: dict[int, list[int]] = defaultdict(list)
        for link in db.scalars(select(ProcessSolution)).all():
            self.solutions_of_process[link.process_id].append(link.solution_type_id)
            self.processes_of_solution[link.solution_type_id].append(link.process_id)

    def refs_for_solution(self, solution_type_id: int) -> tuple[list[RefOut], list[RefOut], list[RefOut]]:
        """Процессы, типы объектов и отрасли, доступные продукту через его тип решения."""
        process_ids = self.processes_of_solution.get(solution_type_id, [])
        object_ids: list[int] = []
        for pid in process_ids:
            for oid in self.objects_of_process.get(pid, []):
                if oid not in object_ids:
                    object_ids.append(oid)
        industry_ids: list[int] = []
        for oid in object_ids:
            for iid in self.industries_of_object.get(oid, []):
                if iid not in industry_ids:
                    industry_ids.append(iid)

        ref = lambda obj: RefOut(code=obj.code, name=obj.name)  # noqa: E731
        return (
            [ref(self.processes[pid]) for pid in process_ids],
            [ref(self.object_types[oid]) for oid in object_ids],
            [ref(self.industries[iid]) for iid in industry_ids],
        )


def _required_defs(defs: list[AttributeDef], solution_code: str) -> list[AttributeDef]:
    return [d for d in defs if not d.required_for or solution_code in d.required_for]


def _completeness(product: Product, defs: list[AttributeDef], solution_code: str) -> tuple[int, int]:
    """Заполненность не хранится, а считается (§6.3)."""
    required = _required_defs(defs, solution_code)
    filled = sum(
        1
        for d in required
        if (a := product.attrs.get(d.key)) and a.get("status") in ("known", "not_applicable")
    )
    return filled, len(required)


def _price(product: Product) -> tuple[float | None, str | None]:
    raw = product.attrs.get("price_rub") or {}
    if raw.get("status") != "known":
        return None, raw.get("note")
    value = raw.get("value")
    return (float(value) if isinstance(value, (int, float)) else None), raw.get("note")


def _region(product: Product) -> str | None:
    raw = product.attrs.get("region") or {}
    value = raw.get("value")
    return value if isinstance(value, str) else None


def card_of(product: Product, hier: Hierarchy, defs: list[AttributeDef]) -> ProductCard:
    solution = hier.solution_types[product.solution_type_id]
    processes, objects, industries = hier.refs_for_solution(product.solution_type_id)
    price, price_note = _price(product)
    filled, total = _completeness(product, defs, solution.code)
    return ProductCard(
        id=product.id,
        slug=product.slug,
        name=product.name,
        manufacturer=product.manufacturer,
        legal_entity=product.legal_entity,
        country=product.country,
        region=_region(product),
        availability=product.availability,
        trl=product.trl,
        market_potential=product.market_potential,
        auto_match=auto_match(product.trl, product.availability),
        solution_type=RefOut(code=solution.code, name=solution.name),
        family=solution.family,
        processes=processes,
        object_types=objects,
        industries=industries,
        price_rub=price,
        price_note=price_note,
        completeness_filled=filled,
        completeness_total=total,
    )


def source_out(src: Source, usage_count: int = 0) -> SourceOut:
    return SourceOut(
        id=src.id,
        kind=src.kind,
        reliability=RELIABILITY[src.kind],
        url=src.url,
        publisher=src.publisher,
        title=src.title,
        captured_at=src.captured_at,
        rationale=src.rationale,
        last_checked_at=src.last_checked_at,
        usage_count=usage_count,
    )


def source_usage(db: Session) -> dict[int, int]:
    """Сколько значений в attrs и кейсов ссылается на каждый источник."""
    usage: dict[int, int] = defaultdict(int)
    for (attrs,) in db.execute(select(Product.attrs).where(Product.valid_to.is_(None))):
        for value in attrs.values():
            if isinstance(value, dict) and (sid := value.get("source_id")) is not None:
                usage[sid] += 1
    for (sid,) in db.execute(select(ProductCase.source_id).where(ProductCase.source_id.is_not(None))):
        usage[sid] += 1
    return dict(usage)


def attribute_defs(db: Session) -> list[AttributeDef]:
    return list(db.scalars(select(AttributeDef).order_by(AttributeDef.sort, AttributeDef.key)).all())


def attribute_defs_out(db: Session) -> list[AttributeDefOut]:
    return [AttributeDefOut.model_validate(d, from_attributes=True) for d in attribute_defs(db)]


def current_products(db: Session) -> list[Product]:
    return list(
        db.scalars(
            select(Product).where(Product.valid_to.is_(None)).order_by(Product.name)
        ).all()
    )


def product_cards(db: Session) -> list[ProductCard]:
    hier = Hierarchy(db)
    defs = attribute_defs(db)
    return [card_of(p, hier, defs) for p in current_products(db)]


_BETTER = frozenset({"max", "min", "none"})


def catalog_attrs(db: Session) -> CatalogAttrs:
    """Все attrs текущей версии одним проходом: product.attrs уже в JSONB строки (E4 §2)."""
    products = current_products(db)
    return CatalogAttrs(
        catalog_version_id=current_version_id(db),
        attrs={
            str(p.id): {k: AttrValue.model_validate(v) for k, v in p.attrs.items()}
            for p in products
        },
    )


def compare_spec() -> list[CompareParamOut]:
    """Спека сравнения из data/compare_spec.json через get_settings().data_dir (E4 §3)."""
    path = get_settings().data_dir / "compare_spec.json"
    if not path.is_file():
        raise FileNotFoundError(f"Файл спеки сравнения не найден: {path}")

    raw = json.loads(path.read_text(encoding="utf-8"))
    params = raw.get("params")
    if not isinstance(params, list) or not params:
        raise ValueError("compare_spec.json: пустой или отсутствующий список params")

    out: list[CompareParamOut] = []
    for i, item in enumerate(params):
        if not isinstance(item, dict):
            raise ValueError(f"compare_spec.json: params[{i}] не объект")
        rationale = item.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            raise ValueError(
                f"compare_spec.json: params[{i}] ({item.get('key')!r}) — пустой rationale"
            )
        better = item.get("better")
        if better not in _BETTER:
            raise ValueError(
                f"compare_spec.json: params[{i}] ({item.get('key')!r}) — "
                f"better={better!r}, ожидается max|min|none"
            )
        out.append(CompareParamOut.model_validate(item))
    return out


def product_detail(db: Session, key: str) -> ProductDetail | None:
    stmt = select(Product).where(Product.valid_to.is_(None))
    try:
        product = db.scalar(stmt.where(Product.id == UUID(key)))
    except ValueError:
        product = db.scalar(stmt.where(Product.slug == key))
    if product is None:
        return None

    hier = Hierarchy(db)
    defs = attribute_defs(db)
    base = card_of(product, hier, defs)

    cases = db.scalars(select(ProductCase).where(ProductCase.product_id == product.id)).all()
    case_out = [
        CaseOut(
            id=c.id,
            summary=c.summary,
            customer=c.customer,
            process=(
                RefOut(code=hier.processes[c.process_id].code, name=hier.processes[c.process_id].name)
                if c.process_id in hier.processes
                else None
            ),
            source_id=c.source_id,
        )
        for c in cases
    ]

    # Источники, на которые ссылаются значения этого продукта и его кейсы
    source_ids = {
        a["source_id"]
        for a in product.attrs.values()
        if isinstance(a, dict) and a.get("source_id") is not None
    }
    source_ids |= {c.source_id for c in cases if c.source_id is not None}
    sources = (
        db.scalars(select(Source).where(Source.id.in_(source_ids))).all() if source_ids else []
    )

    attrs = {k: AttrValue.model_validate(v) for k, v in product.attrs.items()}
    return ProductDetail(
        **base.model_dump(),
        summary=product.summary,
        attrs=attrs,
        cases=case_out,
        sources=[source_out(s) for s in sources],
    )


def catalog_tree(db: Session) -> list[TreeNodeOut]:
    """Отрасль → тип объекта → процесс → тип решения → продукты (ТЗ 3.3.1)."""
    hier = Hierarchy(db)
    products_by_solution: dict[int, list[UUID]] = defaultdict(list)
    for product in current_products(db):
        products_by_solution[product.solution_type_id].append(product.id)

    nodes: list[TreeNodeOut] = []
    for industry in sorted(hier.industries.values(), key=lambda i: i.name):
        object_nodes: list[TreeNodeOut] = []
        for oid in hier.objects_of_industry.get(industry.id, []):
            obj = hier.object_types[oid]
            process_nodes: list[TreeNodeOut] = []
            for pid in hier.processes_of_object.get(oid, []):
                proc = hier.processes[pid]
                solution_nodes = [
                    TreeNodeOut(
                        key=f"{industry.code}/{obj.code}/{proc.code}/{hier.solution_types[sid].code}",
                        label=hier.solution_types[sid].name,
                        level="solution_type",
                        product_ids=products_by_solution.get(sid, []),
                    )
                    for sid in hier.solutions_of_process.get(pid, [])
                ]
                solution_nodes = [n for n in solution_nodes if n.product_ids]
                if not solution_nodes:
                    continue
                solution_nodes.sort(key=lambda n: (-len(n.product_ids), n.label))
                process_nodes.append(
                    TreeNodeOut(
                        key=f"{industry.code}/{obj.code}/{proc.code}",
                        label=proc.name,
                        level="process",
                        children=solution_nodes,
                    )
                )
            if not process_nodes:
                continue
            process_nodes.sort(key=lambda n: n.label)
            object_nodes.append(
                TreeNodeOut(
                    key=f"{industry.code}/{obj.code}",
                    label=obj.name,
                    level="object_type",
                    children=process_nodes,
                )
            )
        if not object_nodes:
            continue
        object_nodes.sort(key=lambda n: n.label)
        nodes.append(
            TreeNodeOut(
                key=industry.code,
                label=industry.name,
                level="industry",
                children=object_nodes,
            )
        )
    return nodes


def load_engine_catalog(db: Session) -> Catalog:
    """Снимок каталога для движка: грузится один раз в lifespan и живёт в app.state (§11.1)."""
    hier = Hierarchy(db)
    products = current_products(db)

    process_solutions: dict[str, list[str]] = defaultdict(list)
    for proc_code, sol_code in db.execute(
        select(Process.code, SolutionType.code)
        .select_from(ProcessSolution)
        .join(Process, Process.id == ProcessSolution.process_id)
        .join(SolutionType, SolutionType.id == ProcessSolution.solution_type_id)
    ):
        process_solutions[proc_code].append(sol_code)

    case_process_codes: dict[UUID, list[str]] = defaultdict(list)
    for product_id, proc_code in db.execute(
        select(ProductCase.product_id, Process.code).join(
            Process, Process.id == ProductCase.process_id
        )
    ):
        if proc_code not in case_process_codes[product_id]:
            case_process_codes[product_id].append(proc_code)

    solution_types: list[EngineSolutionType] = []
    for s in hier.solution_types.values():
        try:
            validate_rule_spec(s.rule_spec)
        except Exception as exc:
            raise ValueError(f"Битый RuleSpec у типа решения {s.code}: {exc}") from exc
        solution_types.append(
            EngineSolutionType(code=s.code, name=s.name, family=s.family, rule_spec=s.rule_spec)
        )

    return Catalog(
        version_id=current_version_id(db),
        solution_types=solution_types,
        products=[
            EngineProduct(
                id=p.id,
                solution_type_code=hier.solution_types[p.solution_type_id].code,
                name=p.name,
                manufacturer=p.manufacturer,
                legal_entity=p.legal_entity,
                country=p.country,
                availability=p.availability,
                trl=p.trl,
                market_potential=p.market_potential,
                summary=p.summary,
                attrs={k: AttrValue.model_validate(v) for k, v in p.attrs.items()},
                case_process_codes=case_process_codes.get(p.id, []),
            )
            for p in products
        ],
        attribute_defs=[
            EngineAttributeDef.model_validate(d, from_attributes=True) for d in attribute_defs(db)
        ],
        sources=[
            EngineSource.model_validate(s, from_attributes=True)
            for s in db.scalars(select(Source)).all()
        ],
        norms=[
            CalcNorm(
                key=n.key,
                value=float(n.value),
                unit=n.unit,
                solution_type_code=(
                    hier.solution_types[n.solution_type_id].code if n.solution_type_id else None
                ),
                source_id=n.source_id,
                editable=n.editable,
            )
            for n in db.scalars(select(DbCalcNorm)).all()
        ],
        process_solutions=dict(process_solutions),
    )


def reload_app_catalog(app: object, db: Session) -> Catalog:
    """Перечитать снимок в app.state. Битый RuleSpec падает здесь, а не в расчёте (§7.2)."""
    catalog = load_engine_catalog(db)
    app.state.catalog = catalog  # type: ignore[attr-defined]
    return catalog

