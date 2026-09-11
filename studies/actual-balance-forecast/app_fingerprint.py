import hashlib,json
from runtime import STUDY,ROOT,CACHE
from approach_eval.core import digest

def fingerprint(settings):
    files=[*(STUDY/name for name in ('adapter.py','runtime.py','isolation.py','app_codex.py','app_runner.py','app_workflows.py','app_fingerprint.py','run_study.py','validate.py','preflight.py','preflight_build.py','test_adapter.py','browser_broker.py')),STUDY/'validation/gate.json',STUDY/'validation/replay-smoke-gate.json',STUDY/'serve.mjs',STUDY/'browser_check.mjs',STUDY/'task.md',STUDY/'runtime.json',
           ROOT/'approach_eval/core.py',ROOT/'approach_eval/codex.py',ROOT/'approach_eval/workflows.py',ROOT/'approach_eval/runner.py',
           ROOT/'tasks/workflows.lock.json',CACHE/'actual-instrumentation/yarn.lock',CACHE/'actual-forecast/base/yarn.lock']
    reference=json.loads((STUDY/'study.json').read_text())
    value={'reference':{k:reference[k] for k in ('id','repository','base_commit','fix_commit','reference_provenance')},'settings':settings,'files':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    return {'sha256':digest(value),'inputs':value}
