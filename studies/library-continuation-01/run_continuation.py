"""Continue the three remaining exhausted runs, preserving their original evidence."""
import hashlib,json,os,shutil,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent
sys.path.insert(0,str(ROOT))
from approach_eval.core import dump
from continuation_fingerprint import fingerprint
from continue_runner import run_one

SOURCES=[('benchmark','runs/suite/boltons-spooled-io--prompt--0'),
         ('benchmark','runs/suite/more-itertools-classify-unique--gennady--0'),
         ('calibration','runs/pilot-v9/boltons-copy-function--gennady')]


def hashes(directory):
    result={}
    for base,dirs,files in os.walk(directory):
        dirs[:]=[d for d in dirs if d not in ('.git','__pycache__','.pytest_cache','.runtime-cache','.runtime-config')]
        for name in files:
            p=Path(base)/name
            if p.is_file() and not p.is_symlink():result[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
    return result


def main():
    assert json.loads((HERE/'preflight/gate.json').read_text())['passed']
    base=json.loads((ROOT/SOURCES[0][1]/'manifest.json').read_text())['settings']
    settings=dict(base,turn_timeout_seconds=3600,max_run_seconds=14400,max_run_tokens=80000000,max_questions_per_stage=32,max_dispatches=64)
    frozen=fingerprint(settings)
    plans=[{'kind':kind,'source':source,'directory':str((HERE/'runs'/Path(source).name).relative_to(ROOT))} for kind,source in SOURCES]
    if (HERE/'schedule.json').exists():
        assert json.loads((HERE/'schedule.json').read_text())['fingerprint']==frozen
    else:
        originals={name:hashes(ROOT/name) for _,name in SOURCES}
        dump(HERE/'original-artifacts.json',originals)
        dump(HERE/'schedule.json',{'settings':settings,'fingerprint':frozen,'runs':plans,'measurement':'incremental continuation; calibration kept separate'})
        for name in frozen['inputs']['files']:
            dest=HERE/'frozen-engine'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,dest)
        dump(HERE/'frozen-engine/fingerprint.json',frozen)
    dump(HERE/'state.json',{'status':'running','reset_credit_used':False})
    sys.path.insert(0,str(ROOT/'scripts'))
    from review_context import assess
    for plan in plans:
        source=ROOT/plan['source'];destination=ROOT/plan['directory']
        if not (destination/'result.json').exists():
            if destination.exists():raise RuntimeError('Inspect incomplete continuation: '+str(destination))
            manifest=json.loads((source/'manifest.json').read_text())
            print('CONTINUE',plan['kind'],source.name,flush=True)
            result=run_one(manifest['task'],manifest['approach'],destination,settings,recover_from=source)
            if result['status']=='harness_error':raise RuntimeError(result['error'])
        assess(destination/'result.json')
    original=json.loads((HERE/'original-artifacts.json').read_text())
    checks={source:hashes(ROOT/source)==expected for source,expected in original.items()}
    audit={'original_artifacts_unchanged':checks,'frozen_engine':fingerprint(settings)==frozen}
    audit['passed']=all(checks.values()) and audit['frozen_engine']
    dump(HERE/'AUDIT.json',audit);assert audit['passed']
    dump(HERE/'state.json',{'status':'complete','recorded_runs':len(plans),'reset_credit_used':False})
    print('CONTINUATIONS AND REVIEWS RECORDED',flush=True)


if __name__=='__main__':main()
