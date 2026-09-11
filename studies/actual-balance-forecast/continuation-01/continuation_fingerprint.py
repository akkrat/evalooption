import hashlib
import json
from pathlib import Path

from app_fingerprint import fingerprint as original_fingerprint
from approach_eval.core import ROOT, digest

HERE = Path(__file__).resolve().parent


def fingerprint(settings):
    value = original_fingerprint(settings)["inputs"]
    value["continuation"] = {
        "kind": "additional budget; resumed original sessions in copied checkouts",
        "original_schedule": json.loads((HERE.parent / "schedule.json").read_text())["fingerprint"]["sha256"],
    }
    for name in (
        "continuation_codex.py", "continue_runner.py", "continuation_fingerprint.py",
        "run_continuation.py", "preflight_resume.py", "test_continuation.py", "PROTOCOL.md",
    ):
        p = HERE / name
        value["files"][str(p.relative_to(ROOT))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return {"sha256": digest(value), "inputs": value}
