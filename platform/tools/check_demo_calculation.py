"""Воспроизводимый READ ONLY-расчёт: PYTHONPATH=. python tools/check_demo_calculation.py.

DEMO_SYNTHETIC_ENABLED=true включает только явно зарегистрированные is_demo-проекты.
"""
import json
from sqlalchemy import text
from app.infrastructure.db.session import session_factory
from app.infrastructure.db.taxonomy_repo import project_economy, resolve_project

out = []
with session_factory()() as db:
    db.execute(text('SET TRANSACTION READ ONLY'))
    for slug in ('demo-warehouse', 'demo-hospital', 'demo-airport'):
        project = resolve_project(db, slug)
        report = project_economy(db, project.id, None, None)
        out.append({'slug': slug, 'status': report['status'], 'scope': report['scope'],
                    'robots': report['robots'], 'blockers': report['blockers'], 'fleet': report['fleet'],
                    'manual_processes': report['manual_processes'],
                    'demo_synthetic': report['demo_synthetic'],
                    'scenarios': [{**{k: s[k]['value'] for k in ('capex', 'opex', 'effect', 'tco', 'roi', 'payback')},
                                   'key': s['key'], 'annual_cost': s['annual_cost']} for s in report['scenarios']],
                    'load_200_robots': project_economy(db, project.id, None, None, preview={'load_factor':200})['robots']})
    db.rollback()
print(json.dumps(out, ensure_ascii=False, indent=2))
