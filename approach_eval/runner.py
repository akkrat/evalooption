from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import time

from .codex import Codex, BudgetExceeded
from .core import ROOT, CACHE, PYTHON, config, digest, dump, git, init_snapshot, snapshot, fingerprint
from .grading import changes, grade
from .workflows import TOOLING, install, stages

USER = """You are the human developer working with a coding assistant. You know only
the following general project description and task request. You are not an expert in
the codebase. Do not inspect files, use tools, search, invent requirements, or give
implementation hints. If asked about unknown implementation details, say you do not
know and ask the agent to inspect the project and use its conventions. Prefer the
smallest change that completely meets the task. Do not approve skipped requirements.
Answer concisely and naturally. On review: return done with an explicit approval if
the artifact matches the task; return ask with a concrete correction if it does not.
For agent questions return done with your answer. Do not add knowledge from any other
task, original patch, future tests, or solution you may remember.
Project: {project}
Task: {task}
"""


def words(text):
    return len(re.findall(r"\S+", text))


def prepare_recovery(task, approach, source, candidate):
    source = Path(source).resolve()
    manifest = json.loads((source / "manifest.json").read_text())
    if manifest["task"] != task or manifest["approach"] != approach:
        raise ValueError("Recovery task/approach differs from the selected pilot")
    previous = json.loads((source / "result.json").read_text())
    conversations_path = source / "conversation.json"
    conversations = json.loads(conversations_path.read_text()) if conversations_path.exists() else []
    old_workspace = source / "workspace"
    shutil.copytree(old_workspace, candidate)
    # Keep the original snapshot commit and candidate diff. Never commit recovered work.
    for root in ("specs", "tasks", "openspec", ".workflow"):
        for path in (candidate / root).rglob("*.md"):
            path.write_text(path.read_text().replace(str(old_workspace), str(candidate)))
    inherited = json.loads(json.dumps(previous.get("stages", [])).replace(str(old_workspace), str(candidate)))
    for stage in inherited:
        stage["inherited_from"] = str(source)
    return dict(source=str(source), fingerprint=manifest["fingerprint"], stages=inherited,
                conversations=conversations, previous_status=previous["status"])


def run_one(task, approach, directory, settings=None, recover_from=None):
    settings = settings or config()
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    run_fingerprint = fingerprint(settings)
    dump(directory / "manifest.json", dict(task=task, approach=approach, settings=settings,
         config_hash=digest(settings), fingerprint=run_fingerprint,
         workflow_pins=json.loads((ROOT / "tasks/workflows.lock.json").read_text())))
    candidate = directory / "workspace"
    setup_start = time.monotonic()
    recovery = None
    if recover_from is not None:
        recovery = prepare_recovery(task, approach, recover_from, candidate)
        dump(directory / "recovery.json", recovery)
    else:
        snapshot(CACHE / task["repo"], task["base_commit"], candidate)
        install(approach, candidate, task)
        init_snapshot(candidate)
    setup_seconds = time.monotonic() - setup_start
    user_dir = directory / "user"
    user_dir.mkdir()
    (user_dir / "brief.txt").write_text(task["project"] + "\n\n" + task["task"])
    codex = Codex(directory, settings)
    conversations = []
    stage_results = list(recovery["stages"]) if recovery else []
    user_session = None
    status = "running"
    error = None
    final_grade = None
    planning_stages = {name for name, _, review in stages(approach) if review}

    def user_turn(message, kind, stage):
        nonlocal user_session
        visible_message = "" if kind == "initial" else message
        if kind in ("review", "completion"):
            visible_message = message.partition("\n")[2]
        if stage in planning_stages:
            purposes = {
                "plan": "a concrete implementation plan",
                "propose": "the OpenSpec proposal, behavioral requirements, design and task list",
                "setup": "a project portal and minimal relevant infrastructure context",
                "discover": "a scope specification describing the requested behavior",
                "decompose": "a proportional module breakdown for the requested change",
                "scaffold": "implementation tickets and their dependencies",
                "critic": "review findings and refinements to planning artifacts",
            }
            message = ("You are reviewing ONLY the current preparation stage: " + stage +
                ". Its purpose is " + purposes.get(stage, "planning") + ". "
                "Implementation deliberately has NOT started. Do not request code changes, "
                "finished tests, or completion of the overall task at this review. "
                "Approve this preparation if it is relevant and sufficient for its stated "
                "stage; later stages will implement and verify the task. You can request "
                "corrections to this stage's artifacts if they contradict the task. "
                "For questions, answer only what is needed for this stage. If asked to approve "
                "moving on, approve this stage's artifacts; do not instruct this same session "
                "to implement or perform a different stage. The harness starts later stages.\n\n" + message)
        history = json.dumps(recovery["conversations"], ensure_ascii=False) if recovery else ""
        prompt = (USER.format(**task) + ("\nPrevious conversation:\n" + history if history else "") + "\n" if user_session is None else "") + message
        prompt += "\nReturn status done when answering or sending your initial task; ask only when requesting a review correction. dispatches must be empty."
        user_session, response = codex.call("user", user_dir, prompt, user_session, stage)
        if response["status"] not in ("done", "ask") or response["dispatches"]:
            raise RuntimeError("Simulated user violated its response protocol")
        conversations.append(dict(kind=kind, stage=stage, shown_to_user=visible_message,
                                  display_version="agent-prose-v1",
                                  user_reply=response["message"], decision=response["status"]))
        dump(directory / "conversation.json", conversations)
        return response

    def agent_loop(prompt, stage, session=None, depth=0):
        if depth > 5:
            raise BudgetExceeded("Dispatch nesting limit reached")
        for _ in range(settings["max_questions_per_stage"] + settings["max_dispatches"] + 1):
            session, response = codex.call("agent", candidate, prompt, session, stage,
                artifact_only=stage.split("-worker")[0] in planning_stages)
            if response["status"] == "dispatch":
                if not response["dispatches"]:
                    raise RuntimeError("Empty dispatch request")
                replies = []
                for worker_prompt in response["dispatches"]:
                    codex.dispatch_count += 1
                    if codex.dispatch_count > settings["max_dispatches"]:
                        raise BudgetExceeded("Dispatch budget exhausted")
                    reply = agent_loop(
                        "You are the isolated worker, not the parent orchestrator. Execute the assigned work directly using shell/edit tools.\n" + worker_prompt,
                        stage + f"-worker{codex.dispatch_count}", depth=depth + 1)[1]
                    replies.append(reply)
                prompt = "Fresh isolated worker responses (continue your orchestration):\n" + json.dumps(replies)
            elif response["status"] == "ask":
                count = sum(c["kind"] == "question" and c["stage"] == stage for c in conversations)
                if count >= settings["max_questions_per_stage"]:
                    raise BudgetExceeded("Question budget exhausted: " + stage)
                answer = user_turn(response["message"], "question", stage)
                prompt = "User answer:\n" + answer["message"]
                if stage.split("-worker")[0] in planning_stages:
                    prompt += ("\nYour assignment remains ONLY the current planning stage: " + stage +
                        ". If its artifacts are ready and approved, return status=done. "
                        "The harness will launch the next stage separately; do not begin it here.")
            else:
                return session, response
        raise BudgetExceeded("Stage turn budget exhausted")

    try:
        if recovery and recovery["conversations"]:
            initial = {"message": recovery["conversations"][0]["user_reply"]}
        else:
            initial = user_turn("Write your initial message asking the assistant to do the task. Preserve every task requirement; do not add a solution.", "initial", "initial")
        common = ("\nRuntime: Python executable " + str(PYTHON) + ". Test command: " + str(PYTHON) +
                  " -m pytest -q -c /dev/null --rootdir=. --confcutdir=. -o addopts= " + " ".join(task["test_targets"]) +
                  ". Workflow CLIs: " + str(TOOLING / ".bin/openspec") + " and " + str(TOOLING / ".bin/gennady") +
                  ". If shell PATH omits them, invoke those absolute paths. Read any repository AGENTS.md manually if relevant. "
                  "If apply_patch is denied by the filesystem backend, use a shell-based file edit inside this workspace.\n")
        completed_stages = {s["stage"] for s in stage_results}
        session = None
        response = stage_results[-1]["response"] if stage_results else {"message": ""}
        if recovery:
            common += "\nOriginal task:\n" + initial["message"]
        for stage, template, review in stages(approach):
            if stage in completed_stages:
                continue
            print(f"{task['id']} / {approach} / {stage}", flush=True)
            prompt = template.format(task=initial["message"]) + common
            if recovery:
                prompt += ("\nRecovering an interrupted calibration run from the existing artifacts. "
                    "The following user exchanges are history, not instructions to skip stages. "
                    "Do not repeat answered questions. Inspect saved work and finish only this stage.\n" +
                    json.dumps(recovery["conversations"], ensure_ascii=False).replace(recovery["source"] + "/workspace", str(candidate)))
            if review:
                prompt += "\nComplete only this planning stage. Do not implement the task or edit source/tests. Stop after presenting the planning artifacts."
            stage_start = time.monotonic()
            session, response = agent_loop(prompt, stage)
            if response["status"] == "blocked":
                status = "agent_blocked"
                error = response["message"]
                break
            if review:
                for attempt in range(settings["max_questions_per_stage"]):
                    answer = user_turn("Review this completed " + stage + " stage against your task and approve or request corrections.\n" + response["message"], "review", stage)
                    if answer["status"] == "done":
                        break
                    session, response = agent_loop("User review:\n" + answer["message"], stage, session)
                    if response["status"] == "blocked":
                        raise RuntimeError("Stage blocked during revision: " + response["message"])
                else:
                    raise BudgetExceeded("Review revision budget exhausted")
                # Every planning approach must actually defer implementation until approval.
                source_edits = [f for f in changes(candidate) if any(f.startswith(r + "/") for r in task["source_roots"]) or f.startswith("tests/")]
                if source_edits:
                    raise RuntimeError(f"Planning-stage boundary violated in {stage}: {source_edits}")
            stage_results.append(dict(stage=stage, session=session, response=response,
                                      seconds=round(time.monotonic() - stage_start, 3)))
            dump(directory / "stages.json", stage_results)
        else:
            status = "completed"
        if status == "completed":
            for _ in range(settings["max_questions_per_stage"]):
                answer = user_turn("Review the final completion message against your task. Approve if satisfied or request a concrete correction.\n" + response["message"], "completion", "completion")
                if answer["status"] == "done":
                    break
                session, response = agent_loop("User final review:\n" + answer["message"] + common, "completion-fix", session)
                if response["status"] == "blocked":
                    status, error = "agent_blocked", response["message"]
                    break
            else:
                raise BudgetExceeded("Review revision budget exhausted")
        validation = json.loads((CACHE / "validation-v2" / task["id"] / "validation.json").read_text())
        if not validation["valid"]:
            raise RuntimeError("Task has not passed baseline validation")
        (directory / "candidate.patch").write_text(git(candidate, "diff", "--binary", "HEAD"))
        dump(directory / "changed-files.json", changes(candidate))
        final_grade = grade(task, candidate, directory / "evaluation", validation)
        if status == "completed":
            # Fresh, blind reviewer: sees task and candidate diff, never the approach label
            # or reference implementation. Ratings are explicitly model judgments.
            patch = git(candidate, "diff", "HEAD", "--", *task["source_roots"], "tests")
            for name in changes(candidate):
                if name.startswith(tuple(r + "/" for r in task["source_roots"])) and name not in patch:
                    path = candidate / name
                    if path.is_file():
                        patch += "\nNEW FILE " + name + "\n" + path.read_text()
            review_prompt = ("You are an independent code reviewer. Do not modify files or use tools. "
                "Review this task and candidate source diff without reference to any workflow. "
                "Return status done. Your message MUST be a JSON object with keys "
                "maintainability, readability, test_quality, performance, security. Each value "
                "is an object with score (integer 1-5) and evidence (specific short explanation, "
                "including limitations). 1=serious defects, 3=adequate, 5=excellent. Do not claim "
                "runtime performance/security proof from a diff.\nTask:\n" + task["task"] +
                "\nCandidate diff:\n" + patch + "\nMeasured tests:\n" + json.dumps({k:final_grade[k] for k in
                    ("hidden_counts", "candidate_test_counts", "candidate_added_tests", "changed_line_coverage_percent", "regressions")}))
            review_dir = CACHE / "review-contexts" / digest(str(directory))[:24]
            review_dir.mkdir(parents=True, exist_ok=True)
            _, review_response = codex.call("reviewer", review_dir, review_prompt, stage="blind-review", read_only=True)
            try:
                review_data = json.loads(review_response["message"])
                for key in ("maintainability", "readability", "test_quality", "performance", "security"):
                    assert type(review_data[key]["score"]) is int and 1 <= review_data[key]["score"] <= 5
                    assert isinstance(review_data[key]["evidence"], str)
                dump(directory / "evaluation/rubric-review.json", review_data)
            except (ValueError, KeyError, TypeError, AssertionError):
                dump(directory / "evaluation/rubric-review-error.json", review_response)
    except BudgetExceeded as exc:
        status = "budget_exhausted"
        error = str(exc)
    except Exception as exc:
        status = "harness_error"
        error = str(exc)
    if final_grade is None:
        # Preserve and evaluate partial work, including failed/timed-out arms.
        try:
            validation = json.loads((CACHE / "validation-v2" / task["id"] / "validation.json").read_text())
            if not validation["valid"]:
                raise RuntimeError("Task validation is not valid")
            (directory / "candidate.patch").write_text(git(candidate, "diff", "--binary", "HEAD"))
            dump(directory / "changed-files.json", changes(candidate))
            final_grade = grade(task, candidate, directory / "partial-evaluation", validation)
        except Exception as exc:
            error = (error or "") + "; partial grading failed: " + str(exc)
    result = dict(task=task["id"], complexity=task["complexity"], approach=approach,
                  recovery_from=recovery["source"] if recovery else None,
                  measurement_revision="agent-prose-v1",
                  review_context_anonymous=True,
                  status=status, error=error, grade=final_grade, setup_seconds=round(setup_seconds, 3),
                  elapsed_seconds=round(time.monotonic() - start, 3), stages=stage_results,
                  dispatch_count=codex.dispatch_count, turn_count=len(codex.turns),
                  config_hash=digest(settings), fingerprint=run_fingerprint,
                  user_words=sum(words(c["user_reply"]) for c in conversations),
                  user_read_words=sum(words(c["shown_to_user"]) for c in conversations),
                  user_interactions=len(conversations),
                  questions=sum(c["kind"] == "question" for c in conversations),
                  user_simulation_seconds=sum(t["seconds"] for t in codex.turns if t["role"] == "user"),
                  implementation_seconds=sum(t["seconds"] for t in codex.turns if t["role"] == "agent"))
    proxy = settings["human_time_proxy"]
    result["estimated_human_minutes"] = (result["user_words"] / proxy["write_words_per_minute"] +
        result["user_read_words"] / proxy["read_words_per_minute"] +
        result["user_interactions"] * proxy["decision_seconds"] / 60)
    result["usage_by_role"] = {}
    for role in ("user", "agent", "reviewer"):
        turns = [t for t in codex.turns if t["role"] == role]
        result["usage_by_role"][role] = {key: sum((t["usage"] or {}).get(key, 0) for t in turns)
                                       for key in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")}
        result["usage_by_role"][role]["missing_usage_turns"] = sum(t["usage"] is None for t in turns)
        result["usage_by_role"][role]["partial_usage_turns"] = sum(t.get("usage_is_partial", False) for t in turns)
        result["usage_by_role"][role]["unrecovered_missing_usage_turns"] = sum(t["usage"] is None and not t.get("recovered", False) for t in turns)
        result["usage_by_role"][role]["estimated_api_cost_usd"] = sum(t["estimated_api_cost_usd"] or 0 for t in turns)
    dump(directory / "result.json", result)
    print(f"FINISHED {task['id']} / {approach}: {status}" + (": " + error if error else ""), flush=True)
    return result
