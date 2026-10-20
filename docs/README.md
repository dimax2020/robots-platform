# Документация проекта

Пакет по ТЗ на сопроводительную документацию. Язык русский. Чтобы собрать DOCX:

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r docs/tools/requirements.txt && playwright install chromium
python docs/tools/build_docx.py          # docs/dist/documentation.docx
```

## Состав

| Документ ТЗ | Файл |
|---|---|
| 1. Главная документация | `00-title.md`, `01…12-*.md`, приложения ниже |
| 2. README репозитория | [../README.md](../README.md) |
| 3. Описание API | [api.md](api.md) |
| 4. Архитектура и границы MVP | [02-architecture.md](02-architecture.md), [01-audience-scenarios-boundaries.md](01-audience-scenarios-boundaries.md) |
| 5. Реестр допущений | [appendix-A-assumptions.md](appendix-A-assumptions.md), `assumptions-register.xlsx` |
| 6. Журнал качества данных | [appendix-B-data-quality.md](appendix-B-data-quality.md) |
| 7. Статусы реализации | [appendix-V-status.md](appendix-V-status.md) |
| 8. Демо-доступы и сценарий проверки | [appendix-G-demo-and-check.md](appendix-G-demo-and-check.md) |
| 9. Презентация (раскадровка) | [presentation-outline.md](presentation-outline.md) |
| 10. Пример отчёта | Выгрузить из платформы в `docs/examples/` |
| Исправление допуска и экономики, этап 1 | [13-assessment-stage1.md](13-assessment-stage1.md) |
| Автоматический подбор по данным каталога | [14-catalog-assessment.md](14-catalog-assessment.md) |
| Выборочные синтетические дополнения DEV | [15-demo-synthetic.md](15-demo-synthetic.md) |
| Матрица соответствия | [appendix-Z-compliance.md](appendix-Z-compliance.md) |

Прочие приложения: [Д правила подбора](appendix-D-rules.md), [Е схема БД](appendix-E-schema.md), [Ж поля площадки](appendix-Zh-site-fields.md).

## Генераторы

| Скрипт | Что делает |
|---|---|
| `tools/gen_appendices.py` | Приложения А, Д, Ж и xlsx из работающей платформы |
| `tools/gen_schema.py` | Приложение Е из БД |
| `tools/screenshots.py` | Скриншоты в `img/` |
| `tools/build_docx.py` | Сборка DOCX |

- [Сквозной демонстрационный расчёт](16-demo-calculation.md) — количество, программа объекта, What-if и происхождение.

- [Расширение сравнимых демоальтернатив](17-demo-alternatives.md) — состав по процессам, параметры режимов и ограничения.

- [Согласованные демосценарии экономики](18-demo-economy-scenarios.md) — выгодные, пограничные и невыгодные альтернативы, итоги трёх объектов.

- [Подбор при неполных характеристиках](19-incomplete-selection.md) — условный допуск, значимые ограничения, происхождение допущений и обновление DEV.

- [Покрытие всех процессов трёх демообъектов](20-demo-process-coverage.md) — реалистичная синтетика, матрица 30 процессов и проверенные экономические альтернативы.

- [Аудит перехода от технического допуска к экономике](21-demo-economy-audit.md) — все 30 процессов, 62 подходящие альтернативы, 47 проверенных выборов и 15 ограничений моделей.

- [Инженерные модели оставшихся альтернатив](22-demo-engineering-models.md) — 62 из 62 доступны экономике, DEV-комплектность и сохранение прежних 47 расчётов.
