"""Assess saved candidates whose original trial ended before code-quality review."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from approach_eval.codex import Codex
from approach_eval.core import CACHE, digest, dump, git
from approach_eval.grading import changes

RUBRICS = ("maintainability", "readability", "test_quality", "performance", "security")
USAGE_KEYS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")


def atomic_dump(path, value):
    temporary = path.with_name(path.name + ".tmp")
    dump(temporary, value)
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    for path in sorted(args.directory.resolve().glob("*/result.json")):
        result = json.loads(path.read_text())
        run = path.parent
        review_path = run / "evaluation/rubric-review.json"
        if review_path.exists() or result.get("grade") is None:
            continue
        manifest = json.loads((run / "manifest.json").read_text())
        task, settings, grade = manifest["task"], manifest["settings"], result["grade"]
        candidate = run / "workspace"
        patch = git(candidate, "diff", "HEAD", "--", *task["source_roots"], "tests")
        for name in changes(candidate):
            if name.startswith(tuple(r + "/" for r in task["source_roots"])) and name not in patch:
                source = candidate / name
                if source.is_file():
                    patch += "\nNEW FILE " + name + "\n" + source.read_text()
        prompt = ("You are an independent code reviewer. Do not modify files or use tools. "
            "Review this task and candidate source diff without reference to any workflow. "
            "Return status done. Your message MUST be a JSON object with keys "
            "maintainability, readability, test_quality, performance, security. Each value "
            "is an object with score (integer 1-5) and evidence (specific short explanation, "
            "including limitations). 1=serious defects, 3=adequate, 5=excellent. Do not claim "
            "runtime performance/security proof from a diff.\nTask:\n" + task["task"] +
            "\nCandidate diff:\n" + patch + "\nMeasured tests:\n" + json.dumps({k: grade[k] for k in
                ("hidden_counts", "candidate_test_counts", "candidate_added_tests", "changed_line_coverage_percent", "regressions")}))
        output = run / "supplemental-review"
        if output.exists():
            raise SystemExit(f"Incomplete supplemental review already exists: {output}; inspect it before retrying.")
        client = Codex(output, settings)
        workspace = CACHE / "review-contexts" / digest(str(output))[:24]
        workspace.mkdir(parents=True, exist_ok=True)
        print("Supplemental review:", run.name, flush=True)
        _, response = client.call("reviewer", workspace, prompt, stage="blind-review", read_only=True)
        rubric = json.loads(response["message"])
        for key in RUBRICS:
            assert type(rubric[key]["score"]) is int and 1 <= rubric[key]["score"] <= 5
            assert isinstance(rubric[key]["evidence"], str)
        dump(run / "result-before-supplemental-review.json", result)
        usage = result["usage_by_role"]["reviewer"]
        for turn in client.turns:
            for key in USAGE_KEYS:
                usage[key] += (turn["usage"] or {}).get(key, 0)
            for key, increment in (
                ("missing_usage_turns", turn["usage"] is None),
                ("partial_usage_turns", turn.get("usage_is_partial", False)),
                ("unrecovered_missing_usage_turns", turn["usage"] is None and not turn.get("recovered", False))):
                usage[key] = usage.get(key, 0) + int(increment)
            usage["estimated_api_cost_usd"] += turn["estimated_api_cost_usd"] or 0
        result["supplemental_review"] = dict(seconds=sum(t["seconds"] for t in client.turns),
            transcript=str(output), note="Post-trial assessment; original workflow status and wall time retained. Cost and usage include this assessment.")
        result["review_context_anonymous"] = True
        atomic_dump(review_path, rubric)
        atomic_dump(path, result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
