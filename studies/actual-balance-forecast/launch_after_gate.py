from runtime import *
import time
from run_study import main
p=STUDY/'validation/replay-smoke-gate.json'
for _ in range(300):
    if p.exists():break
    time.sleep(2)
else:raise RuntimeError('Timed out waiting for replay validation; no trials launched')
if not json.loads(p.read_text())['passed']:raise RuntimeError('Replay smoke failed')
main()
