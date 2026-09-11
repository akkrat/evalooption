"""Create workspace-local dependencies; run with Python 3.12 or newer."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run(*args, cwd=ROOT):
    subprocess.run([str(a) for a in args], cwd=cwd, check=True)


def main():
    if sys.version_info < (3, 12):
        raise SystemExit("Python 3.12+ is required")
    cache = ROOT / ".eval-cache"
    cache.mkdir(exist_ok=True)
    if not (ROOT / ".venv").exists():
        run(sys.executable, "-m", "venv", ROOT / ".venv")
    run(ROOT / ".venv/bin/python", "-m", "pip", "install", "-r", ROOT / "requirements.lock")
    for task in json.loads((ROOT / "tasks/suite.json").read_text())["tasks"]:
        repository = cache / task["repo"]
        if not repository.exists():
            run("git", "clone", task["repository"], repository)
        for revision in (task["base_commit"], task["fix_commit"]):
            run("git", "cat-file", "-e", revision + "^{commit}", cwd=repository)
    tooling = cache / "tooling"
    tooling.mkdir(exist_ok=True)
    shutil.copyfile(ROOT / "tasks/tooling-package.json", tooling / "package.json")
    shutil.copyfile(ROOT / "tasks/tooling-package-lock.json", tooling / "package-lock.json")
    run("npm", "ci", "--ignore-scripts", "--prefix", tooling)
    print("Ready. Authenticate Codex if needed, then run .venv/bin/python -m approach_eval.cli validate")


if __name__ == "__main__":
    main()
