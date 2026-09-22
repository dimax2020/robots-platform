"""Подготовка входа расчёта: суточные объёмы в часовые, пустые поля площадки из нормативов (§6.1 E3_SPEC).

Датасет организатора даёт почти всё в сутках, а формулы считают в часах. Перевод — это
преобразование, а не данные, поэтому каждый пересчёт попадает в trace (ТЗ 3.5.8).

Вызывается один раз в pipeline до match: жёсткие правила и формулы количества обязаны
видеть один и тот же подготовленный вход.
"""

from __future__ import annotations

from .models import CalcRequest, SiteProfile, Task, TraceStep
from .resolve import Resolver

_SITE_FIELDS = ("shift_hours", "shifts_per_day", "days_year", "clean_area_m2")


def prepare(req: CalcRequest, resolver: Resolver) -> tuple[CalcRequest, list[TraceStep]]:
    site, trace = _prepare_site(req.site, resolver)
    tasks: list[Task] = []
    for task in req.tasks:
        prepared, t = _prepare_task(task, site, resolver)
        tasks.append(prepared)
        trace += t
    return req.model_copy(update={"site": site, "tasks": tasks}), trace


def _prepare_site(site: SiteProfile, resolver: Resolver) -> tuple[SiteProfile, list[TraceStep]]:
    """Пустые поля площадки — через лестницу достоверности (§3.4 E3_SPEC)."""
    trace: list[TraceStep] = []
    update: dict[str, float | int] = {}

    for field in _SITE_FIELDS:
        current = getattr(site, field, None)
        if field == "clean_area_m2" and current is None:
            current = _clean_area_from_share(site, resolver, trace)
            if current is not None:
                update[field] = current
                continue
        resolved = resolver.site(field, current, site.object_type_code)
        if resolved is None:
            continue
        if current is None:
            update[field] = int(resolved.value) if field in ("shifts_per_day", "days_year") else resolved.value
            trace.append(
                TraceStep(
                    step="prepare",
                    value=resolved.value,
                    unit=resolved.unit,
                    source=resolved.source_label,
                    message=resolved.message,
                )
            )

    return (site.model_copy(update=update) if update else site), trace


def _clean_area_from_share(site: SiteProfile, resolver: Resolver, trace: list[TraceStep]) -> float | None:
    """Убираемая площадь как доля от общей — когда в профиле объекта её нет."""
    if site.area_m2 is None:
        return None
    share = resolver.norm(f"default.site.clean_area_share.{site.object_type_code}")
    key = f"default.site.clean_area_share.{site.object_type_code}"
    if share is None:
        share = resolver.norm("default.site.clean_area_share")
        key = "default.site.clean_area_share"
    if share is None:
        return None

    value = site.area_m2 * share
    trace.append(
        TraceStep(
            step="prepare",
            formula=f"{site.area_m2:g} * {share:g} = {value:g}",
            value=value,
            unit="м²",
            source=f"[D] допущение: {key} = {share:g}",
            message=(
                f"Убираемая площадь в профиле не задана, взята как {share:g} от общей площади "
                f"{site.area_m2:g} м² — {value:g} м²."
            ),
        )
    )
    return value


def _prepare_task(task: Task, site: SiteProfile, resolver: Resolver) -> tuple[Task, list[TraceStep]]:
    trace: list[TraceStep] = []
    update: dict[str, float] = {}

    for field in ("t_load_s", "t_unload_s"):
        if getattr(task, field) == 0:
            value = resolver.norm(f"default.{field}")
            if value is not None:
                update[field] = value
                trace.append(
                    TraceStep(
                        step="prepare",
                        value=value,
                        unit="с",
                        source=f"[D] допущение: default.{field} = {value:g}",
                        message=(
                            f"Время {'погрузки' if field == 't_load_s' else 'разгрузки'} для задачи "
                            f"«{task.name or task.process_code}» не задано, принято {value:g} с."
                        ),
                    )
                )

    if task.flow_per_hour is None and task.flow_per_day is not None:
        window = site.shift_hours * site.shifts_per_day
        peak = task.peak_factor if task.peak_factor is not None else site.peak_factor
        if window > 0:
            value = task.flow_per_day / window * peak
            update["flow_per_hour"] = value
            trace.append(
                TraceStep(
                    step="prepare",
                    formula=f"{task.flow_per_day:g} / ({site.shift_hours:g} * {site.shifts_per_day}) * {peak:g} = {value:.1f}",
                    value=value,
                    unit="операций/ч",
                    source="[B] профиль площадки из датасета",
                    message=(
                        f"Задача «{task.name or task.process_code}»: суточный объём {task.flow_per_day:g} "
                        f"переведён в часовой поток {value:.1f} по рабочему окну "
                        f"{site.shift_hours:g} ч × {site.shifts_per_day} смен с пиковым коэффициентом {peak:g}."
                    ),
                )
            )

    return (task.model_copy(update=update) if update else task), trace
