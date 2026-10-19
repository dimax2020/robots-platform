"""Проекция опубликованного каталога для оценки. Ничего не записывает в карточки.

Числа нормализуются существующим нормализатором. Классификация использует явные
формулировки назначения/исполнения, а не имя модели, цену или одну связь процесса.
Assessment — необязательные дополнения; конфликт с каталогом остаётся видимым.
"""
from copy import deepcopy
from dataclasses import dataclass, field
import re

from app.domain.assessment import KINDS, CONTROLS, checked, reason
from app.domain.specs import NUMERIC_UNITS, definitions, normalize_attrs


CAPABILITY_TERMS = {
    'warehouse_inventory': r'инвентаризац|инвентаризатор|inventory',
    'floor_cleaning': r'поломоеч|уборк\w* пол|мыть\w* пол|floor.clean',
    'pallet_transport': r'перевоз\w* паллет|транспортиров\w* паллет|перемещ\w* паллет',
    'rack_placement': r'штабелер|штабелёр|размещ\w* на стеллаж|уклад\w* на стеллаж',
    'cart_towing': r'буксиров|тягач|перемещ\w* тележ',
    'pallet_storage': r'систем\w* хранен|автоматическ\w* хранен|хранен\w* и доставк',
    'order_picking': r'комплектов|комплектаци|отбор\w* заказ|товар к человеку',
    'medicine_delivery': r'доставк\w*[^.\n]{0,60}(?:медикамент|лекарств|медицин)|снабжен\w*[^.\n]{0,40}медикамент',
    'biomaterial_delivery': r'доставк\w*[^.\n]{0,60}(?:биоматериал|анализ|образц)|снабжен\w*[^.\n]{0,40}биоматериал',
    'tote_delivery': r'внутриобъектн\w* доставк|перевоз\w* (?:контейнер|ящик)|доставк\w* (?:груз|предмет)',
    'baggage_transport': r'багаж', 'parcel_sorting': r'сортиров\w* (?:посыл|отправлен)',
    'packing': r'упаков', 'palletizing': r'паллетиз|паллетир|уклад\w*[^.\n]{0,25}паллет',
    'passenger_service': r'информирован|сопровожд\w* посетител|сервисн\w* робот',
    'perimeter_security': r'охран|патрулир', 'territory_inspection': r'инспекц|мониторинг территор',
    'roof_inspection': r'инспекц\w* кровл|обследован\w* крыш',
    'ward_service': r'обслуживан\w* палат|помощ\w* пациент',
}


@dataclass
class CatalogAssessment:
    facts: dict
    values: dict
    provenance: dict
    issues: dict = field(default_factory=dict)
    reasons: list = field(default_factory=list)
    site_conditions: dict = field(default_factory=dict)
    demo_synthetic: list = field(default_factory=list)


def resolve_catalog(row, metadata=None, *, process_code='', process_name='', sources=None, site=None, allow_demo=False):
    """Одно представление для runtime и административного предпросмотра."""
    raw_attrs = {k: deepcopy(v) for k, v in (row.attrs or {}).items() if isinstance(v, dict)}
    labels = {k: str(v.get('label') or definitions().get(k, {}).get('label', k)) for k, v in raw_attrs.items()}
    units = {key: raw.get('unit') or NUMERIC_UNITS.get(key) for key, raw in raw_attrs.items()}
    attrs, normalization = normalize_attrs(raw_attrs, labels, units)
    facts, errors = checked(metadata, product=True)
    facts = dict(facts)
    # Исторические служебные флаги не участвуют в разрешении фактов.
    facts.pop('reviewed', None)
    facts.pop('evidence', None)
    provenance, values, issues = {}, {}, {}
    for key, value in facts.items():
        if key != 'version':
            provenance['fact.' + key] = {'value': deepcopy(value), 'origin': 'assessment_supplement',
                                        'evidence': (metadata or {}).get('evidence', [])}
    for key, raw in attrs.items():
        if not isinstance(raw, dict):
            continue
        source_id = raw.get('source_id')
        provenance[key] = {**deepcopy(raw), 'source': (sources or {}).get(source_id)}
        if raw.get('status') == 'known' and not raw.get('conflict') and raw.get('value') not in (None, ''):
            values[key] = raw['value']
        if raw.get('conflict') or raw.get('status') == 'conflict':
            issues[key] = 'Конфликт опубликованных значений'
        source = (sources or {}).get(source_id) or {}
        if source.get('kind') in {'assumption', 'analogue'}:
            values.pop(key, None)
            issues[key] = 'Допущение или аналог не является характеристикой опубликованного изделия'
    for issue in normalization:
        key = issue.get('canonical_key', issue.get('key'))
        if issue['reason'] not in {'repaired_legacy_conversion'}:
            issues[key] = 'Неоднозначное значение или единицы: ' + issue['reason']
            values.pop(key, None)
    # Уже нормализованный scalar может иметь явно другую единицу: не теряем её.
    for key, raw in raw_attrs.items():
        if not isinstance(raw, dict) or raw.get('status') != 'known':
            continue
        if raw.get('conflict') or raw.get('status') == 'conflict':
            values.pop(key, None); issues[key] = 'Конфликт опубликованных значений'
        if key in NUMERIC_UNITS and key in values:
            from app.domain.specs import normalize_value
            normalized = normalize_value(key, raw['value'], labels.get(key, key), units.get(key))
            if normalized is None:
                values.pop(key, None); issues[key] = 'Нельзя однозначно привести характеристику к каноническим единицам'
            else:
                values[key] = normalized[1]
                provenance[key]['normalized_value'] = normalized[1]
                provenance[key]['normalized_unit'] = normalized[2]
    # Граница/условие опубликованного режима не становится гарантированной величиной.
    for key, raw in attrs.items():
        if key not in values:
            continue
        conditions = raw.get('conditions')
        if conditions and (not isinstance(conditions, dict) or any((site or {}).get(k) != v for k, v in conditions.items())):
            values.pop(key, None)
            issues[key] = 'Не установлены условия применимости характеристики'
        original = raw.get('normalization_original') or raw
        bound_text = str(original.get('value', '')) + ' ' + str(raw.get('quote') or '')
        if key in {'work_time_h', 'work_time_loaded_h', 'work_time_empty_h', 'speed_loaded_ms', 'speed_empty_ms', 'throughput', 'proizvoditelnost'} and (raw.get('normalization_rule') == 'upper_bound' or re.search(r'\bдо\s+\d|\bот\s+\d|up to\s+\d|\d\s*[-–—]\s*\d|при\s+(?:\d|нагрузке|скорости|температуре)', bound_text, re.I)):
            values.pop(key, None)
            issues[key] = 'Указана граница, диапазон или отдельный режим, а не однозначное рабочее значение'
    if row.price_rub is not None:
        values['price_rub'] = float(row.price_rub)
        source_id = (row.column_sources or {}).get('price_rub')
        provenance['price_rub'] = {'value': values['price_rub'], 'source_id': source_id, 'source': (sources or {}).get(source_id)}
    if row.trl is not None:
        values['trl'] = row.trl

    def claim(key, value, evidence_keys):
        if value in (None, '', []):
            return
        old = facts.get(key)
        if old is not None and old != value:
            # Не выбираем между каталогом и старым служебным документом молча.
            facts.pop(key, None)
            errors.append(reason('catalog_fact_conflict', f'Расходятся каталог и дополнение assessment: {key}', field=key,
                                 stage='economy' if key in {'configuration_complete', 'price_complete'} else 'sizing' if key == 'execution_class' else 'functional'))
        else:
            facts[key] = value
        provenance['fact.' + key] = {'value': value, 'derived_from': evidence_keys,
                                    'assessment_value': old}

    # Явные структурированные поля имеют приоритет перед извлечением из текста.
    structured = set()
    for key in ('solution_kind', 'control_mode', 'execution_class', 'environments', 'capabilities', 'equipment', 'configuration_complete', 'price_complete'):
        value = values.get(key)
        if value is None:
            continue
        if key in {'environments', 'capabilities', 'equipment'} and isinstance(value, str):
            value = [s.strip() for s in value.split(',') if s.strip()]
        if key in {'configuration_complete', 'price_complete'} and isinstance(value, str):
            value = {'true': True, 'да': True, 'false': False, 'нет': False}.get(value.casefold())
        valid = ((key not in {'solution_kind', 'control_mode'} or isinstance(value, str) and value in (KINDS if key == 'solution_kind' else CONTROLS))
                 and (key != 'execution_class' or isinstance(value, str) and bool(value.strip()))
                 and (key not in {'configuration_complete', 'price_complete'} or isinstance(value, bool))
                 and (key not in {'environments', 'capabilities', 'equipment'} or isinstance(value, list) and all(isinstance(v, str) for v in value)))
        if valid:
            claim(key, value, [key]); structured.add(key)

    texts = {key: str(values[key]).casefold().replace('ё', 'е') for key in
             ('purpose', 'subtype', 'scenario', 'enclosure', 'navigation', 'infrastructure_req') if key in values}
    summary_source = (sources or {}).get((row.column_sources or {}).get('summary')) or {}
    if row.summary and summary_source.get('kind') not in {'assumption', 'analogue'}:
        texts['summary'] = row.summary.casefold().replace('ё', 'е')
        provenance['summary'] = {'value': row.summary, 'source_id': (row.column_sources or {}).get('summary'), 'source': summary_source}
    purpose = ' '.join(texts.get(k, '') for k in ('purpose', 'subtype', 'summary'))
    def derive(key, value, keys):
        if key not in structured:
            claim(key, value, keys)

    kind = None
    if re.search(r'мест\w* для оператора|сидень\w* (?:для )?оператора|постоянн\w* оператор', purpose):
        kind = 'operator_equipment'
    elif re.search(r'^\s*(?:программное обеспечение|систем\w* управления (?:робот|парк))', purpose):
        kind = 'software'
    elif re.search(r'^\s*(?:серия|линейка|семейство)\b', purpose):
        kind = 'family'
    elif re.search(r'систем\w* (?:кубическ\w* )?хранения|автоматическ\w* систем\w* хранения', purpose):
        kind = 'system'
    elif re.search(r'\bробот|\brobots?\b', purpose):
        kind = 'robot'
    # Размеченные семейства/компоненты не превращаем в роботов из-за упоминания роботов в описании.
    if facts.get('solution_kind') not in {'family', 'component', 'software'}:
        derive('solution_kind', kind, ['purpose', 'subtype', 'summary'])
    control_text = purpose + ' ' + texts.get('navigation', '')
    operator = re.search(r'не имеет собственного самоход|перемещается[^.]{0,35}ручн|сидень\w* (?:для )?оператора|постоянн\w* оператор', control_text)
    autonomous = re.search(r'автономн\w* (?:мобильн|робот|движен)|полностью автоматическ\w*|автономно\s+(?:передвига|преодоле|выполня)|без участия (?:человека|оператора)', control_text)
    if operator:
        derive('control_mode', 'operator', ['purpose', 'summary', 'navigation'])
    elif autonomous and not re.search(r'не\s+(?:является\s+)?автономн|не\s+полностью автоматическ', control_text):
        derive('control_mode', 'autonomous', ['purpose', 'summary', 'navigation'])
    env_text = texts.get('enclosure', '') or purpose
    environments = []
    if re.search(r'\bindoor\b|внутри помещен|в помещени', env_text): environments.append('indoor')
    if re.search(r'\boutdoor\b|открыт\w* (?:воздух|территор)|вне помещен', env_text): environments.append('outdoor')
    if re.search(r'не (?:предназначен\w* )?для (?:работы )?в помещен|не (?:поддерживает )?indoor', env_text):
        environments = [e for e in environments if e != 'indoor']
    derive('environments', environments, ['enclosure'] if texts.get('enclosure') else ['purpose', 'summary'])
    pattern = CAPABILITY_TERMS.get(process_code)
    # Для остальных процессов используем явное название операции в назначении, не имя изделия.
    if not pattern and process_name:
        pattern = re.escape(process_name.casefold().replace('ё', 'е'))
    if pattern:
        negative_pattern = r'(?:не предназначен\w*(?:\s+для)?|не выполняет|не поддерживает)\s+(?:' + pattern + ')'
        negative = [key for key, text in texts.items() if key in {'purpose', 'scenario', 'subtype', 'summary'} and re.search(negative_pattern, text)]
        positive = [key for key, text in texts.items() if key in {'purpose', 'scenario', 'subtype', 'summary'}
                    and re.search(pattern, text) and not re.search(negative_pattern, text)]
        if negative:
            conflicts = bool(positive or process_code in facts.get('capabilities', []))
            facts['capabilities'] = [c for c in facts.get('capabilities', []) if c != process_code]
            errors.append(reason('catalog_fact_conflict' if conflicts else 'capability_incompatible',
                                 'Противоречивые сведения о выполнении операции' if conflicts else 'В опубликованном назначении явно исключено выполнение операции',
                                 field=process_code, stage='functional', severity='unknown' if conflicts else 'fail'))
        elif positive:
            caps = list(facts.get('capabilities') or [])
            if process_code not in caps: caps.append(process_code)
            if 'capabilities' not in structured:
                # Перечень возможностей не является перечнем запретов: отсутствие
                # операции в дополнении не опровергает опубликованное назначение.
                facts['capabilities'] = caps
                provenance['fact.capabilities'] = {'value': caps, 'derived_from': positive}
    if 'execution_class' not in facts and process_code in {'pallet_transport', 'cart_towing', 'tote_delivery', 'baggage_transport', 'medicine_delivery', 'biomaterial_delivery'} and facts.get('control_mode') == 'autonomous' and re.search(r'мобильн|самоход', purpose):
        derive('execution_class', 'mobile_transport', ['purpose', 'summary'])
    site_conditions = {}
    infrastructure = texts.get('infrastructure_req', '')
    if re.search(r'QR.маркиров|требуется QR', infrastructure, re.I) and not re.search(r'без QR|опциональн[^.;]{0,30}QR', infrastructure, re.I):
        site_conditions['qr_marking_ready'] = 'Необходима QR-маркировка ячеек и паллетомест'
    if operator and re.search(r'рохл|погрузчик|тягач', purpose + ' ' + infrastructure):
        site_conditions['towing_available'] = 'Необходима предусмотренная изготовителем схема перемещения комплекса с тягачом/оператором'
    if re.search(r'(?:требуется|необходим\w*|обязательн\w*)[^.;]{0,35}\bWMS\b', infrastructure, re.I):
        site_conditions['has_wms'] = 'Для применения решения требуется WMS'
    catalog = CatalogAssessment(facts, values, provenance, issues, errors, site_conditions)
    from app.domain.demo_synthetic import apply_supplements
    catalog.demo_synthetic = apply_supplements(row, catalog, process_code=process_code) if allow_demo else []
    return catalog
