"""Resume all four original application workflows; never overwrite prior results."""
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from runtime import ROOT, dump
from app_fingerprint import fingerprint as original_fingerprint
from continuation_fingerprint import fingerprint
from continue_runner import run_one


def main():
    original = HERE.parent
    schedule = json.loads((original / "schedule.json").read_text())
    previous_settings = json.loads((original / "evaluation.json").read_text())
    assert original_fingerprint(previous_settings) == schedule["fingerprint"]
    assert json.loads((HERE / "preflight/gate.json").read_text())["passed"]
    settings = dict(previous_settings)
    settings.update(turn_timeout_seconds=3600, max_questions_per_stage=32,
                    max_run_seconds=14400, max_run_tokens=80000000)
    frozen = fingerprint(settings)
    state = HERE / "schedule.json"
    if state.exists():
        assert json.loads(state.read_text())["fingerprint"] == frozen
    else:
        dump(state, {"approaches": schedule["approaches"], "settings": settings,
                     "fingerprint": frozen, "original_schedule": str(original / "schedule.json"),
                     "kind": "continuation; additional measurements, not fresh trials"})
        archive = HERE / "frozen-engine"
        for name in frozen["inputs"]["files"]:
            target = archive / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        dump(archive / "fingerprint.json", frozen)
    dump(HERE / "state.json", {"status": "running", "reset_credit_used": False})
    for approach in schedule["approaches"]:
        directory = HERE / "runs" / approach
        if (directory / "result.json").exists():
            continue
        if directory.exists():
            raise RuntimeError("Incomplete continuation requires inspection: " + str(directory))
        print("CONTINUE APPLICATION", approach, flush=True)
        run_one(schedule["task"], approach, directory, settings,
                recover_from=original / "runs" / approach)
    dump(HERE / "state.json", {"status": "matrix-recorded", "recorded_results": 4,
                               "reset_credit_used": False})
    print("APPLICATION CONTINUATION RECORDED", flush=True)


if __name__ == "__main__":
    main()
