"""Application replay, independently preserved regressions, and browser grading."""
from runtime import *
from isolation import sandbox
from approach_eval.core import snapshot,git,digest
from approach_eval.grading import changes
import signal,time,re,hashlib

SPEC=json.loads((STUDY/'study.json').read_text())
REPO=CACHE/'actual-forecast.git'
FEATURE_TESTS=[
 'packages/loot-core/src/server/forecast/forecast.test.ts',
 'packages/desktop-client/src/components/reports/getDashboardWidgetItems.test.ts',
 'packages/desktop-client/src/components/reports/reports/balanceForecastChartData.test.ts']
# Resolve exact historical backend test names, retaining only tests from the PR.
FEATURE_TESTS=[x for x in git(REPO,'diff','--name-only',SPEC['base_commit'],SPEC['fix_commit']).splitlines()
               if x.endswith(('.test.ts','.test.tsx')) and '/e2e/' not in x]

def prepare(tree, revision=None):
    snapshot(REPO,revision or SPEC['base_commit'],tree)
    clone_dependencies(tree)
    initialize_snapshot(tree)

def tests(tree, output, selected=None, coverage=False):
    output=Path(output);result={}
    for name,workspace,script,package in [('core','@actual-app/core','test:node','loot-core'),('web','@actual-app/web','test','desktop-client')]:
        folder=output/name;folder.mkdir(parents=True,exist_ok=True)
        targets=[x.split('/'+package+'/',1)[1] for x in selected or [] if '/'+package+'/' in x]
        if selected is not None and not targets:continue
        args=['workspace',workspace,'run',script,*targets,'--maxWorkers=2','--reporter=json','--outputFile='+str(folder/'vitest.json')]
        if coverage:args+=['--coverage','--coverage.include=src/**','--coverage.reporter=json','--coverage.reporter=json-summary','--coverage.reportsDirectory='+str(folder/'coverage')]
        run=yarn(tree,args,folder,1200)
        result[name]=dict(command=run,counts=test_counts(folder/'vitest.json') if (folder/'vitest.json').exists() else None)
    dump(output/'result.json',result);return result

def statuses(result):
    return {key:value for run in result.values() for key,value in (run.get('counts') or {}).get('tests',{}).items()}

def browser_check(tree,output):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    for name in ('serve.mjs','browser_check.mjs'):shutil.copy2(STUDY/name,output/name)
    env=environment(tree);env['TMPDIR']=str(output/'tmp');Path(env['TMPDIR']).mkdir(exist_ok=True)
    ready=output/'server.json'
    stream=(output/'server.log').open('w')
    argv=sandbox([NODE,output/'serve.mjs',Path(tree)/'packages/desktop-client/build',0,ready],tree,output,browser=True)
    server=subprocess.Popen(argv,cwd=tree,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
    try:
        for _ in range(100):
            if ready.exists():break
            if server.poll() is not None:raise RuntimeError('Browser server stopped; see '+str(output/'server.log'))
            time.sleep(.05)
        url=json.loads(ready.read_text())['url']
        run=command(sandbox([NODE,output/'browser_check.mjs',tree,url,output],tree,output,browser=True),cwd=tree,env=env,timeout=240)
        (output/'stdout.log').write_text(run.pop('stdout'));(output/'stderr.log').write_text(run.pop('stderr'));dump(output/'command.json',run)
        value=json.loads((output/'result.json').read_text()) if (output/'result.json').exists() else dict(passed=False,checks=[],error='Browser infrastructure failed')
        value['command']=run;dump(output/'result.json',value);return value
    finally:
        if server.poll() is None:
            os.killpg(server.pid,signal.SIGTERM)
            try:server.wait(timeout=5)
            except subprocess.TimeoutExpired:os.killpg(server.pid,signal.SIGKILL);server.wait()
        stream.close()

def overlay_tests(tree):
    for name in FEATURE_TESTS:
        target=Path(tree)/name;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(git(REPO,'show',SPEC['fix_commit']+':'+name))

def replay(candidate,destination,restore_tests=False):
    prepare(destination)
    selected=changes(candidate)
    ignored=[]
    for name in selected:
        # Workflow context contributes to process cost but not the product replay.
        if not (name.startswith(('packages/','bin/')) or '/' not in name):
            ignored.append(name);continue
        if name in ('AGENTS.md','gennady.yaml') or name.startswith('.'):
            ignored.append(name);continue
        parts=Path(name).parts
        if any(x in ('node_modules','.git','build','lib-dist','@types','dist') for x in parts):
            ignored.append(name);continue
        src,dst=Path(candidate)/name,Path(destination)/name
        if src.is_symlink():raise ValueError('Source symlink rejected: '+name)
        if not src.exists():
            if dst.is_file():dst.unlink()
        elif src.is_file():
            dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
    if restore_tests:
        for name in git(REPO,'ls-tree','-r','--name-only',SPEC['base_commit']).splitlines():
            if '.test.' in name or '__snapshots__/' in name or '/mocks/' in name or Path(name).name.startswith(('vitest.','vite.config')):
                dst=Path(destination)/name;dst.parent.mkdir(parents=True,exist_ok=True)
                raw=subprocess.check_output([str(GIT),'show',SPEC['base_commit']+':'+name],cwd=REPO)
                dst.write_bytes(raw)
    return {'changed':selected,'not_replayed':ignored}

def coverage_metrics(tree,output,filenames):
    merged={}
    for cov in Path(output).glob('*/coverage/coverage-final.json'):
        for filename,data in json.loads(cov.read_text()).items():
            path=Path(filename)
            try:key=str(path.relative_to(tree))
            except ValueError:continue
            if key not in filenames or '.test.' in key:continue
            lines=merged.setdefault(key,{})
            for sid,location in data['statementMap'].items():
                for line in range(location['start']['line'],location['end']['line']+1):
                    lines[line]=max(lines.get(line,0),data['s'].get(sid,0))
    covered=sum(v>0 for file in merged.values() for v in file.values());total=sum(map(len,merged.values()))
    return {'changed_file_statement_lines_covered':covered,'changed_file_statement_lines_total':total,
            'changed_file_statement_line_coverage_percent':100*covered/total if total else None,
            'note':'Union of mapped statement lines in changed production files across core/web tests (src/** included, including unexecuted files); not path coverage, and not only newly added lines.'}

def grade(candidate,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    baseline=json.loads((STUDY/'validation/gate.json').read_text())
    own=output/'candidate-tree';mapping=replay(candidate,own)
    original=output/'regression-tree';replay(candidate,original,restore_tests=True)
    own_tests=tests(own,output/'candidate-tests',coverage=True)
    regression=tests(original,output/'original-tests')
    base_pass={k for k,v in baseline['baseline_tests'].items() if v=='passed'}
    regressions=sorted(k for k in base_pass if statuses(regression).get(k)!='passed')
    build=yarn(own,['build:browser','--skip-translations'],output/'build',1200)
    browser=browser_check(own,output/'browser') if build['returncode']==0 else {'passed':False,'checks':[],'error':'Build failed'}
    types=yarn(own,['typecheck'],output/'typecheck',1200)
    lint=yarn(own,['lint'],output/'lint',1200)
    overlay_tests(original);historical=tests(original,output/'historical-compatibility',selected=FEATURE_TESTS)
    added={k:v for k,v in statuses(own_tests).items() if k not in baseline['baseline_tests']}
    value=dict(mapping=mapping,build=build,typecheck=types,lint=lint,browser=browser,
               candidate_tests=own_tests,regression_tests=regression,regressions=regressions,
               candidate_added_tests=added,historical_structure_compatibility=historical,
               coverage=coverage_metrics(own,output/'candidate-tests',mapping['changed']),
               limitation='Historical private-module tests and UI selector compatibility are reported separately; alternative UI failures require review. No Linux pixel snapshot equivalence is claimed.')
    dump(output/'result.json',value);return value
