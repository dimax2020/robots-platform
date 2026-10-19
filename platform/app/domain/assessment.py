"""Проверяемые факты изделия и требования операции. Назначение процесса не является допуском."""
from __future__ import annotations

from dataclasses import dataclass, asdict
import math
from typing import Any

KINDS = {'robot', 'cell', 'system', 'family', 'component', 'software', 'operator_equipment'}
CONTROLS = {'autonomous', 'teleoperated', 'operator'}


@dataclass(frozen=True)
class Reason:
    code: str
    message: str
    severity: str = 'unknown'
    field: str | None = None
    stage: str = 'technical'

    def as_dict(self) -> dict:
        return asdict(self)


def reason(code: str, message: str, *, severity='unknown', field=None, stage='technical') -> Reason:
    return Reason(code, message, severity, field, stage)


def validate_metadata(data: Any, *, product: bool) -> dict:
    """Строгий контракт записи администратором; чтение повреждённого JSON безопасно деградирует."""
    if not isinstance(data, dict):
        raise ValueError('Нужен объект метаданных проверки')
    common = {'version', 'reviewed', 'evidence'} | (set() if product else {'requirements_reviewed'})
    allowed = common | ({'solution_kind', 'control_mode', 'execution_class', 'environments', 'capabilities',
                         'equipment', 'configuration_complete', 'price_complete'} if product else
                        {'allowed_kinds', 'allowed_controls', 'environments', 'required_equipment',
                         'critical_robot_keys', 'critical_site_keys', 'required_checks', 'sizing'})
    if set(data) - allowed:
        raise ValueError('Неизвестные поля профиля: ' + ', '.join(sorted(set(data) - allowed)))
    if type(data.get('version', 1)) is not int or data.get('version', 1) != 1:
        raise ValueError('Неподдерживаемая версия профиля')
    for k in ('reviewed', 'requirements_reviewed', 'configuration_complete', 'price_complete'):
        if k in data and not isinstance(data[k], bool):
            raise ValueError(f'{k}: требуется логическое значение')
    for k in ('evidence', 'environments', 'capabilities', 'equipment', 'allowed_kinds', 'allowed_controls',
              'required_equipment', 'critical_robot_keys', 'critical_site_keys', 'required_checks'):
        if k in data and (not isinstance(data[k], list) or any(not isinstance(v, str) or not v.strip() for v in data[k])):
            raise ValueError(f'{k}: требуется список непустых строк')
    for key, choices in [('solution_kind', KINDS), ('control_mode', CONTROLS)]:
        if key in data and (not isinstance(data[key], str) or data[key] not in choices):
            raise ValueError(f'{key}: неизвестное значение')
    for key, choices in [('allowed_kinds', KINDS), ('allowed_controls', CONTROLS)]:
        if key in data and not set(data[key]) <= choices:
            raise ValueError(f'{key}: неизвестное значение')
    if 'execution_class' in data and (not isinstance(data['execution_class'], str) or not data['execution_class'].strip()):
        raise ValueError('execution_class: требуется непустая строка')
    if 'sizing' in data and not isinstance(data['sizing'], dict):
        raise ValueError('sizing: требуется объект')
    if (data.get('reviewed') or data.get('requirements_reviewed')) and not data.get('evidence'):
        raise ValueError('Для подтверждённых метаданных требуется evidence')
    return data


def checked(data: Any, *, product: bool) -> tuple[dict, list[Reason]]:
    try:
        return validate_metadata({} if data is None else data, product=product), []
    except (ValueError, TypeError) as ex:
        return {}, [reason('configuration_error', str(ex), stage='functional')]


def functional_reasons(facts: dict | None, profile: dict | None, process_code: str) -> list[Reason]:
    f, errors = checked(facts, product=True)
    p, more = checked(profile, product=False)
    out = errors + more
    # reviewed — историческая редакционная отметка, а не разрешение использовать каталог.
    kind = f.get('solution_kind')
    if not kind:
        out.append(reason('solution_kind_missing', 'В каталоге не определён вид решения', stage='functional'))
    if kind in {'software', 'component', 'operator_equipment'} and kind not in p.get('allowed_kinds', []):
        out.append(reason('incomplete_solution', 'Это ПО, компонент или операторское оборудование, а не комплектное роботизированное решение', severity='fail', stage='functional'))
    elif kind == 'family':
        out.append(reason('configuration_missing', 'Сначала выберите конкретную конфигурацию семейства', stage='functional'))
    control = f.get('control_mode')
    if p.get('allowed_controls') and not control:
        out.append(reason('control_mode_missing', 'Способ управления не подтверждён', stage='functional'))
    if p.get('allowed_kinds') and kind and kind != 'family' and kind not in p['allowed_kinds']:
        out.append(reason('solution_kind_incompatible', 'Вид решения не поддерживает этот способ выполнения процесса', severity='fail', stage='functional'))
    if p.get('allowed_controls') and control and control not in p['allowed_controls']:
        out.append(reason('control_mode_incompatible', 'Способ управления несовместим с требованиями процесса', severity='fail', stage='functional'))
    environments = set(f.get('environments') or [])
    if p.get('environments') and not environments:
        out.append(reason('environment_missing', 'Среда эксплуатации не подтверждена', stage='functional'))
    elif p.get('environments') and not environments.intersection(p['environments']):
        out.append(reason('environment_incompatible', 'Подтверждённая среда эксплуатации несовместима с процессом', severity='fail', stage='functional'))
    if process_code not in f.get('capabilities', []):
        out.append(reason('capability_unconfirmed', 'Возможность выполнения этой операции не подтверждена', field=process_code, stage='functional'))
    for item in p.get('required_equipment', []):
        if item not in f.get('equipment', []):
            out.append(reason('equipment_missing', f'Не подтверждена необходимая оснастка: {item}', field=item, stage='functional'))
    return out


def valid_count(value: Any) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        number = float(value)
    except OverflowError:
        return False
    return math.isfinite(number) and number >= 0 and number.is_integer()


def economy_eligible(hit: dict) -> bool:
    # Отсутствие новых полей у старого ответа не даёт разрешение на расчёт.
    return hit.get('verdict') == 'pass' and hit.get('economic_ready') is True and valid_count(hit.get('count')) and hit['count'] > 0


def select_hit(group: dict, chosen_id: str | None = None, *, explicit=False) -> tuple[dict | None, list[dict]]:
    hits = group.get('hits') or []
    target = chosen_id if explicit else (chosen_id or group.get('best_product_id'))
    hit = next((h for h in hits if h.get('product_id') == target), None)
    if hit and economy_eligible(hit):
        return hit, []
    if explicit or chosen_id:
        return None, [{'code': 'selection_invalid', 'message': 'Сохранённый или переданный выбор не допущен к экономике',
                       'product_id': target, 'reasons': (hit or {}).get('reasons', []) + (hit or {}).get('economic_reasons', [])}]
    return None, [{'code': 'no_eligible_candidate', 'message': 'Нет подтверждённого решения с известным количеством и ценой'}]
