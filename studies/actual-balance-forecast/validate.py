from adapter import *

def main():
    output=STUDY/'validation/final';output.mkdir(parents=True,exist_ok=True)
    records={}
    for name,tree in [('base',BASE),('gold',GOLD)]:
        folder=output/name;folder.mkdir(exist_ok=True)
        result=tests(tree,folder/'tests',coverage=True)
        build=yarn(tree,['build:browser','--skip-translations'],folder/'build',1200)
        browser=browser_check(tree,folder/'browser') if build['returncode']==0 else {'passed':False,'checks':[]}
        typecheck=yarn(tree,['typecheck'],folder/'typecheck',1200)
        lint=yarn(tree,['lint'],folder/'lint',1200)
        records[name]=dict(tests=result,build=build,browser=browser,typecheck=typecheck,lint=lint)
        dump(folder/'result.json',records[name])
    hidden=output/'base-hidden';prepare(hidden);overlay_tests(hidden)
    compatibility=tests(hidden,output/'base-compatibility',FEATURE_TESTS)
    gold_compatibility=tests(GOLD,output/'gold-compatibility',FEATURE_TESTS)
    preflights=[p for p in (STUDY/'preflight').glob('*/result.json') if json.loads(p.read_text()).get('passed')]
    baseline=statuses(records['base']['tests']);gold=statuses(records['gold']['tests'])
    original_regressions=sorted(k for k,v in baseline.items() if v=='passed' and gold.get(k)!='passed')
    valid=(records['gold']['browser']['passed'] and not records['base']['browser']['passed']
           and not original_regressions and any('build-' in str(p.parent.name) for p in preflights) and any('build-' not in str(p.parent.name) for p in preflights)
           and all(v['build']['returncode']==v['typecheck']['returncode']==v['lint']['returncode']==0 for v in records.values())
           and all(v['command']['returncode']==0 for v in gold_compatibility.values()))
    value=dict(valid=valid,baseline_tests=baseline,gold_tests=gold,original_regressions=original_regressions,
               records=records,base_compatibility=compatibility,gold_compatibility=gold_compatibility,
               preflights=[str(p) for p in preflights],feature_tests=FEATURE_TESTS,
               browser_check_ids=[x['id'] for x in records['gold']['browser']['checks']],
               coverage_provider='@vitest/coverage-v8@4.1.4',reference_provenance=SPEC['reference_provenance'])
    dump(STUDY/'validation/gate.json',value);print('APP VALIDATION GATE',valid,flush=True)
    if valid:
        smoke=grade(BASE,output/'replay-smoke')
        passed=(not smoke['regressions'] and not smoke['browser']['passed'] and
                all(smoke[k]['returncode']==0 for k in ('build','typecheck','lint')) and
                all(x['command']['returncode']==0 for x in smoke['candidate_tests'].values()))
        dump(STUDY/'validation/replay-smoke-gate.json',{'passed':passed,'regressions':smoke['regressions'],'source_changes':smoke['mapping']['changed']})
if __name__=='__main__':main()
