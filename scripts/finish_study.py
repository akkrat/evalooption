"""Wait for an already-running pilot, then run its gated full matrix and report."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=1)
    args = parser.parse_args()
    deadline = time.monotonic() + 4 * 60 * 60
    gate = args.pilot / "gate.json"
    print(f"Waiting for pilot gate: {gate}", flush=True)
    while not gate.exists():
        if time.monotonic() > deadline:
            raise SystemExit("Pilot did not produce a gate within four hours; suite not launched.")
        time.sleep(10)
    if not json.loads(gate.read_text())["passed"]:
        raise SystemExit("Pilot gate failed; suite not launched.")
    # The suite independently verifies the current fingerprint before model calls.
    result = subprocess.run([sys.executable, "-m", "approach_eval.cli", "suite",
        "--pilot", str(args.pilot), "--output", str(args.output), "--jobs", str(args.jobs)])
    if result.returncode:
        return result.returncode
    result = subprocess.run([sys.executable, "scripts/complete_reviews.py", str(args.output)])
    if result.returncode:
        return result.returncode
    result = subprocess.run([sys.executable, "scripts/review_context.py", str(args.output)])
    if result.returncode:
        return result.returncode
    return subprocess.run([sys.executable, "scripts/report_details.py", str(args.output)]).returncode


if __name__ == "__main__":
    sys.exit(main())
