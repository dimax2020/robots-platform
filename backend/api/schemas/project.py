"""Схемы проектов и прогонов (§7.1)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from engine.models import CalcResponse, SiteProfile, Task


class ProjectCreate(BaseModel):
    name: str
    object_type_code: str
    industry_code: str | None = None  # колонки нет — принимаем, не сохраняем
    use_demo: bool = True


class ProjectPatch(BaseModel):
    name: str | None = None
    site: SiteProfile | None = None
    tasks: list[Task] | None = None
    overrides: dict[str, float] | None = None


class ProjectOut(BaseModel):
    id: UUID
    owner_id: UUID
    name: str
    object_type_code: str
    site: SiteProfile
    tasks: list[Task] = Field(default_factory=list)
    overrides: dict[str, float] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SiteProfileRefOut(BaseModel):
    object_type_code: str
    name: str | None = None
    site: SiteProfile
    tasks: list[Task] = Field(default_factory=list)


class CalculateOut(CalcResponse):
    """CalcResponse плюс id сохранённого прогона."""

    run_id: UUID
