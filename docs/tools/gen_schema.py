"""Приложение Е (схема БД) из работающей БД: python docs/tools/gen_schema.py

Нужен запущенный docker compose (сервис db). Пишет docs/appendix-E-schema.md.
"""
import subprocess
from collections import OrderedDict
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "appendix-E-schema.md"
ROOT = Path(__file__).resolve().parents[2]

PURPOSE = {
    "alembic_version": "Текущая ревизия миграций",
    "app_user": "Пользователи и роли",
    "attribute_def": "Справочник характеристик роботов: подпись, единица, группа",
    "economy_norm": "Нормативы экономики (переопределяют значения по умолчанию из кода)",
    "economy_norm_log": "Журнал изменений нормативов",
    "economy_norm_override": "Нормативы для конкретного типа решения",
    "industry": "Отрасли",
    "job": "Очередь заданий: импорт и парсеры",
    "match_setting": "Общие фильтры подбора (готовность)",
    "object_field": "Поля площадки объекта",
    "object_industry": "Связь объект — отрасль",
    "object_input_binding": "Привязка входов формул процесса к полям площадки",
    "object_process": "Процессы объекта",
    "object_type": "Типы объектов; `in_match` разрешает выбор в мастере проекта",
    "parser_setting": "Расписание парсеров",
    "process": "Процессы: формула количества, ключ ранжирования, шаблон схемы",
    "process_filter": "Правила подбора процесса",
    "product": "Карточки роботов; `attrs` значения, `column_sources` источники, `raw_catalog` исходная строка",
    "product_origin": "Внешний идентификатор карточки (платформа, ID)",
    "product_process": "Роботы процесса",
    "project": "Проекты: площадка, ручные значения экономики, схема, признаки демо",
    "project_process": "Включённые процессы проекта",
    "site_field": "Справочник полей площадки: подпись, единица, границы",
    "solution_type": "Типы решений",
    "solution_type_rule": "Правила автоназначения типа при импорте",
    "source": "Реестр источников значений",
}


def psql(sql: str) -> list[list[str]]:
    out = subprocess.check_output(
        ["docker", "compose", "exec", "-T", "db", "psql", "-U", "robots", "-d", "platform", "-At", "-F", "\t", "-c", sql],
        cwd=ROOT, text=True)
    return [line.split("\t") for line in out.splitlines() if line]


def main() -> None:
    cols = psql(
        "select table_name, column_name, "
        "case when data_type='USER-DEFINED' then udt_name else data_type end, is_nullable, coalesce(column_default,'') "
        "from information_schema.columns where table_schema='public' order by table_name, ordinal_position")
    pks = {(t, c) for t, c, k, *_ in psql(
        "select tc.table_name, kcu.column_name, tc.constraint_type from information_schema.table_constraints tc "
        "join information_schema.key_column_usage kcu on tc.constraint_name=kcu.constraint_name "
        "where tc.table_schema='public' and tc.constraint_type='PRIMARY KEY'")}
    fks = {(t, c): rt for t, c, rt in psql(
        "select tc.table_name, kcu.column_name, ccu.table_name from information_schema.table_constraints tc "
        "join information_schema.key_column_usage kcu on tc.constraint_name=kcu.constraint_name "
        "join information_schema.constraint_column_usage ccu on ccu.constraint_name=tc.constraint_name "
        "where tc.table_schema='public' and tc.constraint_type='FOREIGN KEY'")}
    tables: "OrderedDict[str, list]" = OrderedDict()
    for t, c, ty, nul, dflt in cols:
        tables.setdefault(t, []).append((c, ty, nul, dflt))
    lines = [
        "# Приложение Е. Схема базы данных",
        "",
        f"PostgreSQL 16, база `platform`, {len(tables)} таблиц, миграции Alembic до `0014_match_settings`. "
        "Файл сформирован скриптом `docs/tools/gen_schema.py` из работающей БД. "
        "PK — первичный ключ, FK — внешний ключ, `?` — допускает NULL.",
        "",
    ]
    for t, rows in tables.items():
        lines += [f"## `{t}`", "", PURPOSE.get(t, ""), "", "| Поле | Тип | Ключ |", "|---|---|---|"]
        for c, ty, nul, dflt in rows:
            key = "PK" if (t, c) in pks else (f"FK → `{fks[(t, c)]}`" if (t, c) in fks else "")
            if (t, c) in pks and (t, c) in fks:
                key = f"PK, FK → `{fks[(t, c)]}`"
            lines.append(f"| `{c}`{'?' if nul == 'YES' else ''} | {ty} | {key} |")
        lines.append("")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"{OUT}: {len(tables)} таблиц")


if __name__ == "__main__":
    main()
