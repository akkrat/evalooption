"""Publish incremental/cumulative measurements without changing original trials."""
import json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent
sys.path.insert(0,str(ROOT))
from approach_eval.core import dump
from reporting.build_report import actors
from scripts.report_details import visible_prose


def human_minutes(directory,record):
    conversations=json.loads((directory/'conversation.json').read_text())
    proxy=json.loads((directory/'manifest.json').read_text())['settings']['human_time_proxy']
    read_words=sum(len(visible_prose(c).split()) for c in conversations)
    return (record['user_words']/proxy['write_words_per_minute']+read_words/proxy['read_words_per_minute']+
            len(conversations)*proxy['decision_seconds']/60)


def main():
    schedule=json.loads((HERE/'schedule.json').read_text());rows=[];checks={};context_notes={}
    for plan in schedule['runs']:
        directory=ROOT/plan['directory'];old=ROOT/plan['source']
        r=json.loads((directory/'result.json').read_text());before=json.loads((old/'result.json').read_text())
        lineage=[before];paths=[plan['source']];seen={old.resolve()};ancestor=before.get('recovery_from')
        while ancestor:
            path=Path(ancestor).resolve()
            if path in seen:raise ValueError('Cyclic recovery lineage')
            seen.add(path);prior=json.loads((path/'result.json').read_text());lineage.append(prior)
            paths.append(str(path.relative_to(ROOT)));ancestor=prior.get('recovery_from')
        segment_human={name:human_minutes(ROOT/name,record) for name,record in zip(paths,lineage)}
        extra_human=human_minutes(directory,r)
        a=actors(r);prior_usage=[actors(x) for x in lineage]
        b={key:sum(x[key] for x in prior_usage) for key in ('input_tokens','cached_input_tokens','output_tokens','estimated_api_cost_usd')}
        b['partial']=any(x['partial'] for x in prior_usage)
        recovery=json.loads((directory/'recovery.json').read_text())
        turns=json.loads((directory/'turns.json').read_text())
        if recovery['conversations'][0].get('kind')!='initial':
            context_notes[plan['directory']]='Calibration-only limitation: the supplemental Original task reminder used the first v9 reply, a discover-stage approval summary, because v9 was already recovered from v8. The actual task remained in the resumed sessions, task brief and specs. Benchmark continuations used their original initial requests. Do not treat this calibration as a fresh or controlled benchmark.'
        nodes=recovery['resume_nodes'];resumed=[]
        leaf=next(name for name,node in nodes.items() if node['child_stage'] is None)
        stage=leaf
        while True:
            resumed.append((stage,nodes[stage]['session']))
            parents=[name for name,node in nodes.items() if node['child_stage']==stage]
            if not parents:break
            stage=parents[0]
        observed=[]
        for t in turns:
            if t['role']=='agent' and t['stage'] in nodes and t['stage'] not in {stage for stage,_ in observed}:observed.append((t['stage'],t['session']))
        users=[t for t in turns if t['role']=='user']
        checks[plan['directory']]={
            'leaf_then_original_parents':observed[:len(resumed)]==resumed,
            'original_developer_session':all(t['session']==recovery['user_session'] for t in users),
            'model_efforts':all(t['model']=='gpt-5.6-luna' and t['effort']==('medium' if t['role']=='user' else 'xhigh') for t in turns),
            'explicit_relocated_cwd':all('--cd' in t['command'] and t['command'][t['command'].index('--cd')+1]==str(directory/('user' if t['role']=='user' else 'workspace')) for t in turns if t['role']!='reviewer'),
        }
        task_manifest=json.loads((directory/'manifest.json').read_text())['task']
        names=set(json.loads((old/'changed-files.json').read_text())) | set(json.loads((directory/'changed-files.json').read_text()))
        product_changes=[]
        for name in sorted(names):
            if not (name.startswith('tests/') or any(name.startswith(prefix+'/') for prefix in task_manifest['source_roots'])):continue
            left,right=old/'workspace'/name,directory/'workspace'/name
            if (left.read_bytes() if left.is_file() else None)!=(right.read_bytes() if right.is_file() else None):product_changes.append(name)
        row={**plan,'product_files_changed_during_continuation':product_changes,'context_limitation':context_notes.get(plan['directory']),'source_lineage':paths,'source_segment_human_minutes':segment_human,'cumulative_scope':'All recovered ancestors plus this continuation; calibration ancestors may use earlier harness versions','task':r['task'],'approach':r['approach'],'status':r['status'],'error':r['error'],
             'incremental_workflow_minutes':(r['implementation_seconds']+r['user_simulation_seconds'])/60,
             'cumulative_workflow_minutes':sum(x['implementation_seconds']+x['user_simulation_seconds'] for x in [r,*lineage])/60,
             'incremental_human_minutes':extra_human,
             'cumulative_human_minutes':extra_human+sum(segment_human.values()),
             'incremental_user_words':r['user_words'],'cumulative_user_words':r['user_words']+sum(x['user_words'] for x in lineage),
             'incremental_actor_api_equivalent_usd':a['estimated_api_cost_usd'],
             'cumulative_actor_api_equivalent_usd':a['estimated_api_cost_usd']+b['estimated_api_cost_usd'],
             'incremental_usage_partial':a['partial'],'cumulative_usage_partial':a['partial'] or b['partial'],
             'coverage':r['grade']['changed_line_coverage_percent'],'added_tests':len(r['grade']['candidate_added_tests']),
             'regressions':len(r['grade']['regressions']),
             'historical_passed':r['grade']['fail_to_pass_passed'],'historical_total':r['grade']['fail_to_pass_total']}
        for key in ('input_tokens','cached_input_tokens','output_tokens'):
            row['incremental_actor_'+key]=a[key];row['cumulative_actor_'+key]=a[key]+b[key]
        rows.append(row)
    dump(HERE/'MEASUREMENTS.json',rows)
    dump(HERE/'RESUME_AUDIT.json',{'passed':all(all(c.values()) for c in checks.values()),'checks':checks,'scope':'Session identity, model settings, relocation and ordering checks; context limitations are separately disclosed','context_limitations':context_notes})
    assert all(all(c.values()) for c in checks.values()),checks
    lines=['# Remaining budget-exhausted continuations','',
           'Luna medium developer; Luna xhigh implementers/workers. Original sessions resumed in isolated copies. These are additional-budget continuations, not independent repetitions. The pilot remains calibration; its cumulative figures include the earlier v8 recovery segment as well as v9.','',
           '| Cohort / task / approach | Final status | Historical checks | New regressions | Added-line coverage | Extra / cumulative min | Extra / cumulative human min | Extra / cumulative actor $ |',
           '|---|---|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        lines.append(f"| {r['kind']} / {r['task']} / {r['approach']} | {r['status']} | {r['historical_passed']}/{r['historical_total']} | {r['regressions']} | {r['coverage']:.1f}% | {r['incremental_workflow_minutes']:.1f} / {r['cumulative_workflow_minutes']:.1f} | {r['incremental_human_minutes']:.1f} / {r['cumulative_human_minutes']:.1f} | {r['incremental_actor_api_equivalent_usd']:.4f} / {'≥ ' if r['cumulative_usage_partial'] else ''}{r['cumulative_actor_api_equivalent_usd']:.4f} |")
    lines+=['','Costs include simulated developer and all agent/worker calls, excluding independent reviews. API-equivalent estimates, not subscription bills. Original interrupted usage may be partial. Human minutes count visible prose and interactions, not full code/spec review. Fresh model-review scores can vary even when source code is unchanged; do not interpret that variation as an implementation improvement.','']
    for r in rows:
        name=Path(r['directory']).name
        lines += [f"## {r['kind']}: {r['task']} / {r['approach']}",'',f"[Result](runs/{name}/result.json) · [Conversation](runs/{name}/conversation.json) · [Review](runs/{name}/context-review/result.json)",'',r['error'] or 'Workflow completed and reviewed.','',r.get('context_limitation') or '', '', 'Source/test files changed versus the exhausted snapshot: '+(', '.join(r['product_files_changed_during_continuation']) or 'none')+'.','']
    (HERE/'COMPARISON.md').write_text('\n'.join(lines)+'\n')
    print(HERE/'COMPARISON.md')


if __name__=='__main__':main()
