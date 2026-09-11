from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import tarfile
import time
import sys

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".eval-cache"
PYTHON = ROOT / ".venv/bin/python"


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(path)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def command(args, cwd=ROOT, timeout=180, input=None, env=None):
    start = time.monotonic()
    process = subprocess.Popen([str(a) for a in args], cwd=cwd, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, env=env, start_new_session=True)
    timed_out = False
    try:
        out, err = process.communicate(input, timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(process.pid, signal.SIGTERM)
        try:
            out, err = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            out, err = process.communicate()
    return dict(command=[str(a) for a in args], returncode=process.returncode,
                stdout=out, stderr=err, timed_out=timed_out,
                seconds=round(time.monotonic() - start, 3))


def checked(args, cwd=ROOT, **kwargs):
    result = command(args, cwd, **kwargs)
    if result["returncode"]:
        raise RuntimeError(f"{args}: {result['stderr'][-3000:]} {result['stdout'][-1000:]}")
    return result["stdout"]


def git(repo, *args):
    return checked(["git", "-c", "core.hooksPath=/dev/null", *args], repo)


def snapshot(repo, revision, destination):
    """Export only this tree; never expose future commits, refs, or remotes."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    data = subprocess.check_output(["git", "archive", "--format=tar", revision], cwd=repo)
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        archive.extractall(destination, filter="data")


def init_snapshot(path):
    git(path, "init", "-q")
    git(path, "add", ".")
    git(path, "-c", "user.name=Evaluation", "-c", "user.email=eval@localhost",
        "commit", "-qm", "Task starting snapshot")


def tasks():
    return json.loads((ROOT / "tasks/suite.json").read_text())["tasks"]


def config():
    return json.loads((ROOT / "evaluation.json").read_text())


def fingerprint(settings):
    return digest({"settings": settings, "tasks": tasks(), "python": sys.version,
        "locks": {name: (ROOT / name).read_text() for name in (
            "tasks/workflows.lock.json", "tasks/tooling-package-lock.json", "requirements.lock")},
        "code": {p.name: p.read_text() for p in (ROOT / "approach_eval").glob("*.py")}})
