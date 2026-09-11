"""Compact read-only progress snapshot; safe while a CLI turn is running."""
from pathlib import Path
import json
study=Path(__file__).resolve().parent
rows=[]
for approach in ('prompt','plan','openspec','gennady'):
    root=study/'runs'/approach
    result=root/'result.json'
    turns=json.loads((root/'turns.json').read_text()) if (root/'turns.json').exists() else []
    folders=sorted(p.name for p in (root/'turns').glob('*') if p.is_dir())
    value=json.loads(result.read_text()) if result.exists() else {}
    rows.append({'approach':approach,'status':value.get('status','started-without-result' if root.exists() else 'queued'),
                 'latest_call':folders[-1] if folders else None,'recorded_calls':len(turns),
                 'recorded_cli_minutes':round(sum(t['seconds'] for t in turns)/60,1),
                 'review_recorded':(root/'quality-review/result.json').exists()})
print(json.dumps(rows,indent=2))
