"""Measure reference solutions separately; never modify completed study evidence."""
import argparse
import json
import hashlib
import re
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from approach_eval.core import CACHE, config, dump, git, init_snapshot, snapshot, tasks
from approach_eval.grading import grade


def prepare(task, repo, out):
    tree = out / 'workspace'
    if tree.exists():
        raise RuntimeError(f'Partial reference measurement exists: {out}; inspect before retrying')
    snapshot(repo, task['base_commit'], tree)
    init_snapshot(tree)
    patch = subprocess.check_output(['git', 'diff', '--binary', task['base_commit'], task['fix_commit']], cwd=repo)
    (out / 'reference.patch').write_bytes(patch)
    subprocess.run(['git', 'apply', '--binary', '-'], cwd=tree, input=patch, check=True)
    return tree


def library(task, out):
    if not (out / 'result.json').exists():
        tree = prepare(task, CACHE / task['repo'], out)
        validation = json.loads((CACHE / 'validation-v2' / task['id'] / 'validation.json').read_text())
        measured = grade(task, tree, out / 'evaluation', validation)
        dump(out / 'result.json', {'task': task['id'], 'status': 'reference', 'grade': measured})
        dump(out / 'manifest.json', {'task': task, 'settings': config(), 'kind': 'post-study reference analysis'})
    sys.path.insert(0, str(ROOT / 'scripts'))
    from review_context import assess
    assess(out / 'result.json')


def application(out):
    study = ROOT / 'studies/actual-balance-forecast'
    sys.path.insert(0, str(study))
    from adapter import tests, statuses, coverage_metrics
    from runtime import clone_dependencies
    from finish_app import review
    from approach_eval.grading import changes
    task = json.loads((study / 'study.json').read_text())
    if not (out / 'result.json').exists():
        tree = prepare(task, CACHE / 'actual-forecast.git', out)
        clone_dependencies(tree)
        own = tests(tree, out / 'evaluation/candidate-tests', coverage=True)
        before = json.loads((study / 'validation/final/base/result.json').read_text())
        original = json.loads((study / 'validation/final/gold/result.json').read_text())
        baseline, after = statuses(before['tests']), statuses(own)
        measured = {k: original[k] for k in ('build', 'typecheck', 'lint', 'browser')}
        measured.update(candidate_added_tests={k:v for k,v in after.items() if k not in baseline},
                        regressions=[k for k,v in baseline.items() if v == 'passed' and after.get(k) != 'passed'],
                        candidate_tests=own, coverage=coverage_metrics(tree, out / 'evaluation/candidate-tests', changes(tree)),
                        limitation='Reference coverage rerun post-study with src/** included, same candidate test adapter. Build/type/lint/browser reused from frozen reference validation. Historical tests are its own tests, not independent acceptance evidence.')
        dump(out / 'result.json', {'task': task['id'], 'status': 'reference', 'grade': measured})
        dump(out / 'manifest.json', {'task': task, 'settings': config(), 'kind': 'post-study reference analysis'})
    reference_coverage(out)
    review(out)


def reference_coverage(out):
    """Same added statement-start definition, with explicit reference workspace mapping."""
    from approach_eval.grading import changes
    tree=out/'workspace';names=changes(tree)
    production=[n for n in names if n.startswith('packages/') and '/src/' in n and '.test.' not in n and Path(n).suffix in ('.ts','.tsx','.js','.jsx','.mjs')]
    untracked=set(git(tree,'ls-files','--others','--exclude-standard').splitlines());added={}
    for name in production:
        p=tree/name
        if not p.is_file():continue
        if name in untracked:added[name]=set(range(1,len(p.read_text().splitlines())+1));continue
        lines=set()
        for match in re.finditer(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@',git(tree,'diff','--unified=0','HEAD','--',name),re.M):
            start,count=int(match[1]),int(match[2] or 1);lines.update(range(start,start+count))
        added[name]=lines
    mapped={}
    for p in (out/'evaluation/candidate-tests').glob('*/coverage/coverage-final.json'):
        for filename,data in json.loads(p.read_text()).items():
            try:name=str(Path(filename).relative_to(tree))
            except ValueError:continue
            if name not in added:continue
            counts=mapped.setdefault(name,{})
            for sid,span in data.get('statementMap',{}).items():
                line=span['start']['line'];counts[line]=max(counts.get(line,0),data['s'].get(sid,0))
    selected={n:{line:count for line,count in values.items() if line in added[n]} for n,values in mapped.items()}
    total=sum(map(len,selected.values()));covered=sum(v>0 for values in selected.values() for v in values.values())
    dump(out/'post-metrics.json',{'method_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'changed_production_files':len(production),'changed_test_files':sum('.test.' in n or '/e2e/' in n for n in names),
        'changed_documentation_files':sum(n.endswith('.md') for n in names),'added_production_text_lines':sum(map(len,added.values())),
        'added_statement_start_lines':total,'covered_added_statement_start_lines':covered,
        'added_statement_start_line_coverage_percent':100*covered/total if total else None,
        'files_without_coverage_mapping':[n for n in production if n not in mapped],
        'definition':'Same distinct added Istanbul statement-start line definition as application candidates; explicit reference workspace path mapping. Full core/web src/** coverage rerun after study.'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task', default='all')
    args = parser.parse_args()
    for task in tasks():
        if args.task in ('all', task['id']):
            print('Reference:', task['id'], flush=True)
            library(task, ROOT / 'analysis/references' / task['id'])
    if args.task in ('all', 'actual-balance-forecast'):
        print('Reference: actual-balance-forecast', flush=True)
        application(ROOT / 'analysis/references/actual-balance-forecast')


if __name__ == '__main__':
    main()
