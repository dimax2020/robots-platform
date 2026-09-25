from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SourceRow(Base):
    __tablename__ = "source"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    publisher: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str | None] = mapped_column(Text)
    parser_code: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)


class AttributeDefRow(Base):
    __tablename__ = "attribute_def"
    key: Mapped[str] = mapped_column(Text, primary_key=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[str | None] = mapped_column(Text)
    usage: Mapped[str] = mapped_column(Text, nullable=False, default="pending")


class ProductRow(Base):
    __tablename__ = "product"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(Text)
    availability: Mapped[str | None] = mapped_column(Text)
    trl: Mapped[int | None] = mapped_column(Integer)
    price_rub: Mapped[float | None] = mapped_column(Numeric)
    image_url: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    raw_catalog: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    attrs: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    column_sources: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProductOriginRow(Base):
    __tablename__ = "product_origin"
    platform: Mapped[str] = mapped_column(Text, primary_key=True)
    external_id: Mapped[str] = mapped_column(Text, primary_key=True)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("product.id"), nullable=False)


class IndustryRow(Base):
    __tablename__ = "industry"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)


class ObjectTypeRow(Base):
    __tablename__ = "object_type"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)


class ProcessRow(Base):
    __tablename__ = "process"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)


class ObjectIndustryRow(Base):
    __tablename__ = "object_industry"
    object_type_id: Mapped[int] = mapped_column(ForeignKey("object_type.id"), primary_key=True)
    industry_id: Mapped[int] = mapped_column(ForeignKey("industry.id"), primary_key=True)


class ObjectProcessRow(Base):
    __tablename__ = "object_process"
    object_type_id: Mapped[int] = mapped_column(ForeignKey("object_type.id"), primary_key=True)
    process_id: Mapped[int] = mapped_column(ForeignKey("process.id"), primary_key=True)


class ProductProcessRow(Base):
    __tablename__ = "product_process"
    product_id: Mapped[UUID] = mapped_column(ForeignKey("product.id"), primary_key=True)
    process_id: Mapped[int] = mapped_column(ForeignKey("process.id"), primary_key=True)


class ProcessFilterRow(Base):
    __tablename__ = "process_filter"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    process_id: Mapped[int] = mapped_column(ForeignKey("process.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    object_keys: Mapped[list] = mapped_column(JSONB, nullable=False)
    robot_keys: Mapped[list] = mapped_column(JSONB, nullable=False)
    op: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False)


class ProjectRow(Base):
    __tablename__ = "project"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    object_type_id: Mapped[int] = mapped_column(ForeignKey("object_type.id"), nullable=False)
    site: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class ProjectProcessRow(Base):
    __tablename__ = "project_process"
    project_id: Mapped[UUID] = mapped_column(ForeignKey("project.id"), primary_key=True)
    process_id: Mapped[int] = mapped_column(ForeignKey("process.id"), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ParserSettingRow(Base):
    __tablename__ = "parser_setting"
    code: Mapped[str] = mapped_column(Text, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    hour: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    last_enqueued_on: Mapped[date | None] = mapped_column(Date)


class JobRow(Base):
    __tablename__ = "job"
    __table_args__ = (
        Index(
            "uq_job_live",
            "kind",
            "parser_code",
            unique=True,
            postgresql_where=text("status IN ('pending', 'running')"),
        ),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    parser_code: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    counters: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
