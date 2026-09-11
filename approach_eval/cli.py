from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import datetime
import json
from pathlib import Path
import random
import shutil
import sys

from .core import ROOT, CACHE, PYTHON, checked, config, digest, dump, tasks, fingerprint
from .grading import validate_task
from .runner import run_one
from .workflows import APPROACHES


def report(directory):
    directory = Path(directory)
    results = [json.loads(p.read_text()) for p in sorted(directory.glob("*/result.json"))]
    lines = ["# Coding approach evaluation", "", "Model: gpt-5.6-luna; user medium; agents/reviewer xhigh.", "",
             "Costs are API-equivalent estimates; human minutes are a prose/decision proxy. Missing or failed runs remain visible.", "",
             "| Task | Approach | Status | Fixed tests | New regressions | Changed-line coverage | User words | Est. human min | Wall min | Est. API $ |",
             "|---|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for r in results:
        grade = r.get("grade") or {}
        coverage = grade.get("changed_line_coverage_percent")
        money = sum(v["estimated_api_cost_usd"] for v in r["usage_by_role"].values())
        missing_usage = any(v["missing_usage_turns"] or v.get("partial_usage_turns", 0) for v in r["usage_by_role"].values())
        lines.append(f"| {r['task']} | {r['approach']} | {r['status']} | "
                     f"{grade.get('fail_to_pass_passed', '?')}/{grade.get('fail_to_pass_total', '?')} | "
                     f"{len(grade['regressions']) if 'regressions' in grade else '?'} | "
                     f"{f'{coverage:.1f}%' if coverage is not None else 'n/a'} | {r['user_words']} | "
                     f"{r['estimated_human_minutes']:.1f} | {r['elapsed_seconds']/60:.1f} | "
                     f"{'partial ' if missing_usage else ''}{money:.4f} |")
    lines += ["", "## Interpretation", "",
              "Compare success and regressions before effort/cost. One run on three small-library tasks is a smoke benchmark, not a statistically supported ranking. Historical public fixes can be present in model training data even though runtime access is blocked.", "",
              "Quality judgments are in each run's evaluation/rubric-review.json, with evidence. Raw CLI events, prompts, thread IDs, conversations, candidate patches, JUnit results, and coverage are retained per run.", ""]
    for r in results:
        if r.get("error"):
            lines += [f"- {r['task']} / {r['approach']}: {r['error']}"]
    (directory / "REPORT.md").write_text("\n".join(lines) + "\n")
    dump(directory / "results.json", results)
    return directory / "REPORT.md"


def main():
    parser = argparse.ArgumentParser(description="Replay historical tasks through Codex coding approaches")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="Verify original tests fail before and pass after each fix")
    sub.add_parser("doctor", help="Check dependencies and task validation without model calls")
    pilot = sub.add_parser("pilot", help="Run every approach on one seeded-random task")
    pilot.add_argument("--output", type=Path, default=ROOT / "runs/pilot")
    pilot.add_argument("--approaches", nargs="+", choices=APPROACHES, default=list(APPROACHES))
    pilot.add_argument("--jobs", type=int, default=1)
    pilot.add_argument("--recover-from", type=Path, help="Continue pilot artifacts after interruption; calibration only, never a fresh benchmark")
    suite = sub.add_parser("suite", help="Run full matrix only after a successful pilot gate")
    suite.add_argument("--pilot", type=Path, default=ROOT / "runs/pilot")
    suite.add_argument("--output", type=Path, default=ROOT / "runs/suite")
    suite.add_argument("--jobs", type=int, default=1)
    sub.add_parser("list")
    rep = sub.add_parser("report")
    rep.add_argument("directory", type=Path)
    args = parser.parse_args()
    settings = config()
    if args.command == "list":
        for t in tasks():
            print(t["id"], t["complexity"], t["source_url"])
    elif args.command == "doctor":
        checks = {"checkout_under_home": ROOT.resolve().is_relative_to(Path.home().resolve()),
                  "python": PYTHON.exists(), "codex": shutil.which("codex") is not None,
                  "openspec": (CACHE / "tooling/node_modules/.bin/openspec").exists(),
                  "gennady": (CACHE / "tooling/node_modules/.bin/gennady").exists()}
        for t in tasks():
            path = CACHE / "validation-v2" / t["id"] / "validation.json"
            checks[t["id"]] = path.exists() and json.loads(path.read_text())["valid"]
        print(json.dumps(checks, indent=2))
        return int(not all(checks.values()))
    elif args.command == "validate":
        for task in tasks():
            destination = CACHE / "validation-v2" / task["id"]
            if destination.exists():
                print(task["id"], "already validated; see", destination / "validation.json")
                continue
            value = validate_task(task, destination)
            print(task["id"], "VALID" if value["valid"] else "INVALID", len(value["fail_to_pass"]))
            if not value["valid"]:
                return 1
    elif args.command == "pilot":
        task = random.Random(settings["seed"]).choice(tasks())
        args.output.mkdir(parents=True, exist_ok=True)
        if args.jobs < 1:
            raise SystemExit("--jobs must be positive")
        chosen = dict(task=task["id"], seed=settings["seed"], jobs=args.jobs, sampling="Python random.Random(seed).choice in manifest order")
        dump(args.output / "selection.json", chosen)
        def pilot_arm(approach):
            destination = args.output / (task["id"] + "--" + approach)
            if (destination / "result.json").exists():
                r = json.loads((destination / "result.json").read_text())
                if r.get("fingerprint") != fingerprint(settings):
                    raise SystemExit("Cached pilot arm is stale; use a new --output directory.")
            else:
                recovery = args.recover_from / destination.name if args.recover_from else None
                r = run_one(task, approach, destination, settings, recover_from=recovery)
            return r
        results = []
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            for r in pool.map(pilot_arm, args.approaches):
                results.append(r)
                report(args.output)
        # Pilot is a protocol/instrumentation gate, not a correctness filter:
        # an approach may fail the task legitimately. All arms must have run.
        passed = (set(r["approach"] for r in results) == set(APPROACHES)
                  and all(r["status"] in ("completed", "agent_blocked", "budget_exhausted") and r["grade"] is not None for r in results)
                  and all(not v.get("unrecovered_missing_usage_turns", v["missing_usage_turns"]) for r in results for v in r["usage_by_role"].values()))
        dump(args.output / "gate.json", dict(passed=passed, fingerprint=fingerprint(settings),
             recovered_from=str(args.recover_from) if args.recover_from else None, **chosen))
        print("Pilot gate:", "PASS" if passed else "FAIL", flush=True)
        return 0 if passed else 1
    elif args.command == "suite":
        gate = json.loads((args.pilot / "gate.json").read_text())
        if not gate["passed"] or gate["fingerprint"] != fingerprint(settings):
            raise SystemExit("Pilot gate missing, failed, or stale. Run the pilot on this configuration first.")
        if args.jobs < 1:
            raise SystemExit("--jobs must be positive")
        args.output.mkdir(parents=True, exist_ok=True)
        matrix = [(t, a, repeat) for repeat in range(settings["repeats"]) for t in tasks() for a in APPROACHES]
        random.Random(settings["seed"]).shuffle(matrix)
        dump(args.output / "schedule.json", dict(pilot=gate, jobs=args.jobs,
             runs=[dict(task=t["id"], approach=a, repeat=r) for t, a, r in matrix]))
        def execute(item):
            t, a, repeat = item
            destination = args.output / f"{t['id']}--{a}--{repeat}"
            if (destination / "result.json").exists():
                cached = json.loads((destination / "result.json").read_text())
                if cached.get("fingerprint") != fingerprint(settings):
                    raise RuntimeError("Cached suite run is stale; use a new --output directory")
                return cached
            return run_one(t, a, destination, settings)
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            for result in pool.map(execute, matrix):
                report(args.output)
        print(report(args.output))
    elif args.command == "report":
        print(report(args.directory))
    return 0


if __name__ == "__main__":
    sys.exit(main())
