import json,time,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
rows=[]
for a in ('prompt','plan','openspec','gennady'):
    d=HERE/'runs'/a
    r=json.loads((d/'result.json').read_text()) if (d/'result.json').exists() else {}
    t=json.loads((d/'turns.json').read_text()) if (d/'turns.json').exists() else []
    calls=sorted((d/'turns').glob('*'))
    rows.append({'approach':a,'status':r.get('status','running' if d.exists() else 'queued'),'latest_call':calls[-1].name if calls else None,'recorded_calls':len(t),'active_call_minutes':round((time.time()-(calls[-1]/'prompt.txt').stat().st_mtime)/60,1) if calls and len(calls)>len(t) else 0,'extra_cli_minutes':round(sum(x['seconds'] for x in t)/60,1),'review_recorded':(d/'quality-review/result.json').exists()})
if '--compact' in sys.argv:
    for row in rows:
        if row['status']=='queued':continue
        print(f"{row['approach']}: {row['status']}; {row['latest_call']}; {row['recorded_calls']} calls; recorded {row['extra_cli_minutes']} min + active {row['active_call_minutes']} min; review={row['review_recorded']}")
    print('Queued: '+', '.join(r['approach'] for r in rows if r['status']=='queued'))
else:
    print(json.dumps(rows,indent=2))
