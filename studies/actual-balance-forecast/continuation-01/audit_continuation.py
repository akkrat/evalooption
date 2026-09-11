"""Consistency audit for the continuation and preservation of original evidence."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from runtime import dump, GIT
from adjudicate import source_digest
from continuation_fingerprint import fingerprint
from approach_eval.core import git


def audit():
    schedule = json.loads((HERE / "schedule.json").read_text())
    current = fingerprint(schedule["settings"])
    saved = json.loads((HERE / "original-artifacts.json").read_text())
    original_checks = {}
    for key, value in saved.items():
        if isinstance(value, str):
            original_checks[key] = hashlib.sha256((HERE.parent / key).read_bytes()).hexdigest() == value
        else:
            unchanged = source_digest(HERE.parent / "runs" / key / "workspace") == value["workspace"]
            original_checks[key] = unchanged and all(
                (HERE.parent / name).is_file() and hashlib.sha256((HERE.parent / name).read_bytes()).hexdigest() == expected
                for name, expected in value["files"].items())
    rollouts = {p.stem[-36:]: p for p in (Path.home() / ".codex/sessions").rglob("*.jsonl")}
    contexts = {}

    def actual_context(turn, cwd=None):
        sid = turn.get("session")
        if sid not in contexts:
            found = []
            if sid in rollouts:
                for line in rollouts[sid].open():
                    if '"turn_context"' not in line:
                        continue
                    try:
                        e = json.loads(line)
                    except ValueError:
                        continue
                    if e.get("type") == "turn_context":
                        found.append(e["payload"])
            contexts[sid] = found
        relevant = [v for v in contexts[sid] if cwd is None or v.get("cwd") == str(cwd)]
        return bool(relevant) and all(v.get("model") == turn["model"] and v.get("effort") == turn["effort"] for v in relevant)

    trials = []
    for approach in schedule["approaches"]:
        d = HERE / "runs" / approach
        if not (d / "result.json").exists():
            continue
        r = json.loads((d / "result.json").read_text())
        recovery = json.loads((d / "recovery.json").read_text())
        turns = json.loads((d / "turns.json").read_text())
        qa = json.loads((d / "adjudication/summary.json").read_text()) if (d / "adjudication/summary.json").exists() else {}
        qturns = json.loads((d / "quality-review/turns.json").read_text()) if (d / "quality-review/turns.json").exists() else []
        tree = d / "workspace"
        first_agent = next((t for t in turns if t["role"] == "agent"), {})
        first_user = next((t for t in turns if t["role"] == "user"), {})
        tests = {
            "frozen_engine": r["fingerprint"] == current,
            "resumed_original_agent": first_agent.get("session") == recovery["agent_session"],
            "original_developer_when_invoked": not first_user or first_user.get("session") == recovery["user_session"],
            "model_efforts_and_new_cwd": all(t["model"] == "gpt-5.6-luna" and t["effort"] == ("medium" if t["role"] == "user" else "xhigh") and actual_context(t, d / ("user" if t["role"] == "user" else "workspace")) for t in turns),
            "single_snapshot_commit": git(tree, "rev-list", "--count", "HEAD").strip() == "1",
            "no_remotes": not git(tree, "remote").strip(),
            "original_history_absent": subprocess.run([str(GIT), "cat-file", "-e", json.loads((HERE.parent / "study.json").read_text())["base_commit"]], cwd=tree, capture_output=True).returncode != 0,
            "grade_recorded": r.get("grade") is not None,
            "quality_recorded": (d / "quality-review/result.json").exists(),
            "quality_model_effort": bool(qturns) and all(t["model"] == "gpt-5.6-luna" and t["effort"] == "xhigh" and actual_context(t) for t in qturns) or (d / "quality-review/not-applicable.json").exists(),
            "browser_qa_recorded": qa.get("reviewed") is True,
            "qa_sources_unchanged": all(json.loads((d / attempt / "result.json").read_text()).get("source_integrity", {}).get("unchanged") for attempt in qa.get("attempts", [])),
        }
        trials.append({"approach": approach, "status": r["status"], "checks": tests})
    checks = {"original_artifacts_unchanged": original_checks, "frozen_engine": current == schedule["fingerprint"],
              "resume_preflight": json.loads((HERE / "preflight/gate.json").read_text())["passed"],
              "recorded_trials": len(trials), "trials": trials, "reset_credit_used": False}
    checks["passed"] = (all(original_checks.values()) and checks["frozen_engine"] and checks["resume_preflight"] and len(trials) == 4 and all(all(r["checks"].values()) for r in trials))
    dump(HERE / "AUDIT.json", checks)
    print(json.dumps(checks, indent=2))
    return checks


if __name__ == "__main__":
    audit()
