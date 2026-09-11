import json
import subprocess
from pathlib import Path

import pytest

from approach_eval.codex import estimate_cost, usage_from_events, toml_value
from approach_eval.core import snapshot, init_snapshot, git, command
from approach_eval.grading import junit, overlay_gold_tests


def test_usage_counts_completed_turns_once_and_cached_input_is_not_extra():
    events = [
        {"type": "item.completed", "usage": {"input_tokens": 9999}},
        {"type": "turn.completed", "usage": {"input_tokens": 1000, "cached_input_tokens": 600,
         "cache_write_input_tokens": 100, "output_tokens": 100, "reasoning_output_tokens": 80}},
        {"type": "turn.completed", "usage": {"input_tokens": 200, "output_tokens": 20}},
    ]
    usage = usage_from_events(events)
    assert usage["input_tokens"] == 1200
    rates = {"input": 2, "cached_input": .2, "cache_write_input": 2.5, "output": 10}
    assert estimate_cost(usage, rates) == pytest.approx((500*2 + 600*.2 + 100*2.5 + 120*10)/1e6)
    assert usage_from_events([{"type": "turn.failed"}]) is None
    assert estimate_cost(None, rates) is None


def test_snapshot_excludes_future_git_history(tmp_path):
    repo = tmp_path / "upstream"
    repo.mkdir()
    (repo / "code.py").write_text("value = 1\n")
    init_snapshot(repo)
    base = git(repo, "rev-parse", "HEAD").strip()
    (repo / "code.py").write_text("value = 42\n")
    (repo / "secret_test.py").write_text("assert value == 42\n")
    git(repo, "add", ".")
    git(repo, "-c", "user.name=Test", "-c", "user.email=t@localhost", "commit", "-qm", "future solution")
    dest = tmp_path / "candidate"
    snapshot(repo, base, dest)
    init_snapshot(dest)
    assert (dest / "code.py").read_text() == "value = 1\n"
    assert not (dest / "secret_test.py").exists()
    assert git(dest, "rev-list", "--count", "HEAD").strip() == "1"
    assert git(dest, "remote").strip() == ""
    assert "future solution" not in git(dest, "log", "--all", "--oneline")


def test_timeout_terminates_process_group():
    result = command(["/bin/sh", "-c", "sleep 20 & wait"], timeout=.1)
    assert result["timed_out"] is True
    assert result["seconds"] < 8


def test_junit_failure_error_and_skip_are_distinct(tmp_path):
    path = tmp_path / "junit.xml"
    path.write_text('<testsuites><testsuite><testcase classname="a" name="ok"/>'
                    '<testcase classname="a" name="bad"><failure/></testcase>'
                    '<testcase classname="a" name="error"><error/></testcase>'
                    '<testcase classname="a" name="skip"><skipped/></testcase></testsuite></testsuites>')
    assert junit(path) == {"a::ok": "passed", "a::bad": "failed", "a::error": "error", "a::skip": "skipped"}


def test_dotted_paths_are_literal_toml_keys():
    import tomllib
    value = {"evaluation": {"filesystem": {"/Users/a.person/project": "write", ":root": "read"}}}
    assert tomllib.loads("permissions = " + toml_value(value))["permissions"] == value


def test_each_curated_task_has_verified_discriminating_tests():
    from approach_eval.core import tasks, CACHE
    for task in tasks():
        path = CACHE / "validation-v2" / task["id"] / "validation.json"
        if not path.exists():
            pytest.skip("Run approach-eval validate for live fixture checks")
        validation = json.loads(path.read_text())
        assert validation["valid"]
        assert validation["fail_to_pass"]
        assert validation["after"]["returncode"] == 0
        for case in validation["fail_to_pass"]:
            assert validation["before"]["tests"][case] in ("failed", "error")
            assert validation["after"]["tests"][case] == "passed"


def test_deleting_candidate_tests_cannot_pass_hidden_grading(tmp_path, monkeypatch):
    from approach_eval import grading
    repo = tmp_path / "upstream"
    (repo / "sample").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "sample/__init__.py").write_text("def increment(x):\n    return x\n")
    (repo / "tests/test_increment.py").write_text("from sample import increment\ndef test_callable():\n    assert callable(increment)\n")
    init_snapshot(repo)
    base = git(repo, "rev-parse", "HEAD").strip()
    (repo / "sample/__init__.py").write_text("def increment(x):\n    return x + 1\n")
    with (repo / "tests/test_increment.py").open("a") as f:
        f.write("def test_increment():\n    assert increment(2) == 3\n")
    git(repo, "add", ".")
    git(repo, "-c", "user.name=Test", "-c", "user.email=t@localhost", "commit", "-qm", "fix")
    fix = git(repo, "rev-parse", "HEAD").strip()
    task = dict(id="fixture", repo="upstream", base_commit=base, fix_commit=fix,
                source_roots=["sample"], test_files=["tests/test_increment.py"],
                test_targets=["tests/test_increment.py"], full_test_targets=["tests"])
    monkeypatch.setattr(grading, "CACHE", tmp_path)
    validation = grading.validate_task(task, tmp_path / "validation")
    assert validation["valid"]
    candidate = tmp_path / "candidate"
    snapshot(repo, base, candidate)
    init_snapshot(candidate)
    (candidate / "tests/test_increment.py").unlink()
    result = grading.grade(task, candidate, tmp_path / "grade", validation)
    assert result["correctness_percent"] == 0
    assert result["resolved"] is False
    assert result["hidden_counts"]["failed"] == 1


@pytest.mark.parametrize("relocated", [False, True])
def test_grader_sandbox_denies_hidden_metadata_and_network(tmp_path, monkeypatch, relocated):
    from approach_eval import grading
    from approach_eval.grading import sandbox_test_command
    from approach_eval.core import ROOT, PYTHON
    hidden = ROOT / "tasks/suite.json"
    if relocated:
        evaluator = tmp_path / "evaluator"
        evaluator.mkdir()
        hidden = evaluator / "private.json"
        hidden.write_text("evaluator-only metadata")
        monkeypatch.setattr(grading, "ROOT", evaluator)
    workspace = tmp_path / "candidate"
    workspace.mkdir()
    source = """import pathlib, socket
try:
    pathlib.Path(HIDDEN).read_text()
except PermissionError:
    pass
else:
    raise AssertionError('hidden metadata was readable')
try:
    pathlib.Path(HIDDEN).write_text('corrupted')
except PermissionError:
    pass
else:
    raise AssertionError('hidden metadata was writable')
try:
    s = socket.socket(); s.bind(('127.0.0.1', 0))
except PermissionError:
    pass
else:
    raise AssertionError('network binding was allowed')
print('ISOLATED')
""".replace("HIDDEN", repr(str(hidden)))
    result = command(sandbox_test_command([PYTHON, "-c", source], workspace, workspace), workspace)
    assert result["returncode"] == 0, result["stderr"]
    assert "ISOLATED" in result["stdout"]


def test_human_reading_excludes_simulator_coaching_but_preserves_agent_prose():
    from scripts.report_details import visible_prose
    assert visible_prose(dict(kind="initial", shown_to_user="Write your initial task.")) == ""
    question = "Which behavior should be preserved?\n\nFor example, shared mutable defaults."
    assert visible_prose(dict(kind="question", shown_to_user=question)) == question
    assert visible_prose(dict(kind="question", shown_to_user=
        "You are reviewing ONLY the current preparation stage: setup. Private coaching.\n\n" + question)) == question
    summary = "The proposal covers defaults and regression tests.\n\nPlease review it."
    assert visible_prose(dict(kind="review", shown_to_user=
        "You are reviewing ONLY the current preparation stage: propose. Private coaching.\n\n"
        "Review this completed stage against your task.\n" + summary)) == summary


def test_interrupted_usage_uses_latest_invocation_counter_not_sum(tmp_path):
    from approach_eval.codex import rollout_counter
    path = tmp_path / "session.jsonl"
    rows = []
    for second, count in ((1, 9000), (11, 100), (12, 250), (13, 250)):
        rows.append(dict(timestamp=f"2026-09-09T00:00:{second:02d}Z", type="event_msg",
            payload=dict(type="token_count", info=dict(total_token_usage=dict(input_tokens=count, output_tokens=10)))))
    path.write_text("\n".join(json.dumps(row) for row in rows))
    import datetime
    start = datetime.datetime(2026, 9, 9, 0, 0, 10, tzinfo=datetime.timezone.utc).timestamp()
    assert rollout_counter([path], start)["input_tokens"] == 250
    assert rollout_counter([path], start + 20) is None


def test_recovery_preserves_base_diff_and_original_artifacts(tmp_path):
    from approach_eval.runner import prepare_recovery
    old = tmp_path / "old"
    tree = old / "workspace"
    tree.mkdir(parents=True)
    (tree / "code.py").write_text("value = 1\n")
    init_snapshot(tree)
    base = git(tree, "rev-parse", "HEAD").strip()
    (tree / "code.py").write_text("value = 2\n")
    (tree / "specs").mkdir()
    (tree / "specs/plan.md").write_text(str(tree) + "/code.py")
    task = dict(id="sample")
    (old / "manifest.json").write_text(json.dumps(dict(task=task, approach="plan", fingerprint="old")))
    (old / "result.json").write_text(json.dumps(dict(status="harness_error", stages=[])))
    new = tmp_path / "new"
    recovered = prepare_recovery(task, "plan", old, new)
    assert git(new, "rev-parse", "HEAD").strip() == base
    assert "+value = 2" in git(new, "diff", "HEAD")
    assert (new / "specs/plan.md").read_text() == str(new) + "/code.py"
    assert (tree / "specs/plan.md").read_text() == str(tree) + "/code.py"
    assert recovered["source"] == str(old)
    with pytest.raises(ValueError):
        prepare_recovery(dict(id="different"), "plan", old, tmp_path / "wrong")


def test_usage_limit_retry_resumes_same_luna_session_and_keeps_partial_cost(tmp_path, monkeypatch):
    from approach_eval import codex
    from approach_eval.core import config
    monkeypatch.setattr(codex, "ROOT", tmp_path)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    sid = "11111111-1111-1111-1111-111111111111"
    commands = []
    def fake_command(args, cwd, timeout, prompt, env):
        commands.append(args)
        if len(commands) == 1:
            events = [dict(type="thread.started", thread_id=sid),
                      dict(type="turn.failed", error=dict(message="You've hit your usage limit."))]
            code = 1
        else:
            Path(args[args.index("--output-last-message") + 1]).write_text(json.dumps(
                dict(status="done", message="finished", dispatches=[])))
            events = [dict(type="turn.completed", usage=dict(input_tokens=20, output_tokens=10))]
            code = 0
        return dict(stdout="\n".join(json.dumps(e) for e in events), stderr="", returncode=code,
                    timed_out=False, seconds=1, command=args)
    monkeypatch.setattr(codex, "command", fake_command)
    monkeypatch.setattr(codex, "rollout_counter", lambda paths, start: dict(input_tokens=5, cached_input_tokens=0, output_tokens=2))
    monkeypatch.setattr(codex.time, "sleep", lambda seconds: None)
    client = codex.Codex(tmp_path / "transcript", config())
    actual_sid, response = client.call("agent", tmp_path, "Do the task", stage="implement")
    assert actual_sid == sid and response["status"] == "done"
    assert commands[1][1:4] == ["exec", "resume", sid]
    assert all(c[c.index("--model") + 1] == "gpt-5.6-luna" for c in commands)
    assert client.turns[0]["recovered"] and client.turns[0]["usage_is_partial"]
    assert sum(t["usage"]["input_tokens"] for t in client.turns) == 25


@pytest.mark.parametrize("outside", ["checkout", "workspace", "transcript"])
def test_model_call_rejects_paths_outside_home_before_execution(tmp_path, monkeypatch, outside):
    from approach_eval import codex
    from approach_eval.core import config
    home = tmp_path / "home"
    paths = {name: home / name for name in ("checkout", "workspace", "transcript")}
    paths[outside] = tmp_path / "outside"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(codex, "ROOT", paths["checkout"])
    def forbidden(*args, **kwargs):
        pytest.fail("Unsupported checkout must not launch a model call")
    monkeypatch.setattr(codex, "command", forbidden)
    client = codex.Codex(paths["transcript"], config())
    with pytest.raises(RuntimeError, match="under your home directory"):
        client.call("agent", paths["workspace"], "Do the task")
