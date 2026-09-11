"""Build an offline comparison from immutable evidence, or a portable data.json."""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import subprocess
from datetime import datetime, timezone
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'studies/actual-balance-forecast'
APPROACHES = ['prompt', 'plan', 'openspec', 'gennady']
try:
    from .archive_results import excluded
except ImportError:
    from archive_results import excluded


def read(p, default=None):
    return json.loads(p.read_text()) if p.exists() else default


def rel(p):
    return str(p.relative_to(ROOT))


def git(repo, *args):
    return subprocess.check_output(['git', '-c', 'core.hooksPath=/dev/null', *args], cwd=repo, text=True)


def text_file(p):
    if not p.is_file() or p.is_symlink():
        return ''
    data = p.read_bytes()
    return '[Binary file; see artifact]' if b'\0' in data else data.decode('utf-8', errors='replace')


def changed(tree):
    return sorted(set(git(tree, 'diff', '--name-only', 'HEAD').splitlines() + git(tree, 'ls-files', '--others', '--exclude-standard').splitlines()))


def code_files(names):
    return [n for n in names if not n.startswith(('.agents/', '.claude/', '.codex/', 'specs/', 'openspec/', 'tasks/')) and Path(n).suffix in {'.py', '.pyi', '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.css', '.scss', '.json', '.md', '.rst'}]


def diff(a, b, left, right):
    return ''.join(difflib.unified_diff(a.splitlines(True), b.splitlines(True), fromfile=left, tofile=right))


def coverage(g, post):
    if post:
        return {'percent': post.get('added_statement_start_line_coverage_percent'),
                'covered': post.get('covered_added_statement_start_lines'), 'total': post.get('added_statement_start_lines'),
                'method': 'Added Istanbul statement-start lines', 'unmapped': post.get('files_without_coverage_mapping', [])}
    return {'percent': g.get('changed_line_coverage_percent'), 'covered': g.get('changed_covered_lines'),
            'total': g.get('changed_executable_lines'), 'method': 'Added Python executable lines', 'unmapped': []}


def dialogue(directory):
    turns = []
    for t in read(directory / 'turns.json', []):
        prefix = f"{t['index']:03d}-"
        folder = next((directory / 'turns').glob(prefix + '*'), None)
        response = read(folder / 'response.json', {}) if folder else {}
        turns.append({k:t.get(k) for k in ('index', 'role', 'stage', 'model', 'effort', 'seconds', 'usage', 'usage_is_partial', 'estimated_api_cost_usd')} | {
            'response': response, 'artifacts': rel(folder) if folder else None,
            'prompt': text_file(folder / 'prompt.txt') if folder else ''})
    return {'exchanges': read(directory / 'conversation.json', []), 'turns': turns}


def artifacts(directory):
    result = []
    for base, dirs, files in os.walk(directory, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not excluded((Path(base)/d).relative_to(ROOT)) and not (Path(base)/d).is_symlink())
        for name in sorted(files):
            p = Path(base)/name
            if p.is_symlink() or not p.is_file() or excluded(p.relative_to(ROOT)): continue
            result.append({'path': rel(p), 'bytes': p.stat().st_size})
    return result


def actors(row):
    roles = {k:v for k,v in row.get('usage_by_role', {}).items() if k != 'reviewer'}
    return {key:sum(v.get(key, 0) or 0 for v in roles.values()) for key in ('input_tokens','cached_input_tokens','output_tokens','estimated_api_cost_usd')} | {
        'partial':any(v.get('missing_usage_turns') or v.get('partial_usage_turns') for v in roles.values())}


def test_counts(g):
    if 'candidate_test_counts' in g:return g['candidate_test_counts']
    states=[v for x in g.get('candidate_tests',{}).values() for v in (x.get('counts') or {}).get('tests',{}).values()]
    return {k:states.count(k) for k in ('passed','failed','skipped','error')} if states else None


def load_run(directory, task, phase, measured=None):
    r = read(directory/'result.json'); g = r.get('grade') or {}; m = measured or r
    app = task['id'] == 'actual-balance-forecast'
    cont = phase.endswith('continuation')
    post = read(directory/'post-metrics.json', {})
    review = read(directory/('quality-review/result.json' if app else 'context-review/result.json'), {})
    rubric = review if app else review.get('rubric', {})
    usage = actors(r)
    row = {'id': task['id']+'--'+phase+'--'+r['approach'], 'task':task['id'], 'phase':phase,
           'approach':r['approach'], 'status':r['status'], 'error':r.get('error'), 'directory':rel(directory),
           'coverage':coverage(g,post), 'added_tests':len(g.get('candidate_added_tests', {})),
           'added_tests_passed':sum(v=='passed' for v in g.get('candidate_added_tests', {}).values()),
           'regressions':len(g.get('regressions', [])) if g else None, 'quality':rubric,
           'static':post or g.get('static_metrics', {}), 'dialogue':dialogue(directory),
           'audit':rel(APP/'continuation-01/AUDIT.json' if cont else APP/'AUDIT.json' if app else ROOT/'runs/suite/AUDIT.json'),
           'minutes':m.get('cumulative_workflow_minutes') if cont else m.get('workflow_minutes') if app else (r.get('implementation_seconds',0)+r.get('user_simulation_seconds',0))/60,
           'incremental_minutes':m.get('incremental_workflow_minutes'),
           'human_minutes':m.get('cumulative_human_minutes') if cont else m.get('human_minutes') if app else m.get('estimated_human_minutes'),
           'words':m.get('cumulative_user_words') if cont else m.get('user_words'),
           'cost':m.get('cumulative_actor_api_equivalent_usd') if cont else m.get('actor_api_equivalent_usd') if app else usage['estimated_api_cost_usd'],
           'partial':m.get('cumulative_usage_partial') if cont else m.get('usage_partial') if app else usage['partial'],
           'input_tokens':m.get('cumulative_actor_input_tokens') if cont else m.get('actor_input_tokens') if app else usage['input_tokens'],
           'output_tokens':m.get('cumulative_actor_output_tokens') if cont else m.get('actor_output_tokens') if app else usage['output_tokens'],
           'checks':{k:m.get(k) for k in ('build','typecheck','lint')} if app else {},
           'acceptance': {'passed':g.get('fail_to_pass_passed'), 'total':g.get('fail_to_pass_total')} if not app else None,
           'browser':m.get('browser_adjudication'), 'raw_browser':m.get('raw_browser', g.get('browser')) if app else None,
           'fingerprint':r.get('fingerprint'), 'test_counts':test_counts(g),
           'review_cost':m.get('review_api_equivalent_usd') if app else review.get('estimated_api_cost_usd')}
    return row


def collect():
    tasks = read(ROOT/'tasks/suite.json')['tasks']
    app = read(APP/'study.json'); app['task'] = text_file(APP/'task.md'); app['complexity']='large application'; tasks.append(app)
    suite = read(ROOT/'runs/suite/MEASUREMENTS.json')
    rows=[]; refs=[]; inventory=[]
    for task in tasks:
        tid=task['id']; app=tid=='actual-balance-forecast'
        directory=ROOT/'analysis/references'/tid
        reference=read(directory/'result.json')
        if not reference: raise RuntimeError(f'Missing reference measurements: {directory}')
        g=reference['grade']; post=read(directory/'post-metrics.json', {})
        quality=read(directory/('quality-review/result.json' if app else 'context-review/result.json'), {})
        refs.append({'task':tid,'directory':rel(directory),'coverage':coverage(g,post),'quality':quality if app else quality.get('rubric',{}),
                     'added_tests':len(g.get('candidate_added_tests',{})), 'regressions':len(g.get('regressions',[])),
                     'test_counts':test_counts(g), 'static':post or g.get('static_metrics',{}),
                     'checks':{k:g.get(k,{}).get('returncode') for k in ('build','typecheck','lint')} if app else {},
                     'browser':g.get('browser') if app else None})
        reference_tree=directory/'workspace'
        names_ref=code_files(changed(reference_tree))
        tracked_ref=set(git(reference_tree,'ls-files').splitlines())
        base_text={}
        for phase in (['initial','continuation'] if app else ['initial']):
            measurements=read(APP/('continuation-01/MEASUREMENTS.json' if phase=='continuation' else 'MEASUREMENTS.json')) if app else suite
            for approach in APPROACHES:
                if app:
                    run=APP/('continuation-01/runs' if phase=='continuation' else 'runs')/approach
                    m=next(x for x in measurements if x['approach']==approach)
                else:
                    run=ROOT/'runs/suite'/f'{tid}--{approach}--0'
                    m=next(x for x in measurements if x['approach']==approach and x['task']==tid)
                row=load_run(run,task,phase,m); tree=run/'workspace'
                names=sorted(set(names_ref+code_files(changed(tree))))
                files=[]
                for name in names:
                    a=text_file(reference_tree/name); b=text_file(tree/name)
                    if name not in base_text:base_text[name]=git(reference_tree,'show','HEAD:'+name) if name in tracked_ref else ''
                    base=base_text[name]
                    files.append({'name':name,'same':a==b,'reference_diff':diff(base,a,'before/'+name,'reference/'+name),
                                  'candidate_diff':diff(base,b,'before/'+name,'candidate/'+name),
                                  'comparison_diff':diff(a,b,'reference/'+name,'candidate/'+name),
                                  'reference_file':rel(reference_tree/name) if (reference_tree/name).is_file() else None,
                                  'candidate_file':rel(tree/name) if (tree/name).is_file() else None})
                row['code']=files; rows.append(row)
        inventory += artifacts(directory)
        inventory += artifacts(ROOT/'analysis/repositories'/tid)
    for directory in [ROOT/'runs/suite',APP]:
        inventory += artifacts(directory)
    # The application tree includes its continuation. Deduplicate by portable path.
    inventory={x['path']:x for x in inventory}
    for folder in ['approach_eval','reporting','scripts','docs','tasks','tests']:
        for x in artifacts(ROOT/folder): inventory[x['path']]=x
    for name in ['README.md','evaluation.json','requirements.lock','pyproject.toml']:
        p=ROOT/name;inventory[name]={'path':name,'bytes':p.stat().st_size}
    sources=[]
    for p in [ROOT/'tasks/suite.json',ROOT/'evaluation.json',ROOT/'runs/suite/MEASUREMENTS.json',APP/'MEASUREMENTS.json',APP/'continuation-01/MEASUREMENTS.json']:
        sources.append({'path':rel(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    return {'schema_version':1,'generated_at':datetime.now(timezone.utc).isoformat(),'tasks':tasks,'runs':rows,'references':refs,'artifacts':list(inventory.values()),'sources':sources,
            'methodology':{'model':'gpt-5.6-luna','user_effort':'medium','agent_effort':'xhigh',
                           'human_proxy':'Read 200 words/min + write 40 words/min + 20 seconds/interaction. Visible summaries only; excludes full code/spec review.',
                           'cost':'Pinned 2026-09-09 API-equivalent estimates for user + agent + dispatched workers; reviewer cost separate. Not Codex subscription billing. Partial values are lower bounds.',
                           'time':'Library workflow = recorded implementation + simulated-user seconds. Application workflow excludes setup and grading. Continuation values are cumulative; extra time shown separately.'}}


def append_budget_continuations(data):
    """Import optional follow-ups; calibration remains an explicitly separate phase."""
    study=ROOT/'studies/library-continuation-01'
    measurements=read(study/'MEASUREMENTS.json')
    if not measurements:return data
    for m in measurements:
        task=next(t for t in data['tasks'] if t['id']==m['task'])
        for ancestor in m.get('source_lineage',[]):data['artifacts']+=artifacts(ROOT/ancestor)
        reference=ROOT/'analysis/references'/task['id']/'workspace'
        tracked=set(git(reference,'ls-files').splitlines())
        runs=[(ROOT/m['directory'],'calibration-continuation' if m['kind']=='calibration' else 'continuation',m)]
        if m['kind']=='calibration':runs.insert(0,(ROOT/m['source'],'calibration-initial',None))
        for directory,phase,metrics in runs:
            row=load_run(directory,task,phase,metrics)
            row['continuation_product_changes']=m.get('product_files_changed_during_continuation',[]);row['cohort']=m['kind'];row['source_lineage']=m.get('source_lineage',[]);row['audit']=rel(study/'AUDIT.json')
            tree=directory/'workspace';files=[]
            for name in sorted(set(code_files(changed(reference))+code_files(changed(tree)))):
                a=text_file(reference/name);b=text_file(tree/name)
                base=git(reference,'show','HEAD:'+name) if name in tracked else ''
                files.append({'name':name,'same':a==b,'reference_diff':diff(base,a,'before/'+name,'reference/'+name),
                    'candidate_diff':diff(base,b,'before/'+name,'candidate/'+name),'comparison_diff':diff(a,b,'reference/'+name,'candidate/'+name),
                    'reference_file':rel(reference/name) if (reference/name).is_file() else None,
                    'candidate_file':rel(tree/name) if (tree/name).is_file() else None})
            row['code']=files;data['runs'].append(row)
            data['artifacts']+=artifacts(directory)
    data['artifacts']+=artifacts(study)
    data['artifacts']=list({x['path']:x for x in data['artifacts']}.values())
    p=study/'MEASUREMENTS.json';data['sources'].append({'path':rel(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    return data


def render(data, output):
    output.mkdir(parents=True, exist_ok=True)
    (output/'data.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    payload=json.dumps(data,ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    template=(Path(__file__).parent/'template.html').read_text()
    root_relative=os.path.relpath(ROOT,output).replace(os.sep,'/')
    html=template.replace('__ARTIFACT_ROOT__',quote(root_relative,safe='/.' )).replace('__REPORT_DATA__',payload)
    (output/'index.html').write_text(html)
    return output/'index.html'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from-data',type=Path,help='Rebuild offline without Git, tests, models or absolute host paths')
    parser.add_argument('--output',type=Path,default=ROOT/'reports/comparison')
    args=parser.parse_args()
    data=read(args.from_data) if args.from_data else append_budget_continuations(collect())
    print(render(data,args.output.resolve()))


if __name__=='__main__': main()
