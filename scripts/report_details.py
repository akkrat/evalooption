"""Produce a comparison across measured results without changing execution state."""
import argparse
import json
from pathlib import Path
import statistics
import re


def visible_prose(conversation):
    """Count agent messages, excluding the simulator's role/stage coaching."""
    if conversation.get("display_version") == "agent-prose-v1":
        return conversation["shown_to_user"]
    if conversation["kind"] == "initial":
        return ""
    message = conversation["shown_to_user"]
    if message.startswith("You are reviewing ONLY the current preparation stage:"):
        message = message.partition("\n\n")[2]
    if conversation["kind"] in ("review", "completion") and message.startswith("Review "):
        message = message.partition("\n")[2]
    return message


def number(value, places=1):
    return "n/a" if value is None else f"{value:.{places}f}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    directory = args.directory.resolve()
    rows = []
    runtimes = set()
    for path in sorted(directory.glob("*/result.json")):
        result = json.loads(path.read_text())
        review_path = path.parent / "evaluation/rubric-review.json"
        result["rubric"] = json.loads(review_path.read_text()) if review_path.exists() else {}
        context_path = path.parent / "context-review/result.json"
        result["context_review"] = json.loads(context_path.read_text()) if context_path.exists() else {}
        context_turns = path.parent / "context-review/turns.json"
        if result["context_review"] and context_turns.exists():
            turns = json.loads(context_turns.read_text())
            result["context_review"]["usage"] = {
                key: sum((turn.get("usage") or {}).get(key, 0) for turn in turns)
                for key in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")}
        result["directory"] = str(path.parent)
        conversation_path = path.parent / "conversation.json"
        conversations = json.loads(conversation_path.read_text()) if conversation_path.exists() else []
        settings = json.loads((path.parent / "manifest.json").read_text())["settings"]
        runtimes.add(f"{settings['model']}: user {settings['user_effort']}; implementers and reviewers {settings['agent_effort']}.")
        result["raw_estimated_human_minutes"] = result["estimated_human_minutes"]
        result["visible_agent_words"] = sum(len(re.findall(r"\S+", visible_prose(c))) for c in conversations)
        proxy = settings["human_time_proxy"]
        result["estimated_human_minutes"] = (result["user_words"] / proxy["write_words_per_minute"]
            + result["visible_agent_words"] / proxy["read_words_per_minute"]
            + result["user_interactions"] * proxy["decision_seconds"] / 60)
        result["measurement_revision"] = "visible-prose-v1"
        rows.append(result)
    text = ["# Evaluation comparison", "", " ".join(sorted(runtimes)) or "No results recorded yet.", "",
            "## Outcomes by approach", "",
            "Each task counts equally. These are descriptive summaries of a small set, not a significance test.", "",
            "| Approach | Finished / attempted | Historical checks satisfied | Mean acceptance % | Mean user words | Mean est. human min | Mean wall min | Total agent API $ | Simulator + first review $ |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    schedule_path = directory / "schedule.json"
    if schedule_path.exists():
        schedule_record = json.loads(schedule_path.read_text())
        schedule = schedule_record["runs"]
        started = sum((directory / f"{r['task']}--{r['approach']}--{r['repeat']}" / "manifest.json").exists() for r in schedule)
        text[4:4] = [f"Progress: {len(rows)}/{len(schedule)} results recorded; {started-len(rows)} started without a result; {len(schedule)-started} queued.", "",
                     f"Concurrency: up to {schedule_record.get('jobs', 'unknown')} trials. Wall times include shared-service variability.", ""]
    for approach in ("prompt", "plan", "openspec", "gennady"):
        selected = [r for r in rows if r["approach"] == approach]
        if not selected:
            continue
        grades = [r["grade"] for r in selected if r.get("grade") is not None]
        mean = lambda key: statistics.mean(r[key] for r in selected)
        cost = sum(v["estimated_api_cost_usd"] for r in selected for v in r["usage_by_role"].values())
        agent_cost = sum(r["usage_by_role"]["agent"]["estimated_api_cost_usd"] for r in selected)
        partial_role = lambda role: any(r["usage_by_role"][role]["missing_usage_turns"] or r["usage_by_role"][role].get("partial_usage_turns", 0) for r in selected)
        agent_partial = partial_role("agent")
        overhead_partial = partial_role("user") or partial_role("reviewer")
        correctness = statistics.mean(g["correctness_percent"] for g in grades) if grades else None
        text.append(f"| {approach} | {sum(r['status']=='completed' for r in selected)}/{len(selected)} | "
                    f"{sum(g['resolved'] for g in grades)}/{len(selected)} | {number(correctness)} | "
                    f"{number(mean('user_words'))} | {number(mean('estimated_human_minutes'))} | "
                    f"{number(mean('elapsed_seconds')/60)} | {'partial ' if agent_partial else ''}{agent_cost:.4f} | {'partial ' if overhead_partial else ''}{cost-agent_cost:.4f} |")
    text += ["", "## Measured task results", "",
             "| Task / approach | Status | Hidden acceptance | New regressions | Changed-line coverage | Added tests | User interactions / questions | Input / cached / output tokens |",
             "|---|---|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        g = r.get("grade") or {}
        u = r["usage_by_role"]
        tokens = [sum(v[key] for v in u.values()) for key in ("input_tokens", "cached_input_tokens", "output_tokens")]
        text.append(f"| [{r['task']} / {r['approach']}]({r['directory']}/result.json) | {r['status']} | "
            f"{g.get('fail_to_pass_passed','?')}/{g.get('fail_to_pass_total','?')} | "
            f"{len(g['regressions']) if 'regressions' in g else 'n/a'} | "
            f"{number(g.get('changed_line_coverage_percent'))} | {len(g.get('candidate_added_tests',{}))} | "
            f"{r['user_interactions']} / {r['questions']} | {' / '.join(map(str,tokens))} |")
    text += ["", "## Coverage and change scope", "",
             "Whole-package coverage is comparable within a task; unchanged code dominates it. Static counts are scope indicators, not quality scores.", "",
             "| Task / approach | Package line % | Package branch % | Changed source / tests / docs files | Worker dispatches |",
             "|---|---:|---:|---:|---:|"]
    for r in rows:
        grade = r.get("grade") or {}
        coverage = grade.get("candidate_coverage") or {}
        percent = lambda numerator, denominator: 100 * coverage.get(numerator, 0) / coverage[denominator] if coverage.get(denominator) else None
        scope = grade.get("static_metrics") or {}
        files = " / ".join(str(scope.get(k, "n/a")) for k in ("source_files_changed", "test_files_changed", "documentation_files_changed"))
        text.append(f"| {r['task']} / {r['approach']} | {number(percent('covered_lines', 'num_statements'))} | "
                    f"{number(percent('covered_branches', 'num_branches'))} | {files} | {r.get('dispatch_count', 0)} |")
    phases = {}
    for r in rows:
        turns_path = Path(r["directory"]) / "turns.json"
        for turn in json.loads(turns_path.read_text()) if turns_path.exists() else []:
            if turn["role"] != "agent":
                continue
            key = (r["approach"], turn["stage"].split("-worker")[0])
            phase = phases.setdefault(key, {"seconds": 0, "cost": 0, "calls": 0, "partial": False})
            phase["seconds"] += turn["seconds"]
            phase["cost"] += turn.get("estimated_api_cost_usd") or 0
            phase["calls"] += 1
            phase["partial"] |= turn.get("usage_is_partial", False) or turn.get("usage") is None
    text += ["", "## Agent time by workflow stage", "",
             "Totals across recorded trials, including workers and retries. CLI time excludes simulator, setup and independent grading; it is not end-to-end wall time.", "",
             "| Approach / stage | CLI calls | Agent minutes | Agent API $ |", "|---|---:|---:|---:|"]
    for (approach, stage), phase in sorted(phases.items()):
        text.append(f"| {approach} / {stage} | {phase['calls']} | {number(phase['seconds']/60)} | "
                    f"{'partial ' if phase['partial'] else ''}{phase['cost']:.4f} |")
    anonymity = ("The review prompt omits workflow labels and the reviewer uses an anonymous working-directory name."
                 if all(r.get("review_context_anonymous") for r in rows)
                 else "These legacy reviews can reveal the approach through their working-directory paths and are not fully blinded.")
    text += ["", "## Independent quality judgments", "",
             "Original review protocol. Scores: 1 serious defects, 3 adequate, 5 excellent. These are model judgments; open the evidence before interpreting a score. " + anonymity + " Performance and security are reviews, not benchmark/audit guarantees.", "",
             "| Task / approach | Maintainability | Readability | Tests | Performance | Security |",
             "|---|---:|---:|---:|---:|---:|"]
    for r in rows:
        values = [str(r["rubric"].get(k,{}).get("score","n/a")) for k in
                  ("maintainability","readability","test_quality","performance","security")]
        evidence = f"{r['directory']}/evaluation/rubric-review.json"
        label = f"[{r['task']} / {r['approach']}]({evidence})" if r["rubric"] else f"{r['task']} / {r['approach']}"
        text.append(f"| {label} | " + " | ".join(values) + " |")
    text += ["", "Review limitation: reviewers received candidate failure counts and new-regression identities, but not the full baseline failure explanation or unchanged source. Several spooled-stream reviews penalize the three pre-existing failures or infer missing behavior from a diff. These ratings are retained as recorded and should not determine an approach ranking; use independent regression results and inspect the linked evidence."]
    contexts = [r for r in rows if r["context_review"]]
    if contexts:
        text += ["", "## Quality review with baseline and source context", "",
                 "A separately recorded, uniform post-trial review supplies baseline failure identities/counts, complete changed source files, and newly added test files. It preserves the original scores and execution outcomes. This additional assessment cost is shown here separately from the earlier overhead column. Ratings remain model judgments.", "",
                 "| Task / approach | Status | Maintainability | Readability | Tests | Performance | Security | Extra API $ |",
                 "|---|---|---:|---:|---:|---:|---:|---:|"]
        for r in contexts:
            context = r["context_review"]
            values = [str(context.get("rubric", {}).get(k, {}).get("score", "n/a")) for k in
                      ("maintainability", "readability", "test_quality", "performance", "security")]
            cost = number(context.get("estimated_api_cost_usd"), 4)
            text.append(f"| [{r['task']} / {r['approach']}]({r['directory']}/context-review/result.json) | {context['status']} | "
                        + " | ".join(values) + f" | {'partial ' if context.get('usage_is_partial') else ''}{cost} |")
    text += ["", "## Limits", "",
             "Historical checks satisfied means all original fail-to-pass tests pass with no new original-suite regressions. It does not prove every requirement is met.", "",
             "API-equivalent prices are not measured subscription charges. Human minutes estimate summary-review interaction burden using configurable reading/writing/decision rates; they exclude full artifact/code review and simulator-only coaching. This report recalculates that proxy from the visible messages; raw result files retain the earlier full-prompt proxy for audit. MEASUREMENTS.json contains the corrected report records. Simulator latency is recorded separately. Cached input is a subset of input, and reasoning is a subset of output. Public historical tasks may be in model training data. Workflow bootstrapping is charged on every run; pre-existing-spec amortization is a separate experiment.", ""]
    for r in rows:
        source = Path(r["directory"]) / "workspace/boltons/ioutils.py"
        if r["task"] == "boltons-spooled-io" and source.exists() and "return self.getvalue() == other.getvalue()" in source.read_text():
            text.append(f"- **Requirement gap — {r['task']} / {r['approach']}:** the candidate retains `getvalue()`-based equality, contrary to the streaming requirement. The historical acceptance tests do not detect this gap.")
        if r.get("recovery_from"):
            text.append(f"- **Calibration recovery:** {r['task']} / {r['approach']} continues {r['recovery_from']}. Its time/prose/usage measure the continuation only; do not pool it with fresh benchmark runs.")
        if r.get("error"):
            text.append(f"- **{r['task']} / {r['approach']}:** {r['error']}")
    output = directory / "COMPARISON.md"
    output.write_text("\n".join(text) + "\n")
    (directory / "MEASUREMENTS.json").write_text(json.dumps(rows, indent=2) + "\n")
    print(output)


if __name__ == "__main__":
    main()
