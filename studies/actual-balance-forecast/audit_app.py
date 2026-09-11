"""Read-only consistency checks for the completed application study."""
from runtime import *
from app_fingerprint import fingerprint
from approach_eval.core import git

def audit():
    settings=json.loads((STUDY/'evaluation.json').read_text())
    schedule=json.loads((STUDY/'schedule.json').read_text())
    current=fingerprint(settings)
    checks={'engine_unchanged':current==schedule['fingerprint'],
            'borrowed_changes_helper_unchanged':(ROOT/'approach_eval/grading.py').read_bytes()==(ROOT/'runs/suite/frozen-harness/approach_eval/grading.py').read_bytes(),
            'adapter_gate_passed':json.loads((STUDY/'validation/gate.json').read_text())['valid'],
            'replay_gate_passed':json.loads((STUDY/'validation/replay-smoke-gate.json').read_text())['passed'],
            'reset_credit_used':False}
    results=[]
    rollouts={p.stem[-36:]:p for p in (Path.home()/'.codex/sessions').rglob('*.jsonl')}
    contexts={}
    def rollout_matches(turn):
        session=turn.get('session')
        if session not in contexts:
            found=[]
            path=rollouts.get(session)
            if path:
                for line in path.open():
                    if '"turn_context"' not in line:continue
                    try:event=json.loads(line)
                    except ValueError:continue
                    if event.get('type')=='turn_context':
                        value=event['payload'];found.append({'model':value.get('model'),'effort':value.get('effort',value.get('reasoning_effort'))})
            contexts[session]=found
        return bool(contexts[session]) and all(v['model']==turn['model'] and v['effort']==turn['effort'] for v in contexts[session])
    for approach in schedule['approaches']:
        directory=STUDY/'runs'/approach
        if not (directory/'result.json').exists():continue
        result=json.loads((directory/'result.json').read_text());turns=json.loads((directory/'turns.json').read_text())
        tree=directory/'workspace'
        future=subprocess.run([str(GIT),'cat-file','-e',schedule['task']['base_commit']],cwd=tree,capture_output=True).returncode
        # The upstream base object, and therefore its future merge, must not be present.
        entry=dict(approach=approach,model_efforts_match=all(t['model']=='gpt-5.6-luna' and t['effort']==('medium' if t['role']=='user' else 'xhigh') for t in turns),
                   fingerprint_matches=result['fingerprint']==current,
                   rollout_model_efforts_match=all(rollout_matches(t) for t in turns),
                   original_history_absent=future!=0,
                   snapshot_commits=int(git(tree,'rev-list','--count','HEAD').strip()),
                   remotes=git(tree,'remote').strip(),
                   grade_recorded=result.get('grade') is not None,
                   quality_review_recorded=(directory/'quality-review/result.json').exists())
        if (directory/'quality-review/turns.json').exists():
            review=json.loads((directory/'quality-review/turns.json').read_text())
            entry['review_model_effort_match']=all(t['model']=='gpt-5.6-luna' and t['effort']=='xhigh' and rollout_matches(t) for t in review)
        if (directory/'quality-review/not-applicable.json').exists():
            entry['review_model_effort_match']=True
            entry['review_kind']='not applicable: no product code'
        results.append(entry)
    checks['recorded_trials']=len(results)
    qa=[]
    for approach in schedule['approaches']:
        directory=STUDY/'runs'/approach
        summary=directory/'adjudication/summary.json'
        value=json.loads(summary.read_text()) if summary.exists() else {}
        attempts=[]
        for name in value.get('attempts',[]):
            path=directory/name/'result.json'
            record=json.loads(path.read_text()) if path.exists() else {}
            attempts.append(bool(record.get('source_integrity',{}).get('unchanged')))
        qa.append({'approach':approach,'reviewed':value.get('reviewed') is True,
                   'replay_sources_unchanged':all(attempts)})
    checks['browser_qa']=qa
    checks['browser_qa_recorded']=all(x['reviewed'] and x['replay_sources_unchanged'] for x in qa)
    measurements=STUDY/'MEASUREMENTS.json'
    checks['report_recorded']=measurements.exists() and len(json.loads(measurements.read_text()))==4 and (STUDY/'QA_REPORT.md').exists()

    checks['passed']=(checks['engine_unchanged'] and checks['borrowed_changes_helper_unchanged'] and checks['adapter_gate_passed'] and checks['replay_gate_passed'] and len(results)==4 and checks['browser_qa_recorded'] and checks['report_recorded'] and
        all(r['model_efforts_match'] and r['rollout_model_efforts_match'] and r['fingerprint_matches'] and r['original_history_absent'] and r['snapshot_commits']==1 and not r['remotes'] and r['grade_recorded'] and r['quality_review_recorded'] and r.get('review_model_effort_match') for r in results))
    checks['trials']=results;dump(STUDY/'AUDIT.json',checks);print(json.dumps(checks,indent=2));return checks
if __name__=='__main__':audit()
