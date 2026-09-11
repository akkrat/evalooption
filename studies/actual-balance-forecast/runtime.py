"""Pinned application runtime and command recording for this separate study."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys

STUDY = Path(__file__).resolve().parent
ROOT = STUDY.parent.parent
CACHE = ROOT / ".eval-cache"
NODE = Path("~/.local/share/pi-node/node-v22.22.2-darwin-arm64/bin/node").expanduser()
GIT = Path("/Library/Developer/CommandLineTools/usr/bin/git")
BASE = CACHE / "actual-forecast/base"
GOLD = CACHE / "actual-forecast/gold"
YARN = ".yarn/releases/yarn-4.13.0.cjs"
sys.path.insert(0, str(ROOT))
from approach_eval.core import command, dump


def environment(tree):
    tree = Path(tree).resolve()
    temporary = tree / "node_modules/.cache/actual-eval-tmp"
    temporary.mkdir(parents=True, exist_ok=True)
    values = {key: value for key, value in os.environ.items()
              if key in ("HOME", "USER", "LOGNAME", "LANG")}
    values.update(PATH=str(NODE.parent) + ":/Library/Developer/CommandLineTools/usr/bin:/usr/bin:/bin:/usr/sbin:/sbin",
                  TMPDIR=str(temporary), CI="1", TZ="UTC", HUSKY="0",
                  GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1", GIT_OPTIONAL_LOCKS="0",
                  NPM_CONFIG_USERCONFIG="/dev/null", NPM_CONFIG_GLOBALCONFIG="/dev/null",
                  YARN_ENABLE_IMMUTABLE_INSTALLS="true", YARN_ENABLE_NETWORK="false",
                  YARN_ENABLE_STRICT_SETTINGS="false",
                  YARN_CACHE_FOLDER=str(CACHE / "actual-yarn-cache"),
                  PLAYWRIGHT_BROWSERS_PATH=str(CACHE / "actual-playwright"),
                  ELECTRON_SKIP_BINARY_DOWNLOAD="1", DEVELOPER_DIR="/Library/Developer/CommandLineTools")
    return values


def yarn(tree, args, output, timeout=900, isolated=True):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    argv=[NODE,YARN,*args]
    if isolated:
        from isolation import sandbox
        argv=sandbox(argv,tree,output,extra_reads=[CACHE/'actual-instrumentation'])
    result = command(argv, cwd=tree, env=environment(tree), timeout=timeout)
    (output / "stdout.log").write_text(result.pop("stdout"))
    (output / "stderr.log").write_text(result.pop("stderr"))
    dump(output / "command.json", result)
    print(output.name, "exit", result["returncode"], "seconds", result["seconds"], flush=True)
    return result


def clone_dependencies(destination):
    destination = Path(destination).resolve()
    if destination == BASE.resolve() or ROOT not in destination.parents:
        raise ValueError("Dependency clone requires another workspace-local tree")
    # Only generated dependency trees are replaced; application source is preserved.
    for existing in [destination / "node_modules", *destination.glob("packages/*/node_modules")]:
        if existing.is_symlink():
            existing.unlink()
        elif existing.exists():
            shutil.rmtree(existing)
    for source in [BASE / "node_modules", *BASE.glob("packages/*/node_modules")]:
        target = destination / source.relative_to(BASE)
        subprocess.run(["/bin/cp", "-cR", str(source), str(target)], check=True)
    shutil.copy2(BASE / ".yarn/install-state.gz", destination / ".yarn/install-state.gz")


def initialize_snapshot(tree):
    tree = Path(tree).resolve()
    if (tree / ".git").exists():
        return
    for args in (("init", "-q"),):
        subprocess.run([str(GIT), *args], cwd=tree, env=environment(tree), check=True)
    (tree / ".git/info/exclude").write_text(".eval-tmp/\n.eval-output/\n")
    for args in (("add", "."), ("-c", "user.name=Evaluation", "-c", "user.email=eval@localhost",
                                "-c", "core.hooksPath=/dev/null", "commit", "-qm", "[AI] Evaluation starting snapshot")):
        subprocess.run([str(GIT), *args], cwd=tree, env=environment(tree), check=True)


def test_counts(path):
    data = json.loads(Path(path).read_text())
    tests = {}
    for suite in data.get("testResults", []):
        filename = suite.get("name", "unknown")
        filename = "packages/" + filename.split("/packages/", 1)[1] if "/packages/" in filename else Path(filename).name
        for test in suite.get("assertionResults", []):
            tests[filename + "::" + test["fullName"]] = test["status"]
        if suite.get("status") == "failed" and not suite.get("assertionResults"):
            tests[filename + "::<suite loading>"] = "failed"
    return {"success": data.get("success", False), "total": data.get("numTotalTests", 0),
            "passed": data.get("numPassedTests", 0), "failed": data.get("numFailedTests", 0), "tests": tests}
