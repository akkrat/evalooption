"""Import a manually completed Git task, validate it, then append to the suite."""
import argparse
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from approach_eval.core import ROOT, CACHE, checked, dump, git
from approach_eval.grading import validate_task


def relative_path(value):
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or not path.parts or value.startswith("-"):
        raise argparse.ArgumentTypeError("Expected a repository-relative path without traversal")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--id", required=True)
    parser.add_argument("--repository", required=True, help="Clone URL or local repository path")
    parser.add_argument("--fix", required=True, help="Known completed commit")
    parser.add_argument("--base", help="Default: first parent of fix; for a PR supply its actual base")
    parser.add_argument("--brief", type=Path, required=True, help="Public task text with solution details removed")
    parser.add_argument("--project", required=True, help="Short general project description")
    parser.add_argument("--source-url", default="")
    parser.add_argument("--complexity", choices=["small", "medium", "larger"], required=True)
    parser.add_argument("--test-file", action="append", type=relative_path, required=True,
                        help="Changed original test file to install for hidden grading; repeatable")
    parser.add_argument("--test-target", action="append", type=relative_path)
    parser.add_argument("--full-test-target", action="append", type=relative_path)
    parser.add_argument("--source-root", action="append", type=relative_path, required=True,
                        help="Python package root eligible for candidate replay; repeatable")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]+", args.id):
        parser.error("id must contain lowercase letters, numbers and hyphens")
    manifest_path = ROOT / "tasks/suite.json"
    manifest = json.loads(manifest_path.read_text())
    if any(t["id"] == args.id for t in manifest["tasks"]):
        parser.error("Task id already exists; use a new id to preserve results")
    repository = CACHE / ("import-" + args.id)
    if not repository.exists():
        checked(["git", "clone", "--", args.repository, repository], timeout=600)
    fix = git(repository, "rev-parse", "--verify", args.fix + "^{commit}").strip()
    base = git(repository, "rev-parse", "--verify", (args.base or fix + "^") + "^{commit}").strip()
    task = dict(id=args.id, repo=repository.name, repository=args.repository,
                fix_commit=fix, base_commit=base, source_url=args.source_url,
                project=args.project, task=args.brief.read_text().strip(), complexity=args.complexity,
                test_files=args.test_file, test_targets=args.test_target or args.test_file,
                full_test_targets=args.full_test_target or ["tests"], source_roots=args.source_root,
                provenance="User-imported historical change; authorship and brief curated by importer.",
                notes="Validated locally before registration; Python source-only evaluator.")
    validation = validate_task(task, CACHE / "validation-v2" / task["id"])
    if not validation["valid"]:
        raise SystemExit("Task was NOT registered: reference fail-to-pass validation failed. Inspect .eval-cache/validation-v2/" + args.id)
    manifest["tasks"].append(task)
    dump(manifest_path, manifest)
    print(f"Registered {args.id} with {len(validation['fail_to_pass'])} discriminating tests. Run a new pilot for the changed suite.")


if __name__ == "__main__":
    main()
