"""Схема БД по §6. Имена таблиц и колонок — латиница, как зафиксировано в §0.5."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# §6.1 Иерархия каталога — справочники и связи
# ---------------------------------------------------------------------------


class Industry(Base):
    __tablename__ = "industry"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)


class ObjectType(Base):
    __tablename__ = "object_type"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)


class Process(Base):
    __tablename__ = "process"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)


class SolutionType(Base):
    __tablename__ = "solution_type"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    family: Mapped[str] = mapped_column(Text, nullable=False)  # семейство формул, §7.3
    rule_spec: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class IndustryObject(Base):
    __tablename__ = "industry_object"
    industry_id: Mapped[int] = mapped_column(ForeignKey("industry.id"), nullable=False)
    object_type_id: Mapped[int] = mapped_column(ForeignKey("object_type.id"), nullable=False)
    __table_args__ = (PrimaryKeyConstraint("industry_id", "object_type_id"),)


class ObjectProcess(Base):
    __tablename__ = "object_process"
    object_type_id: Mapped[int] = mapped_column(ForeignKey("object_type.id"), nullable=False)
    process_id: Mapped[int] = mapped_column(ForeignKey("process.id"), nullable=False)
    __table_args__ = (PrimaryKeyConstraint("object_type_id", "process_id"),)


class ProcessSolution(Base):
    __tablename__ = "process_solution"
    process_id: Mapped[int] = mapped_column(ForeignKey("process.id"), nullable=False)
    solution_type_id: Mapped[int] = mapped_column(ForeignKey("solution_type.id"), nullable=False)
    __table_args__ = (PrimaryKeyConstraint("process_id", "solution_type_id"),)


# ---------------------------------------------------------------------------
# §6.5 Версионирование каталога
# ---------------------------------------------------------------------------


class CatalogVersion(Base):
    __tablename__ = "catalog_version"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    published_by: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)


# ---------------------------------------------------------------------------
# §6.2 Продукт и параметры
# ---------------------------------------------------------------------------


class Product(Base):
    __tablename__ = "product"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    solution_type_id: Mapped[int] = mapped_column(ForeignKey("solution_type.id"), nullable=False)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)  # отклонение от §6.2, см. §15
    name: Mapped[str] = mapped_column(Text, nullable=False)
    manufacturer: Mapped[str] = mapped_column(Text, nullable=False)
    legal_entity: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(Text)
    availability: Mapped[str] = mapped_column(Text, nullable=False)  # operation | piloting | rnd
    trl: Mapped[int | None] = mapped_column(SmallInteger)
    market_potential: Mapped[int | None] = mapped_column(SmallInteger)
    summary: Mapped[str | None] = mapped_column(Text)
    png_url: Mapped[str | None] = mapped_column(Text)
    attrs: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )  # ключ attribute_def.key → AttrValue
    valid_from: Mapped[int] = mapped_column(ForeignKey("catalog_version.id"), nullable=False)
    valid_to: Mapped[int | None] = mapped_column(ForeignKey("catalog_version.id"))

    __table_args__ = (
        Index("ix_product_attrs", "attrs", postgresql_using="gin", postgresql_ops={"attrs": "jsonb_path_ops"}),
        Index(
            "ix_product_solution_type_current",
            "solution_type_id",
            postgresql_where=text("valid_to IS NULL"),
        ),
        # GIN pg_trgm по (name || ' ' || manufacturer) — создаётся в миграции 0001 через op.execute.
    )


class AttributeDef(Base):
    """Новый параметр = строка, не миграция (ТЗ 3.2.6, 4.2.6)."""

    __tablename__ = "attribute_def"
    key: Mapped[str] = mapped_column(Text, primary_key=True)
    group_code: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[str | None] = mapped_column(Text)
    datatype: Mapped[str] = mapped_column(Text, nullable=False)  # number | range | text | enum | bool
    enum_values: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    required_for: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    sort: Mapped[int | None] = mapped_column(SmallInteger)


# ---------------------------------------------------------------------------
# §6.4 Источники, кейсы, нормативы
# ---------------------------------------------------------------------------


class Source(Base):
    __tablename__ = "source"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str | None] = mapped_column(Text)
    publisher: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    captured_at: Mapped[date] = mapped_column(Date, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text)
    ref_product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("product.id"))
    content_hash: Mapped[str | None] = mapped_column(Text)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "kind not in ('analogue', 'assumption') or rationale is not null", name="reasoned"
        ),
    )


class ProductCase(Base):
    __tablename__ = "product_case"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("product.id"), nullable=False)
    object_type_id: Mapped[int | None] = mapped_column(ForeignKey("object_type.id"))
    process_id: Mapped[int | None] = mapped_column(ForeignKey("process.id"))
    customer: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("source.id"))


class CalcNorm(Base):
    """Коэффициент без обоснования физически не вставляется: source_id NOT NULL → source.rationale."""

    __tablename__ = "calc_norm"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    solution_type_id: Mapped[int | None] = mapped_column(ForeignKey("solution_type.id"))
    key: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    unit: Mapped[str | None] = mapped_column(Text)
    source_id: Mapped[int] = mapped_column(ForeignKey("source.id"), nullable=False)
    editable: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    __table_args__ = (UniqueConstraint("solution_type_id", "key"),)


# ---------------------------------------------------------------------------
# §6.6 Пользователи, проекты, прогоны, очередь модерации
# ---------------------------------------------------------------------------


class AppUser(Base):
    __tablename__ = "app_user"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    login: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)  # argon2
    role: Mapped[str] = mapped_column(Text, nullable=False)  # guest | user | admin


class Project(Base):
    __tablename__ = "project"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    object_type_id: Mapped[int] = mapped_column(ForeignKey("object_type.id"), nullable=False)
    site: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)  # SiteProfile
    tasks: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)  # list[Task]
    overrides: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CalcRun(Base):
    __tablename__ = "calc_run"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project.id", ondelete="CASCADE"), nullable=False
    )
    catalog_version_id: Mapped[int] = mapped_column(ForeignKey("catalog_version.id"), nullable=False)
    engine_version: Mapped[str] = mapped_column(Text, nullable=False)
    request: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    response: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)  # включая trace[] и events[]
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AttrProposal(Base):
    """Всё входящее — импорт, парсер, ручная правка — проходит через одну очередь (ТЗ 3.3.5)."""

    __tablename__ = "attr_proposal"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("product.id"))
    key: Mapped[str] = mapped_column(Text, nullable=False)
    new_value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)  # AttrValue
    origin: Mapped[str] = mapped_column(Text, nullable=False)  # import | parser | manual
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_by: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RefreshRun(Base):
    __tablename__ = "refresh_run"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)  # sources_check | import
    status: Mapped[str] = mapped_column(Text, nullable=False)  # running | done | failed
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stats: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
