"""Validate report provenance, metric mapping, complete reviews, and artifact links."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def validate(root=ROOT):
    data=json.loads((root/'reports/comparison/data.json').read_text())
    errors=[]
    def check(value,message):
        if not value:errors.append(message)
    check(len(data['runs'])>=20,'Expected at least the 20 original recorded run phases')
    check(len({r['id'] for r in data['runs']})==len(data['runs']),'Duplicate run IDs')
    check(len(data['references'])==4,'Expected four original solutions')
    for source in data['sources']:
        check(hashlib.sha256((root/source['path']).read_bytes()).hexdigest()==source['sha256'],'Input changed: '+source['path'])
    for r in data['runs']+data['references']:
        raw=json.loads((root/r['directory']/'result.json').read_text());grade=raw['grade']
        check(r['added_tests']==len(grade.get('candidate_added_tests',{})),r.get('id',r['task'])+': added tests mismatch')
        check(r['regressions']==len(grade.get('regressions',[])),r.get('id',r['task'])+': regressions mismatch')
        cov=r['coverage']
        check(cov['total'] is not None and not cov['unmapped'],r.get('id',r['task'])+': missing coverage mapping')
        expected=100*cov['covered']/cov['total'] if cov['total'] else None
        check(cov['percent']==expected,r.get('id',r['task'])+': inconsistent coverage ratio')
        check(bool(r['quality']) or r.get('phase')=='calibration-initial',r.get('id',r['task'])+': missing quality review')
    for r in data['runs']:
        if r['phase'].endswith('continuation'):
            source='studies/actual-balance-forecast/continuation-01/MEASUREMENTS.json' if r['task']=='actual-balance-forecast' else 'studies/library-continuation-01/MEASUREMENTS.json'
            rows=json.loads((root/source).read_text())
            m=next(x for x in rows if x['approach']==r['approach'] and x.get('task',r['task'])==r['task'])
            for key,source in [('minutes','cumulative_workflow_minutes'),('human_minutes','cumulative_human_minutes'),('cost','cumulative_actor_api_equivalent_usd'),('words','cumulative_user_words')]:
                check(r[key]==m[source],r['id']+': cumulative '+key+' mismatch')
        for f in r['code']:
            for key in ('candidate_file','reference_file'):
                if f[key]:check((root/f[key]).is_file(),'Missing code link: '+f[key])
    for a in data['artifacts']:
        p=root/a['path'];check(p.is_file() and p.stat().st_size==a['bytes'],'Missing/changed artifact: '+a['path'])
    result={'passed':not errors,'run_phases':len(data['runs']),'reference_solutions':len(data['references']),'artifact_links':len(data['artifacts']),'errors':errors}
    print(json.dumps(result,indent=2))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,default=ROOT)
    result=validate(parser.parse_args().root)
    raise SystemExit(0 if result['passed'] else 1)
