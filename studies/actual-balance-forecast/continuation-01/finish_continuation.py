"""Review continuation submissions and report incremental/cumulative measurements."""
import json,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from runtime import dump
from finish_app import review,RUBRICS
from post_metrics import measure

def report():
    original={r['approach']:r for r in json.loads((HERE.parent/'MEASUREMENTS.json').read_text())}
    rows=[]
    for approach in ('prompt','plan','openspec','gennady'):
        directory=HERE/'runs'/approach
        if not (directory/'result.json').exists():continue
        r=json.loads((directory/'result.json').read_text());g=r.get('grade') or {};old=original[approach]
        turns=json.loads((directory/'turns.json').read_text());actors=[t for t in turns if t['role'] in ('user','agent')]
        quality=json.loads((directory/'quality-review/result.json').read_text()) if (directory/'quality-review/result.json').exists() else None
        qa=json.loads((directory/'adjudication/summary.json').read_text()) if (directory/'adjudication/summary.json').exists() else None
        cost=sum(t.get('estimated_api_cost_usd') or 0 for t in actors)
        row=dict(approach=approach,status=r['status'],error=r.get('error'),quality=quality,browser_adjudication=qa,
                 incremental_workflow_minutes=r['workflow_seconds']/60,cumulative_workflow_minutes=old['workflow_minutes']+r['workflow_seconds']/60,
                 incremental_human_minutes=r['estimated_human_minutes'],cumulative_human_minutes=old['human_minutes']+r['estimated_human_minutes'],
                 incremental_user_words=r['user_words'],cumulative_user_words=old['user_words']+r['user_words'],
                 incremental_read_words=r['user_read_words'],cumulative_read_words=old['read_words']+r['user_read_words'],
                 incremental_actor_api_equivalent_usd=cost,cumulative_actor_api_equivalent_usd=old['actor_api_equivalent_usd']+cost,
                 incremental_usage_partial=any(t.get('usage_is_partial') or t.get('usage') is None for t in actors),
                 cumulative_usage_partial=old['usage_partial'] or any(t.get('usage_is_partial') or t.get('usage') is None for t in actors),
                 incremental_questions=r['questions'],cumulative_questions=old['questions']+r['questions'],
                 incremental_grading_minutes=r['evaluation_seconds']/60,
                 raw_browser=g.get('browser'),regressions=g.get('regressions'),
                 build=(g.get('build') or {}).get('returncode'),typecheck=(g.get('typecheck') or {}).get('returncode'),lint=(g.get('lint') or {}).get('returncode'),
                 candidate_added_tests=g.get('candidate_added_tests'),coverage=g.get('coverage'),diff_metrics=measure(directory))
        for key in ('input_tokens','cached_input_tokens','output_tokens'):
            row['incremental_actor_'+key]=sum((t.get('usage') or {}).get(key,0) for t in actors)
            row['cumulative_actor_'+key]=old['actor_'+key]+row['incremental_actor_'+key]
        qturns=json.loads((directory/'quality-review/turns.json').read_text()) if (directory/'quality-review/turns.json').exists() else []
        row['review_api_equivalent_usd']=sum(t.get('estimated_api_cost_usd') or 0 for t in qturns)
        rows.append(row)
    dump(HERE/'MEASUREMENTS.json',rows)
    lines=['# Actual Budget: additional-budget continuation','',f'{len(rows)}/4 results recorded. '+('Provisional.' if len(rows)<4 else ''),'',
           'These are resumed original sessions in copied checkouts, not fresh independent trials. The [original bounded comparison](../COMPARISON.md) remains unchanged. Luna medium developer and Luna xhigh agents; no evaluator feedback supplied to actors. See [continuation protocol](PROTOCOL.md).','',
           '| Approach | Continuation outcome | Extra / total workflow min | Extra / total human proxy min | Extra / total developer words | Extra / total actor API-equivalent $ |','|---|---|---:|---:|---:|---:|']
    if len(rows)==4 and all(r['browser_adjudication'] for r in rows):
        lines[4:4]=[
            'Direct prompting, plan then implement, and OpenSpec completed their workflows and passed all seven common browser checks plus the non-default Monthly persistence probe. Gennady ended blocked at its infrastructure prerequisite without feature code. All four have zero new original-suite regressions.',
            '',
            'Visual issues remain: direct prompting clips its controls; OpenSpec displays a stale End date after a preset change; both omit the monthly minimum marker. The seven passing checks do not establish complete correctness. See [visual evidence](QA_REPORT.md).',
            '',
            'This is the separate Actual Budget application task from [PR 7310](https://github.com/actualbudget/actual/pull/7310), whose reference is explicitly AI-assisted. It is not pooled with the original 12-run library study. The inherited Gennady scope also includes extra currency handling beyond the common brief; that work is not rewarded by this grader.',
            '',
        ]
    for r in rows:
        lines.append(f"| {r['approach']} | {r['status']} | {r['incremental_workflow_minutes']:.1f} / {r['cumulative_workflow_minutes']:.1f} | {r['incremental_human_minutes']:.1f} / {r['cumulative_human_minutes']:.1f} | {r['incremental_user_words']} / {r['cumulative_user_words']} | {r['incremental_actor_api_equivalent_usd']:.4f} / {r['cumulative_actor_api_equivalent_usd']:.4f}{' (partial)' if r['cumulative_usage_partial'] else ''} |")
    lines+=['','Human time is the same summary-reading/writing/decision proxy, excluding full code/spec review. Cumulative costs retain any partial usage from the original timeout. Prices are pinned API-equivalent estimates, not subscription charges. Setup, independent grading and review costs are recorded separately. Historical work is inherited once, not charged again as new work.','',
            '| Approach | Build / types / lint | New original-suite regressions | Added tests passed / total | Browser replay | Added-statement coverage |','|---|---|---:|---:|---|---:|']
    for r in rows:
        commands=' / '.join('pass' if r[k]==0 else 'fail' if r[k] is not None else '?' for k in ('build','typecheck','lint'))
        tests=r['candidate_added_tests'] or {};qa=r['browser_adjudication'];coverage=r['diff_metrics']['added_statement_start_line_coverage_percent']
        browser=f"{qa['feature_checks_passed']}/7 — {qa['status']}" if qa else 'pending'
        lines.append(f"| {r['approach']} | {commands} | {len(r['regressions']) if r['regressions'] is not None else '?'} | {sum(v=='passed' for v in tests.values())}/{len(tests)} | {browser} | {f'{coverage:.1f}%' if coverage is not None else 'N/A'} |")
    lines+=['','Candidate tests/coverage and code quality describe the whole current implementation, including inherited code. Raw browser results and historical private-module compatibility remain in each result.json. Equivalent-control replay and visual findings are separate post-trial evidence; seven fixture checks do not prove all requirements.','',
            '| Approach | Maintainability | Readability | Tests | Performance | Security | Requirements | UI/accessibility |','|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        lines.append('| '+r['approach']+' | '+' | '.join(('N/A' if (r['quality'] or {}).get(k,{}).get('score','pending') is None else str((r['quality'] or {}).get(k,{}).get('score','pending'))) for k in RUBRICS)+' |')
    lines+=['','Scores are blind same-model judgments, not an independent human audit. Reviews use raw measurements before additional browser adjudication. Their evidence and limitations are preserved; replay findings supersede only the obligations tested.','']
    for r in rows:
        a=r['approach'];lines.extend([f"## {a}",'',f"[Result](runs/{a}/result.json) · [Conversation](runs/{a}/conversation.json) · [Quality evidence](runs/{a}/quality-review/result.json)",'',r['error'] or 'Workflow completed.',''])
    lines+=['[Workflow observations](WORKFLOW_FINDINGS.md) · [Machine-readable measurements](MEASUREMENTS.json) · [Browser/visual evidence](QA_REPORT.md) · [Audit](AUDIT.json)','']
    (HERE/'COMPARISON.md').write_text('\n'.join(lines))
    return rows

def main():
    while True:
        for approach in ('prompt','plan','openspec','gennady'):
            d=HERE/'runs'/approach
            if (d/'result.json').exists():review(d)
        rows=report()
        if len(rows)==4 and all(r['quality'] is not None for r in rows):break
        time.sleep(30)
    print('CONTINUATION REVIEWS AND REPORT COMPLETE',flush=True)

if __name__=='__main__':main()
