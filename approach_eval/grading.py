from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import re
import shutil
import sys
import xml.etree.ElementTree as ET

from .core import CACHE, PYTHON, command, dump, git, snapshot


def sandbox_test_command(args, tree, output):
    """Tests execute generated code, so they get neither network nor evaluator data."""
    if sys.platform != "darwin":
        raise RuntimeError("This test isolation adapter requires macOS sandbox-exec; add a container adapter for other platforms")
    readable = [tree.resolve(), output.resolve(), PYTHON.parent.parent.resolve(),
                PYTHON.resolve().parent.parent]
    writable = [tree.resolve(), output.resolve(), Path("/private/tmp"), Path("/dev/null")]
    quote = lambda p: json.dumps(str(p))
    read_exceptions = " ".join("(require-not (subpath " + quote(p) + "))" for p in readable)
    write_exceptions = " ".join("(require-not (subpath " + quote(p) + "))" for p in writable)
    profile = ("(version 1) (allow default) (deny network*) "
        "(deny file-read-data (require-all (subpath " + quote(Path.home()) + ") " + read_exceptions + ")) "
        "(deny file-write* (require-all " + write_exceptions + "))")
    return ["/usr/bin/sandbox-exec", "-p", profile, *args]


def junit(path):
    if not Path(path).exists():
        return {}
    root = ET.parse(path).getroot()
    statuses = {}
    for item in root.iter("testcase"):
        key = item.get("classname", "") + "::" + item.get("name", "")
        statuses[key] = ("error" if item.find("error") is not None else
                         "failed" if item.find("failure") is not None else
                         "skipped" if item.find("skipped") is not None else "passed")
    return statuses


def test_run(tree, targets, output, source_roots, coverage=False):
    output.mkdir(parents=True, exist_ok=True)
    env = {key: value for key, value in os.environ.items()
           if key in ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "SYSTEMROOT")}
    env.update(PYTHONPATH=str(tree), PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1",
               PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", COVERAGE_FILE=str(output / ".coverage"))
    args = [PYTHON, "-m"]
    if coverage:
        args += ["coverage", "run", "--branch", "--source=" + ",".join(source_roots), "-m"]
    args += ["pytest", "-q", "-c", "/dev/null", "--rootdir=" + str(tree), "--confcutdir=" + str(tree), "-o", "addopts=", "-p", "no:cacheprovider",
             "--junitxml=" + str(output / "junit.xml"), *targets]
    result = command(sandbox_test_command(args, tree, output), tree, timeout=240, env=env)
    (output / "stdout.log").write_text(result.pop("stdout"))
    (output / "stderr.log").write_text(result.pop("stderr"))
    statuses = junit(output / "junit.xml")
    result["tests"] = statuses
    result["counts"] = {status: list(statuses.values()).count(status)
                        for status in ("passed", "failed", "error", "skipped")}
    if coverage:
        cov = command(sandbox_test_command([PYTHON, "-m", "coverage", "json", "-o", output / "coverage.json"], tree, output), tree, env=env)
        result["coverage_command_returncode"] = cov["returncode"]
        if (output / "coverage.json").exists():
            result["coverage_totals"] = json.loads((output / "coverage.json").read_text())["totals"]
    dump(output / "result.json", result)
    return result


def overlay_gold_tests(task, tree):
    for name in task["test_files"]:
        path = tree / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(git(CACHE / task["repo"], "show", f"{task['fix_commit']}:{name}"))


def validate_task(task, output):
    output.mkdir(parents=True, exist_ok=False)
    repo = CACHE / task["repo"]
    base, gold = output / "base", output / "gold"
    snapshot(repo, task["base_commit"], base)
    snapshot(repo, task["fix_commit"], gold)
    baseline = test_run(base, task["full_test_targets"], output / "baseline", task["source_roots"])
    overlay_gold_tests(task, base)
    before = test_run(base, task["test_targets"], output / "before", task["source_roots"])
    after = test_run(gold, task["test_targets"], output / "after", task["source_roots"], True)
    gold_full = test_run(gold, task["full_test_targets"], output / "gold-full", task["source_roots"])
    discriminating = sorted(name for name, state in before["tests"].items()
                            if state in ("failed", "error") and after["tests"].get(name) == "passed")
    valid = (bool(discriminating) and after["returncode"] == 0 and not before["timed_out"]
             and not any(r["timed_out"] for r in (baseline, gold_full)))
    value = dict(task=task["id"], valid=valid, fail_to_pass=discriminating,
                 baseline=baseline, before=before, after=after, gold_full=gold_full,
                 base_commit=task["base_commit"], fix_commit=task["fix_commit"])
    dump(output / "validation.json", value)
    return value


def changes(tree):
    tracked = git(tree, "diff", "--name-only", "HEAD").splitlines()
    untracked = git(tree, "ls-files", "--others", "--exclude-standard").splitlines()
    return sorted(set(tracked + untracked))


def code_metrics(tree, filenames):
    result = {"changed_files": len(filenames), "changed_python_files": 0,
              "syntax_errors": [], "functions": 0, "branch_points": 0,
              "max_function_lines": 0, "test_files_changed": 0, "documentation_files_changed": 0}
    for name in filenames:
        result["test_files_changed"] += int(name.startswith("tests/"))
        result["documentation_files_changed"] += int(name.endswith((".md", ".rst")))
        path = tree / name
        if path.suffix != ".py" or not path.is_file():
            continue
        result["changed_python_files"] += 1
        try:
            parsed = ast.parse(path.read_text())
        except (SyntaxError, UnicodeError) as exc:
            result["syntax_errors"].append({"file": name, "error": str(exc)})
            continue
        for node in ast.walk(parsed):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                result["functions"] += 1
                result["max_function_lines"] = max(result["max_function_lines"], node.end_lineno - node.lineno + 1)
            if isinstance(node, (ast.If, ast.For, ast.While, ast.ExceptHandler, ast.IfExp, ast.BoolOp)):
                result["branch_points"] += 1
    return result


def grade(task, candidate, output, validation):
    output.mkdir(parents=True, exist_ok=True)
    files = changes(candidate)
    # The evaluator starts independently from base. Candidate cannot delete or rewrite
    # evaluator tests/config. Only package source changes are replayed here.
    clean = output / "hidden-tree"
    snapshot(CACHE / task["repo"], task["base_commit"], clean)
    source_files = [f for f in files if any(f.startswith(r + "/") for r in task["source_roots"])]
    for name in source_files:
        src, dest = candidate / name, clean / name
        if src.is_symlink():
            raise RuntimeError(f"Candidate source symlink rejected: {name}")
        if src.is_file():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)
        elif dest.exists():
            dest.unlink()
    regressions = test_run(clean, task["full_test_targets"], output / "regressions", task["source_roots"], True)
    overlay_gold_tests(task, clean)
    hidden = test_run(clean, task["test_targets"], output / "hidden", task["source_roots"], True)
    # Independently preserve agent-written tests to measure their actual contribution.
    own = output / "candidate-tree"
    shutil.copytree(candidate, own, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
    candidate_tests = test_run(own, task["full_test_targets"], output / "candidate-tests", task["source_roots"], True)
    baseline_pass = {name for name, state in validation["baseline"]["tests"].items() if state == "passed"}
    regressions_failed = sorted(name for name in baseline_pass if regressions["tests"].get(name) != "passed")
    ftp = validation["fail_to_pass"]
    ftp_passed = [name for name in ftp if hidden["tests"].get(name) == "passed"]
    baseline_names = set(validation["baseline"]["tests"])
    added_tests = {name: state for name, state in candidate_tests["tests"].items() if name not in baseline_names}
    metrics = code_metrics(candidate, files)
    metrics["source_files_changed"] = len(source_files)
    metrics["diff_stat"] = git(candidate, "diff", "--stat", "HEAD")
    metrics["untracked_files"] = git(candidate, "ls-files", "--others", "--exclude-standard").splitlines()
    cov = json.loads((output / "candidate-tests/coverage.json").read_text()) if (output / "candidate-tests/coverage.json").exists() else {}
    # Coverage of executable added lines, not all text lines. None when no executable lines.
    added = {}
    for name in source_files:
        text = git(candidate, "diff", "--unified=0", "HEAD", "--", name)
        if name in metrics["untracked_files"] and (candidate / name).is_file():
            added[name] = set(range(1, len((candidate / name).read_text().splitlines()) + 1))
        else:
            added[name] = set()
            lineno = 0
            for line in text.splitlines():
                match = re.match(r"@@ .* \+(\d+)(?:,(\d+))? @@", line)
                if match:
                    lineno = int(match[1])
                elif line.startswith("+") and not line.startswith("+++"):
                    added[name].add(lineno); lineno += 1
                elif line.startswith(" "):
                    lineno += 1
    executable, covered = set(), set()
    for name, lines in added.items():
        data = cov.get("files", {}).get(name, {})
        executed = set(data.get("executed_lines", []))
        missing = set(data.get("missing_lines", []))
        executable.update((name, n) for n in lines & (executed | missing))
        covered.update((name, n) for n in lines & executed)
    result = dict(
        correctness_percent=100 * len(ftp_passed) / len(ftp),
        resolved=len(ftp_passed) == len(ftp) and hidden["returncode"] == 0 and not regressions_failed,
        fail_to_pass_passed=len(ftp_passed), fail_to_pass_total=len(ftp),
        regressions=regressions_failed,
        regression_preservation_percent=100 * (len(baseline_pass) - len(regressions_failed)) / len(baseline_pass) if baseline_pass else None,
        hidden_counts=hidden["counts"], candidate_test_counts=candidate_tests["counts"],
        candidate_added_tests=added_tests,
        candidate_coverage=candidate_tests.get("coverage_totals"),
        changed_executable_lines=len(executable), changed_covered_lines=len(covered),
        changed_line_coverage_percent=100 * len(covered) / len(executable) if executable else None,
        static_metrics=metrics,
        limitation="Maintenance, security and performance require rubric review; static counts are proxies. Hidden tests are source-only replay; package/build changes need a custom evaluator."
    )
    dump(output / "grade.json", result)
    return result
