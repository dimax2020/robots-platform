"""READ ONLY: PYTHONPATH=. python tools/check_demo_coverage.py --verify-economy.

Статусы и количества берутся из рабочих механизмов, без эталонных pass/количеств.
"""
import argparse
import json
from collections import Counter

from sqlalchemy import text

from app.infrastructure.db.session import session_factory
from app.infrastructure.db.taxonomy_repo import resolve_project, run_match, project_economy


def coverage(verify_economy=False):
    output=[]
    with session_factory()() as db:
        db.execute(text('SET TRANSACTION READ ONLY'))
        for slug in ('demo-warehouse','demo-hospital','demo-airport'):
            project=resolve_project(db,slug)
            matched=run_match(db,project.id)
            defaults={g['process_code']:g['demo_best_product_id'] for g in matched['groups'] if g['demo_best_product_id']}
            for group in matched['groups']:
                counts=Counter()
                eligible=[]
                technical=[]
                blockers=Counter()
                for hit in group['hits']:
                    bucket='conditional_pass' if hit['verdict']=='pass' and hit.get('applicability')=='conditional' else hit['verdict']
                    counts[bucket]+=1
                    if hit['verdict']=='pass':
                        technical.append({'product_id':hit['product_id'],'name':hit['name'],'count':hit['count'],
                                          'sizing_model':hit['sizing']['model'],'economic_ready':hit['demo_economic_ready'] or hit['economic_ready'],
                                          'assumption_fields':[a['key'] for a in hit['assumptions']]})
                    else:
                        blockers.update(r['message'] for r in hit['reasons'] if r['severity']!='info')
                    if hit['demo_economic_ready'] or hit['economic_ready']:
                        eligible.append(hit['product_id'])
                        if verify_economy:
                            report=project_economy(db,project.id,None,None,picks={**defaults,group['process_code']:hit['product_id']})
                            item=next(r for r in report['fleet'] if r['process_code']==group['process_code'])
                            assert item['product_id']==hit['product_id'] and item['count_used']==hit['count'] and item['included']
                            assert item['assumptions']==hit['assumptions'] and report['complete']
                output.append({'project':slug,'process_code':group['process_code'],'process_name':group['process_name'],
                               **{key:counts[key] for key in ('pass','conditional_pass','unknown','fail')},
                               'economic_candidates':len(eligible),'economy_verified':verify_economy and bool(eligible),
                               'no_suitable_candidate':not technical,'technical_candidates':technical,
                               'main_reasons':[{'message':message,'candidates':count} for message,count in blockers.most_common(5)]})
        db.rollback()
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-economy',action='store_true')
    args=parser.parse_args()
    print(json.dumps(coverage(args.verify_economy),ensure_ascii=False,indent=2))
