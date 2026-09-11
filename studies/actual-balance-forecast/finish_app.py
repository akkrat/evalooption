"""Separate blind quality review and reporting for all completed or partial app trials."""
from runtime import *
from approach_eval.core import config,git,digest
from approach_eval.grading import changes
from app_codex import Codex
import time
from post_metrics import measure

RUBRICS=('maintainability','readability','test_quality','performance','security','requirements_completeness','ui_accessibility')

def review(directory):
    output=directory/'quality-review'
    if (output/'result.json').exists():return
    result=json.loads((directory/'result.json').read_text());tree=directory/'workspace'
    filenames=changes(tree)
    product_code=[name for name in filenames if name.startswith('packages/') and '.test.' not in name and '/e2e/' not in name and Path(name).suffix in ('.ts','.tsx','.js','.jsx','.mjs','.cjs')]
    if not product_code:
        rating={key:{'score':None,'evidence':'No product code was submitted; this quality is not assessable.'} for key in RUBRICS}
        rating['requirements_completeness']={'score':1,'evidence':'No implementation of the requested feature was submitted.'}
        dump(output/'not-applicable.json',{'reason':'No changed product code','changed_files':filenames})
        dump(output/'result.json',rating)
        return
    settings=config();settings.update(turn_timeout_seconds=900,max_run_seconds=1800)
    client=Codex(output,settings)
    context=CACHE/'actual-review-contexts'/digest(str(directory))[:24];context.mkdir(parents=True,exist_ok=True)
    files=changes(tree);source=[];total=0;omitted=[]
    for name in files:
        if not name.startswith('packages/'):continue
        p=tree/name
        if not p.is_file() or p.suffix not in ('.ts','.tsx','.js','.json','.md','.css','.scss'):continue
        text=p.read_text(errors='replace')
        if total+len(text)>650000:omitted.append(name);continue
        source.append('\nFILE '+name+'\n'+text);total+=len(text)
    grade=result.get('grade') or {}
    measured={key:grade.get(key) for key in ('browser','regressions','candidate_added_tests','coverage','limitation')}
    measured['commands']={key:(grade.get(key) or {}).get('returncode') for key in ('build','typecheck','lint')}
    # Avoid giving a reviewer an approach label or run-directory name through logs/commands.
    def redact(value):
        if isinstance(value,dict):return {k:redact(v) for k,v in value.items() if k not in ('command','mapping','output_directory')}
        if isinstance(value,list):return [redact(v) for v in value]
        if isinstance(value,str):return value.replace(str(directory),'<candidate>').replace(str(ROOT),'<workspace>')
        return value
    prompt=('Review a candidate implementation of a TypeScript personal finance application feature. '
            'No tools, no edits, no dispatches. The candidate approach and reference implementation are withheld. '
            'The baseline has 1225 existing tests passing and 3 skipped. Evaluate the actual submitted code and '
            'measurements; do not assume unspecified behavior is correct. Distinguish browser selector mismatches '
            'from proven product defects. Runtime tests do not prove security/performance/accessibility. '
            'Respect Actual conventions: translated UI, existing theme and financial number styles, no new '
            'type/lint suppressions without a justified exception, prefer precise types and real tests. '
            'Return status done. message must be a JSON object with keys '+','.join(RUBRICS)+'. '
            'Each value: {score: integer 1-5, evidence: specific concise explanation including limitations}. '
            '1=serious defects, 3=adequate, 5=excellent.\nTASK\n'+(STUDY/'task.md').read_text()+
            '\nMEASUREMENTS\n'+json.dumps(redact(measured))+'\nTRACKED DIFF\n'+git(tree,'diff','HEAD','--','packages')+
            '\nCOMPLETE CHANGED FILES\n'+''.join(source)+'\nOMITTED FILES DUE TO SIZE\n'+json.dumps(omitted))
    _,response=client.call('reviewer',context,prompt,stage='blind-application-review',read_only=True)
    try:
        rating=json.loads(response['message'])
        for key in RUBRICS:
            assert type(rating[key]['score']) is int and 1<=rating[key]['score']<=5
            assert isinstance(rating[key]['evidence'],str)
        dump(output/'result.json',rating)
    except (ValueError,KeyError,AssertionError,TypeError):
        dump(output/'error.json',response);raise RuntimeError('Invalid quality review: '+str(output))

def report():
    rows=[];feature_ids=set(json.loads((STUDY/'validation/gate.json').read_text())['browser_check_ids'])-{'local-budget-startup'}
    for approach in ('prompt','plan','openspec','gennady'):
        directory=STUDY/'runs'/approach
        if not (directory/'result.json').exists():continue
        result=json.loads((directory/'result.json').read_text());g=result.get('grade') or {}
        counts=g.get('historical_structure_compatibility',{})
        quality=json.loads((directory/'quality-review/result.json').read_text()) if (directory/'quality-review/result.json').exists() else None
        turns=json.loads((directory/'turns.json').read_text())
        actor=[t for t in turns if t['role'] in ('user','agent')]
        reviewturns=json.loads((directory/'quality-review/turns.json').read_text()) if (directory/'quality-review/turns.json').exists() else []
        passed={x['id'] for x in g.get('browser',{}).get('checks',[]) if x['status']=='passed'}&feature_ids
        row=dict(approach=approach,status=result['status'],error=result['error'],
                 workflow_minutes=result.get('workflow_seconds',0)/60,evaluation_minutes=result.get('evaluation_seconds',0)/60,
                 human_minutes=result['estimated_human_minutes'],user_words=result['user_words'],read_words=result['user_read_words'],
                 interactions=result['user_interactions'],questions=result['questions'],dispatches=result['dispatch_count'],
                 feature_checks_passed=len(passed),feature_checks_total=len(feature_ids),browser_pass=g.get('browser',{}).get('passed',False),
                 regressions=len(g.get('regressions',[])),grade_available=bool(g),
                 build=(g.get('build') or {}).get('returncode'),typecheck=(g.get('typecheck') or {}).get('returncode'),lint=(g.get('lint') or {}).get('returncode'),
                 candidate_added_tests=len(g.get('candidate_added_tests',{})),candidate_added_tests_passed=sum(x=='passed' for x in g.get('candidate_added_tests',{}).values()),
                 historical_passed=sum((v.get('counts') or {}).get('passed',0) for v in counts.values()),
                 historical_total=sum((v.get('counts') or {}).get('total',0) for v in counts.values()),
                 coverage=g.get('coverage'),quality=quality,
                 actor_api_equivalent_usd=sum(t.get('estimated_api_cost_usd') or 0 for t in actor),
                 actor_input_tokens=sum((t.get('usage') or {}).get('input_tokens',0) for t in actor),
                 actor_cached_input_tokens=sum((t.get('usage') or {}).get('cached_input_tokens',0) for t in actor),
                 actor_output_tokens=sum((t.get('usage') or {}).get('output_tokens',0) for t in actor),
                 usage_partial=any(t.get('usage_is_partial') or t.get('usage') is None for t in actor),
                 review_api_equivalent_usd=sum(t.get('estimated_api_cost_usd') or 0 for t in reviewturns))
        row['diff_metrics']=measure(directory)
        qa=directory/'adjudication/summary.json'
        row['browser_adjudication']=json.loads(qa.read_text()) if qa.exists() else None
        rows.append(row)
    dump(STUDY/'MEASUREMENTS.json',rows)
    lines=['# Actual Budget: four coding approaches','',f"Progress: {len(rows)}/4 trials recorded." + (' Provisional comparison.' if len(rows)<4 else ''),'',
      'One substantial application task, one run per approach, Luna medium developer and Luna xhigh agents. The [reference PR](https://github.com/actualbudget/actual/pull/7310) declares AI assistance. These results are separate from the original library matrix.','',
      '| Approach | Workflow | Raw browser checks | Regressions | Build/types/lint | Workflow min | Human proxy min | Developer words | Actor API-equivalent $ |',
      '|---|---|---:|---:|---|---:|---:|---:|---:|']
    if len(rows)==4 and all(r.get('browser_adjudication') for r in rows):
        lines.insert(6,'Three implementations (prompt, plan and OpenSpec) pass all seven common browser obligations after equivalent controls are bound, plus a separate non-default Monthly persistence probe. All four have zero new original-suite regressions. All workflows were censored: the three implementation calls hit 30 minutes; Gennady hit the discovery-question cap without product code. Visual QA found stale date controls in OpenSpec and overlapping controls in prompt. See [replay evidence and limitations](QA_REPORT.md).')
        lines.insert(7,'')
    for r in rows:
        checks='/'.join('pass' if r[k]==0 else 'fail' if r[k] is not None else '?' for k in ('build','typecheck','lint'))
        lines.append(f"| {r['approach']} | {r['status']} | {r['feature_checks_passed']}/{r['feature_checks_total']} | {r['regressions'] if r['grade_available'] else '?'} | {checks} | {r['workflow_minutes']:.1f} | {r['human_minutes']:.1f} | {r['user_words']} | {'partial ' if r['usage_partial'] else ''}{r['actor_api_equivalent_usd']:.4f} |")
    lines+=['','Browser checks count passed feature obligations; later checks blocked by an earlier UI mismatch are unverified, not independently demonstrated failures. Inspect the browser error and candidate code before treating selector incompatibility as product failure. Historical private-module tests are a separate compatibility measure.','',
      '| Approach | Added tests passing/total | Historical tests passed/reported | Changed-file statement-line coverage | Worker dispatches |',
      '|---|---:|---:|---:|---:|']
    for r in rows:
        cov=(r['coverage'] or {}).get('changed_file_statement_line_coverage_percent')
        lines.append(f"| {r['approach']} | {r['candidate_added_tests_passed']}/{r['candidate_added_tests']} | {str(r['historical_passed'])+'/'+str(r['historical_total']) if r['historical_total'] else 'Import failure (22 reference cases)'} | {f'{cov:.1f}%' if cov is not None else 'unavailable'} | {r['dispatches']} |")
    lines+=['','| Approach | Changed production/test/doc files | Added production lines | Added statement-start line coverage |',
            '|---|---:|---:|---:|']
    for r in rows:
        m=r['diff_metrics'];cov=m['added_statement_start_line_coverage_percent']
        lines.append(f"| {r['approach']} | {m['changed_production_files']}/{m['changed_test_files']}/{m['changed_documentation_files']} | {m['added_production_text_lines']} | {f'{cov:.1f}%' if cov is not None else 'unavailable'} |")
    lines+=['','Added-line coverage counts distinct added/changed lines starting an Istanbul statement, unioned across core/web tests. It excludes comments, type-only lines and statement continuations. Unmapped files and the exact definition are recorded in post-metrics.json. File/line counts indicate scope, not quality.']
    lines+=['','The historical reference contributes 22 tests. A suite-import failure may report zero tests; it is not a zero-obligation success. Coverage includes mapped statement lines in changed production files, including untouched lines in those files. It is not path coverage.','',
      '| Approach | Maintainability | Readability | Test quality | Performance | Security | Requirements | UI/accessibility |',
      '|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in rows:lines.append('| '+r['approach']+' | '+' | '.join(('N/A' if (r['quality'] or {}).get(k,{}).get('score','pending') is None else str((r['quality'] or {}).get(k,{}).get('score','pending'))) for k in RUBRICS)+' |')
    lines+=['','Rubric scores are blind Luna model judgments on a 1–5 scale, with evidence and limitations in each linked review. When no product code was submitted, code qualities are N/A and requirement completion is 1; no model review is fabricated. They are not objective measurements. Reviews preceded the additional browser replay; their unverified-UI statements are superseded only for the specific checks in QA_REPORT.md. Reviewers received whole-changed-file coverage, including untouched code; the separate added-line coverage table is the better measure of coverage of new statements. Review costs are recorded separately in MEASUREMENTS.json.','',
      'Human time uses 200 reading words/minute, 40 writing words/minute, and 20 seconds per interaction. It covers displayed summaries and replies, not full code/spec review. Workflow time excludes setup and external grading. Costs use the pinned API-equivalent rate card, not subscription billing. One task/run cannot establish general superiority or statistical significance. Per-call and question caps censor completion differently across workflow shapes; a stopped run does not show what a larger budget would achieve. Gennady also elicited multi-currency scope beyond the common brief and used Russian during discovery; its extra work is not rewarded by the common-task grader.','']
    for r in rows:
        lines+=['## '+r['approach'],'',f"[Result](runs/{r['approach']}/result.json) · [Conversation](runs/{r['approach']}/conversation.json) · [Quality evidence](runs/{r['approach']}/quality-review/result.json)",'']
        if r['error']:lines+=[r['error'],'']
    if any(r.get('browser_adjudication') for r in rows):
        lines+=['## Browser replay after locator inspection','','The frozen raw checks above are preserved. This additional replay uses equivalent visible controls with the same fixture and expected outcomes; no candidate code was changed. See [recorded adaptations, screenshots and observations](QA_REPORT.md).','','| Approach | Additional replay | Feature checks verified |','|---|---|---:|']
        for r in rows:
            qa=r.get('browser_adjudication') or {}
            lines.append(f"| {r['approach']} | {qa.get('status','pending')} | {qa.get('feature_checks_passed','?')}/{r['feature_checks_total']} |")
        lines+=['','These checks cover only the stated seven obligations; chart rendering observations and untested edge cases are recorded separately.','']
    lines+=['See [protocol, runtime and caveats](README.md), [validation gate](validation/gate.json), and [machine-readable measurements](MEASUREMENTS.json).','']
    (STUDY/'COMPARISON.md').write_text('\n'.join(lines))
    return rows

def main():
    approaches=('prompt','plan','openspec','gennady')
    while True:
        for approach in approaches:
            directory=STUDY/'runs'/approach
            if (directory/'result.json').exists():review(directory)
        rows=report()
        if len(rows)==4 and all(r['quality'] is not None for r in rows):break
        time.sleep(30)
    print('APPLICATION REPORT AND REVIEWS COMPLETE',flush=True)
if __name__=='__main__':main()
