"""Exercise the actual Codex sandbox/runtime before paying for a full pilot."""
import datetime
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from approach_eval.core import ROOT, PYTHON, config, dump, init_snapshot, fingerprint
from approach_eval.codex import Codex


def main():
    output = ROOT / ".eval-cache" / ("preflight-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    workspace = output / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "sample.py").write_text("VALUE = 1\n")
    (workspace / "test_sample.py").write_text("from sample import VALUE\ndef test_value():\n    assert VALUE == 1\n")
    gate = [str(PYTHON), "-m", "pytest", "-q", "-c", "/dev/null", "--rootdir=.", "--confcutdir=.", "-p", "no:cacheprovider", "test_sample.py"]
    (workspace / "gennady.yaml").write_text("stack:\n  use: [anystack]\n  anystack:\n    extraGates:\n      - id: tests\n        argv: " + json.dumps(gate) + "\n")
    init_snapshot(workspace)
    script = '''import pathlib, subprocess, sys
print("PYTHON", sys.executable)
for argv in (["node", "--version"], ["git", "status", "--short"], ["openspec", "--version"], ["gennady", "--help"]):
    result = subprocess.run(argv, text=True, capture_output=True)
    print(argv[0], result.returncode, result.stdout[:180], result.stderr)
    assert result.returncode == 0 and not result.stderr
result = subprocess.run([__SDD_PATH__, "verify", "--wip", "sample.py"], text=True, capture_output=True)
print("SDD_VERIFY", result.returncode, result.stdout, result.stderr)
assert result.returncode == 0
assert not pathlib.Path(".git/gennady-verify.lock").exists()
try:
    pathlib.Path(".git/forbidden-probe").write_text("BAD")
except PermissionError:
    print("GIT_METADATA_WRITE_DENIED")
else:
    raise AssertionError("Unrelated Git metadata write was allowed")
try:
    pathlib.Path("sample.py").write_text("BAD")
except PermissionError:
    print("SOURCE_WRITE_DENIED")
else:
    raise AssertionError("Source write was allowed")
try:
    pathlib.Path(__HIDDEN_PATH__).read_text()
except PermissionError:
    print("HIDDEN_READ_DENIED")
else:
    raise AssertionError("Hidden read was allowed")
pathlib.Path(".workflow").mkdir(exist_ok=True)
pathlib.Path(".workflow/preflight.md").write_text("ARTIFACT_WRITE_ALLOWED")
print("PREFLIGHT_PASS")
'''.replace("__HIDDEN_PATH__", repr(str(ROOT / "tasks/suite.json"))).replace("__SDD_PATH__", repr(str(ROOT / ".eval-cache/tooling/node_modules/gennady/ai/skills/sdd-execute/scripts/sdd")))
    settings = config()
    client = Codex(output / "transcript", settings)
    _, response = client.call("agent", workspace,
        "Execute this exact Python script using your shell. Do not modify it, repair the environment, or dispatch. Report exact output.\n" + script,
        stage="preflight", artifact_only=True)
    events = [json.loads(line) for line in (output / "transcript/turns/000-agent-preflight/events.jsonl").read_text().splitlines()]
    actual = [e["item"].get("aggregated_output", "") for e in events if e.get("type") == "item.completed"
              and e.get("item", {}).get("type") == "command_execution" and e["item"].get("exit_code") == 0]
    passed = (any(all(marker in text for marker in ("PREFLIGHT_PASS", "SOURCE_WRITE_DENIED", "HIDDEN_READ_DENIED", "GIT_METADATA_WRITE_DENIED", "SDD_VERIFY 0")) for text in actual)
              and (workspace / "sample.py").read_text() == "VALUE = 1\n"
              and (workspace / ".workflow/preflight.md").read_text() == "ARTIFACT_WRITE_ALLOWED")
    dump(output / "result.json", dict(passed=passed, fingerprint=fingerprint(settings), response=response))
    print("PREFLIGHT", "PASS" if passed else "FAIL", output)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
