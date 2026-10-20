"""READ ONLY-аудит всех процессов и альтернатив трёх демо.

PYTHONPATH=. python tools/check_demo_coverage.py --verify-economy
python tools/check_demo_coverage.py --http-base http://localhost:8080/platform/api/v1 --verify-economy

Статусы, количества и результаты экономики вычисляет рабочий движок.
HTTP-подбор может обновлять штатные счётчики показов, но не исходные данные.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
from urllib.request import Request, urlopen

PROJECTS = ('demo-warehouse', 'demo-hospital', 'demo-airport')


def blocker_category(problem, operation_fields=()):
    """Различаем отсутствие данных, коммерческие ограничения и отсутствие модели."""
    code = problem['code']
    if code in {'sizing_model_missing', 'sizing_model_unknown', 'sizing_incompatible', 'sizing_unit_incompatible'}:
        return 'model'
    if code in {'configuration_missing', 'equipment_missing', 'incomplete_solution'}:
        return 'configuration'
    if code in {'price_missing', 'price_scope_unconfirmed'}:
        return 'price'
    if code in {'sizing_attribute_missing', 'working_speed_exceeds_limit'}:
        return 'robot_characteristics'
    if code in {'sizing_input_missing', 'sizing_input_invalid'}:
        if problem.get('field') in {'work_time_h', 'charge_time_h', 'payload_kg'}:
            return 'robot_characteristics'
        return 'operation_parameters' if problem.get('field') in operation_fields else 'quantity_inputs'
    if code == 'selection_invalid':
        return 'selection'
    return 'other'


def verify_selection(report, group, hit):
    item = next((r for r in report['fleet'] if r['process_code'] == group['process_code']), {})
    checks = {
        'selected_id': item.get('product_id') == hit['product_id'],
        'calculated_count': item.get('count_used') == hit['count'],
        'included': item.get('included') is True,
        'assumptions_preserved': item.get('assumptions') == hit['assumptions'],
        'sizing_preserved': item.get('sizing') == hit['sizing'],
        'complete': report['complete'] is True,
        'three_scenarios': len(report['scenarios']) == 3,
    }
    return {'verified': all(checks.values()), 'checks': checks, 'blockers': report['blockers']}


def audit_match(slug, matched, calculate=None):
    defaults = {g['process_code']: g['demo_best_product_id'] if g.get('calculation_mode') == 'demo' else g.get('best_product_id')
                for g in matched['groups']}
    defaults = {code: pid for code, pid in defaults.items() if pid}
    program = (matched.get('demo_plan') or {}).get('processes')
    if program is not None:
        program = set(program) | {code for code, p in matched['demo_plan'].get('technical_processes', {}).items() if p.get('optional')}
    output = []
    for group in matched['groups']:
        counts = Counter()
        eligible = []
        technical = []
        blockers = Counter()
        for hit in group['hits']:
            bucket = 'conditional_pass' if hit['verdict'] == 'pass' and hit.get('applicability') == 'conditional' else hit['verdict']
            counts[bucket] += 1
            if hit['verdict'] != 'pass':
                blockers.update({r['message'] for r in hit['reasons'] if r['severity'] != 'info'})
                continue
            ready = hit['demo_economic_ready'] or hit['economic_ready']
            reasons = hit['economic_reasons']
            candidate = {
                'product_id': hit['product_id'], 'name': hit['name'], 'count': hit['count'],
                'sizing_model': hit['sizing']['model'], 'economic_ready': ready,
                'selected_by_default': hit['product_id'] == defaults.get(group['process_code']),
                'in_program': program is None or group['process_code'] in program,
                'assumption_fields': [a['key'] for a in hit['assumptions']],
                'economic_reasons': reasons,
                'blocker_categories': sorted({blocker_category(r, (group.get('operation') or {}).get('fields', {})) for r in reasons}),
                'commercial_facts': {key: hit['resolved_facts'].get(key) for key in ('solution_kind', 'configuration_complete', 'price_complete')},
                'selection_check': None,
            }
            if ready:
                eligible.append(hit['product_id'])
                if calculate:
                    report = calculate({**defaults, group['process_code']: hit['product_id']})
                    candidate['selection_check'] = verify_selection(report, group, hit)
            technical.append(candidate)
        checked = [c['selection_check'] for c in technical if c['economic_ready']]
        output.append({
            'project': slug, 'process_code': group['process_code'], 'process_name': group['process_name'],
            **{key: counts[key] for key in ('pass', 'conditional_pass', 'unknown', 'fail')},
            'economic_candidates': len(eligible),
            'economy_verified': bool(checked) and all(c and c['verified'] for c in checked),
            'no_suitable_candidate': not technical, 'technical_candidates': technical,
            'operation': group.get('operation'),
            'main_reasons': [{'message': message, 'candidates': count} for message, count in blockers.most_common(5)],
        })
    return output


def coverage(verify_economy=False, *, http_base=None):
    output = []
    if http_base:
        def post(path, payload):
            request = Request(http_base.rstrip('/') + path, data=json.dumps(payload).encode(),
                              headers={'Content-Type': 'application/json'}, method='POST')
            with urlopen(request, timeout=120) as response:
                return json.load(response)
        for slug in PROJECTS:
            matched = post(f'/projects/{slug}/match', {})
            calculate = (lambda picks: post(f'/projects/{slug}/economy', {'picks': picks})) if verify_economy else None
            output.extend(audit_match(slug, matched, calculate))
        return output

    from sqlalchemy import text
    from app.infrastructure.db.session import session_factory
    from app.infrastructure.db.taxonomy_repo import resolve_project, run_match, project_economy
    with session_factory()() as db:
        db.execute(text('SET TRANSACTION READ ONLY'))
        for slug in PROJECTS:
            project = resolve_project(db, slug)
            matched = run_match(db, project.id)
            calculate = (lambda picks: project_economy(db, project.id, None, None, picks=picks)) if verify_economy else None
            output.extend(audit_match(slug, matched, calculate))
        db.rollback()
    return output


def summary(rows):
    technical = [c for r in rows for c in r['technical_candidates']]
    ready = [c for c in technical if c['economic_ready']]
    blocked = [c for c in technical if not c['economic_ready']]
    return {
        'projects': len({r['project'] for r in rows}), 'processes': len(rows),
        'technical_candidates': len(technical), 'economic_candidates': len(ready),
        'blocked_candidates': len(blocked),
        'blocker_categories': dict(Counter(category for c in blocked for category in c['blocker_categories'])),
        'verified_selections': sum(bool(c['selection_check'] and c['selection_check']['verified']) for c in ready),
        'verified_nondefault_selections': sum(bool(c['selection_check'] and c['selection_check']['verified']) for c in ready if not c['selected_by_default']),
        'selection_failures': sum(bool(c['selection_check'] and not c['selection_check']['verified']) for c in ready),
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-economy', action='store_true')
    parser.add_argument('--http-base')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    rows = coverage(args.verify_economy, http_base=args.http_base)
    if args.output:
        args.output.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(summary(rows), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    if args.verify_economy and summary(rows)['selection_failures']:
        raise SystemExit('Есть альтернативы, объявленные готовыми, но не прошедшие явный выбор в экономике')
