"""Recover the suspended nested dispatch chain, including its original leaf session."""
import json
from pathlib import Path
import shutil


def prepare_recovery(task, approach, source, candidate):
    source=Path(source).resolve()
    manifest=json.loads((source/'manifest.json').read_text())
    if manifest['task']!=task or manifest['approach']!=approach:raise ValueError('Task/approach mismatch')
    previous=json.loads((source/'result.json').read_text())
    if previous['status']!='budget_exhausted':raise ValueError('Only exhausted runs may enter this continuation')
    turns=json.loads((source/'turns.json').read_text())
    leaf=next(t for t in reversed(turns) if t['role']=='agent')
    user=next(t for t in reversed(turns) if t['role']=='user')
    nodes={};stage=leaf['stage'];child=None
    while True:
        turn=next(t for t in reversed(turns) if t['role']=='agent' and t['stage']==stage)
        if not turn.get('session'):raise ValueError('Missing original session ID')
        response_path=source/'turns'/f"{turn['index']:03d}-agent-{stage}"/'response.json'
        response=json.loads(response_path.read_text()) if response_path.exists() else {}
        if child and not (response.get('status')=='dispatch' and len(response['dispatches'])==1):
            raise ValueError('Recovery requires one unreturned worker per suspended parent')
        nodes[stage]={'session':turn['session'],'child_stage':child,'pending_response':response}
        if '-worker' not in stage:break
        child,stage=stage,stage.rsplit('-worker',1)[0]
    completed={s['stage'] for s in previous.get('stages',[])}
    if stage in completed:raise ValueError('Interrupted session belongs to an already completed stage')
    old=source/'workspace';shutil.copytree(old,candidate)
    for name in ('specs','tasks','openspec','.workflow'):
        for p in (candidate/name).rglob('*.md'):
            p.write_text(p.read_text().replace(str(old),str(candidate)))
    inherited=json.loads(json.dumps(previous.get('stages',[])).replace(str(old),str(candidate)))
    for s in inherited:s['inherited_from']=str(source)
    return {'source':str(source),'fingerprint':manifest['fingerprint'],'stages':inherited,
            'conversations':json.loads((source/'conversation.json').read_text()),
            'previous_status':previous['status'],'previous_dispatch_count':previous.get('dispatch_count',0),
            'user_session':user['session'],'resume_nodes':nodes}
