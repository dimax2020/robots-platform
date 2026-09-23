"""Схемы проектов и прогонов (§7.1)."""

from __future__ import annotations

from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from api.services.limits import check_site_and_tasks, violations_to_validation_error
from engine.models import CalcResponse, SiteProfile, Task


class ProjectCreate(BaseModel):
    """Создание: site/tasks подставляет роутер; диапазонам здесь проверять нечего (кроме непустого name у pydantic)."""

    name: str
    object_type_code: str
    industry_code: str | None = None  # колонки нет — принимаем, не сохраняем
    use_demo: bool = True


class ProjectPatch(BaseModel):
    name: str | None = None
    site: SiteProfile | None = None
    tasks: list[Task] | None = None
    overrides: dict[str, float] | None = None

    @model_validator(mode="after")
    def validate_field_limits(self) -> Self:
        violations = check_site_and_tasks(self.site, self.tasks)
        if violations:
            raise violations_to_validation_error(self.__class__.__name__, violations)
        return self


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
