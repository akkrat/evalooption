"""Uniform post-trial review with baseline failures and complete changed source files."""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from approach_eval.codex import Codex
from approach_eval.core import CACHE, digest, dump, git
from approach_eval.grading import changes

RUBRICS = ("maintainability", "readability", "test_quality", "performance", "security")


def assess(path):
    run = path.parent
    output = run / "context-review"
    if (output / "result.json").exists():
        return
    if output.exists():
        raise RuntimeError(f"Unfinished review exists at {output}; inspect before retrying.")
    result = json.loads(path.read_text())
    manifest = json.loads((run / "manifest.json").read_text())
    task, settings = manifest["task"], manifest["settings"]
    grade = result.get("grade")
    if grade is None:
        dump(output / "result.json", {"status": "unavailable", "reason": "No independently graded candidate."})
        return
    candidate = run / "workspace"
    validation = json.loads((CACHE / "validation-v2" / task["id"] / "validation.json").read_text())
    baseline = validation["baseline"]
    patch = git(candidate, "diff", "HEAD", "--", *task["source_roots"], "tests")
    tracked = set(git(candidate, "ls-files").splitlines())
    context = []
    for name in changes(candidate):
        file = candidate / name
        source = name.startswith(tuple(root + "/" for root in task["source_roots"]))
        if file.is_file() and (source or (name.startswith("tests/") and name not in tracked)):
            context.append("FILE " + name + "\n" + file.read_text(errors="replace"))
    evidence = {k: grade[k] for k in ("hidden_counts", "candidate_test_counts", "candidate_added_tests",
                                    "changed_line_coverage_percent", "regressions")}
    evidence["baseline_counts"] = baseline["counts"]
    evidence["baseline_nonpassing"] = {name: state for name, state in baseline["tests"].items() if state != "passed"}
    prompt = (
        "You are an independent code reviewer. Do not modify files or use tools. "
        "Review the task, candidate diff, complete changed source files, newly added test files, and measured outcomes. "
        "The baseline outcomes were measured BEFORE this candidate: do not attribute pre-existing failures to this change. "
        "Unchanged behavior can satisfy a requirement; inspect the complete source before inferring that behavior is absent. "
        "Separate demonstrated defects from uncertainty or missing evidence. Hidden-test success is not proof of complete correctness. "
        "Return status done. Your message MUST be a JSON object with keys maintainability, readability, test_quality, "
        "performance, security. Each value is an object with score (integer 1-5) and evidence (specific short explanation "
        "with limitations). 1=serious defects, 3=adequate, 5=excellent. Do not claim runtime performance/security proof "
        "from source inspection.\nTask:\n" + task["task"] + "\nCandidate diff:\n" + patch +
        "\nCandidate source context:\n" + "\n\n".join(context) + "\nMeasured outcomes:\n" + json.dumps(evidence))
    client = Codex(output, settings)
    workspace = CACHE / "review-contexts" / digest(str(output))[:24]
    workspace.mkdir(parents=True, exist_ok=True)
    print("Context review:", run.name, flush=True)
    started = time.monotonic()
    try:
        _, response = client.call("reviewer", workspace, prompt, stage="context-review", read_only=True)
        rubric = json.loads(response["message"])
        for key in RUBRICS:
            assert type(rubric[key]["score"]) is int and 1 <= rubric[key]["score"] <= 5
            assert isinstance(rubric[key]["evidence"], str)
        record = {"status": "completed", "rubric": rubric}
    except Exception as exc:
        record = {"status": "error", "error": str(exc)}
    record.update(protocol="baseline-context-v2", seconds=time.monotonic() - started,
                  model=settings["model"], effort=settings["agent_effort"],
                  estimated_api_cost_usd=sum(t.get("estimated_api_cost_usd") or 0 for t in client.turns),
                  usage_is_partial=any(t.get("usage_is_partial") or t.get("usage") is None for t in client.turns),
                  note="Uniform post-trial assessment; original workflow outcomes and first reviews preserved.")
    dump(output / "result.json", record)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--follow", action="store_true", help="Wait for scheduled trials to produce their results.")
    args = parser.parse_args()
    directory = args.directory.resolve()
    schedule = json.loads((directory / "schedule.json").read_text())["runs"]
    deadline = time.monotonic() + 4 * 60 * 60
    while True:
        paths = sorted(directory.glob("*/result.json"))
        for path in paths:
            assess(path)
        if not args.follow or len(paths) == len(schedule):
            break
        if time.monotonic() > deadline:
            raise SystemExit("Timed out waiting for remaining trial results.")
        time.sleep(10)
    records = [json.loads(p.read_text()) for p in directory.glob("*/context-review/result.json")]
    print(f"Context reviews: {sum(r['status']=='completed' for r in records)}/{len(records)} completed.", flush=True)
    return int(any(r["status"] == "error" for r in records))


if __name__ == "__main__":
    sys.exit(main())
