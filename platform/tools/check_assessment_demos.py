"""READ ONLY-снимок демо. Запуск из platform: python tools/check_assessment_demos.py."""
import json
from collections import Counter
from sqlalchemy import text
from app.infrastructure.db.session import session_factory
from app.infrastructure.db.taxonomy_repo import resolve_project, run_match, project_economy

out = []
with session_factory()() as db:
    db.execute(text('SET TRANSACTION READ ONLY'))
    version = db.execute(text('SELECT version_num FROM alembic_version')).scalar_one()
    for slug in ('demo-warehouse', 'demo-airport', 'demo-hospital'):
        project = resolve_project(db, slug)
        matched = run_match(db, project.id)
        economy = project_economy(db, project.id, None, None)
        out.append({'slug': slug,
                    'groups': [{'process_code': g['process_code'], 'verdicts': dict(Counter(h['verdict'] for h in g['hits'])),
                                'best_product_id': g['best_product_id'],
                                'best_count': next((h['count'] for h in g['hits'] if h['product_id'] == g['best_product_id']), None)} for g in matched['groups']],
                    'robots': economy['robots'], 'status': economy['status'],
                    'coverage': economy['coverage'], 'blockers': economy['blockers'],
                    'purchase_capex': economy['scenarios'][1]['capex']['value'],
                    'purchase_payback': economy['scenarios'][1]['payback']['value']})
    db.rollback()
print(json.dumps({'schema': version, 'demos': out}, ensure_ascii=False, indent=2))
