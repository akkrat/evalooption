"""Guarded sequential application study, separate from the frozen library matrix."""
from runtime import *
from approach_eval.core import config,digest
from app_runner import run_one
from adapter import SPEC
from app_fingerprint import fingerprint
import random

def main():
    gate=json.loads((STUDY/'validation/gate.json').read_text())
    if not gate['valid']:raise RuntimeError('Application adapter/protocol gate has not passed')
    smoke=STUDY/'validation/replay-smoke-gate.json'
    if not smoke.exists() or not json.loads(smoke.read_text())['passed']:raise RuntimeError('End-to-end replay grader has not passed')
    settings=config();settings.update(turn_timeout_seconds=1800,max_run_seconds=14400,seed=20260910,concurrency=1)
    settings_path=STUDY/'evaluation.json'
    if settings_path.exists() and json.loads(settings_path.read_text())!=settings:raise RuntimeError('Frozen settings changed')
    dump(settings_path,settings)
    task=dict(id=SPEC['id'],repo='actual-forecast.git',base_commit=SPEC['base_commit'],complexity='large-application',
              project='Actual Budget is a local-first personal finance application using TypeScript, React, and a SQLite backend.',
              task=(STUDY/'task.md').read_text(),source_roots=['packages'],test_targets=[])
    approaches=['prompt','plan','openspec','gennady'];random.Random(settings['seed']).shuffle(approaches)
    runs=STUDY/'runs';runs.mkdir(exist_ok=True)
    frozen=fingerprint(settings)
    schedule=STUDY/'schedule.json'
    if schedule.exists():
        old=json.loads(schedule.read_text())
        if old['fingerprint']!=frozen:raise RuntimeError('Engine changed after freeze')
    else:dump(schedule,dict(approaches=approaches,concurrency=1,fingerprint=frozen,task=task))
    archive=STUDY/'frozen-engine'
    if not archive.exists():
        for name in frozen['inputs']['files']:
            source=ROOT/name;target=archive/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
        dump(archive/'fingerprint.json',frozen)
    state=json.loads((STUDY/'study.json').read_text());state['status']='running';dump(STUDY/'study.json',state)
    for approach in approaches:
        directory=runs/approach
        if (directory/'result.json').exists():continue
        if directory.exists():raise RuntimeError('Incomplete trial exists; inspect before resuming, never silently restart')
        print('START APPLICATION',approach,flush=True)
        run_one(task,approach,directory,settings)
    state['status']='matrix-recorded';dump(STUDY/'study.json',state)
    print('APPLICATION MATRIX RECORDED',flush=True)
if __name__=='__main__':main()
