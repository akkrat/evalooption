"""Check relocation of a resumed CLI session before continuing measured actors."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
from approach_eval.core import dump
from continuation_codex import Codex


def main():
    output = HERE / "preflight"
    output.mkdir(exist_ok=False)
    before, after = output / "before", output / "after"
    before.mkdir(); after.mkdir()
    (before / "marker.txt").write_text("original-checkout")
    (after / "marker.txt").write_text("relocated-checkout")
    settings = json.loads((HERE.parent.parent / "evaluation.json").read_text())
    settings.update(turn_timeout_seconds=300, max_run_seconds=900)
    client = Codex(output, settings)
    session, first = client.call("agent", before,
        "Calibration only. Run pwd and read marker.txt with a shell tool. Do not edit files or use browser tools. "
        "Return status done and message containing the exact marker and cwd.", stage="initial-checkout")
    session2, second = client.call("agent", after,
        "Calibration continuation: the workspace moved to " + str(after) + ". Run pwd, read marker.txt, "
        "and attempt to read " + str(before / "marker.txt") + ". That old path should be denied. "
        "Do not edit files or use browser tools. Return status done with message as a JSON object "
        "{cwd: actual pwd, marker: actual marker text, old_read_denied: boolean from the attempted read}.",
        session, stage="relocated-checkout")
    evidence = json.loads(second["message"])
    passed = (session == session2 and evidence["cwd"] == str(after)
              and evidence["marker"].strip() == "relocated-checkout"
              and evidence["old_read_denied"] is True)
    dump(output / "gate.json", {"passed": passed, "session": session, "first": first,
                               "second": second, "evidence": evidence})
    assert passed, evidence
    print("RESUME RELOCATION PREFLIGHT PASSED", flush=True)


if __name__ == "__main__":
    main()
