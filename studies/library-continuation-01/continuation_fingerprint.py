import hashlib
from pathlib import Path
from approach_eval.core import ROOT,digest,fingerprint as original_fingerprint
HERE=Path(__file__).resolve().parent

def fingerprint(settings):
    names=['continuation_codex.py','continue_runner.py','recovery.py','continuation_fingerprint.py','run_continuation.py','preflight.py','test_recovery.py','PROTOCOL.md']
    value={'settings':settings,'original_engine':original_fingerprint(settings),
           'files':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [*(HERE/n for n in names),*(ROOT/'approach_eval').glob('*.py'),ROOT/'tasks/workflows.lock.json',ROOT/'tasks/suite.json',ROOT/'requirements.lock']}}
    return {'sha256':digest(value),'inputs':value}
