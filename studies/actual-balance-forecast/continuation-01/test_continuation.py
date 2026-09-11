import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[2]))
import continue_runner as runner


class ContinuationTests(unittest.TestCase):
    def fixture(self, root):
        source = root / "original"
        workspace = source / "workspace"
        (workspace / "specs").mkdir(parents=True)
        (workspace / "specs/context.md").write_text(str(workspace) + "/source.txt")
        (workspace / "source.txt").write_text("saved partial source")
        task = {"id": "fixture", "complexity": "large", "project": "Fixture project", "task": "Finish the feature"}
        data = {
            "manifest.json": {"task": task, "approach": "gennady", "fingerprint": {"sha256": "original"}},
            "result.json": {"status": "budget_exhausted", "stages": [{"stage": "setup", "session": "setup-id", "response": {"status": "done", "message": "Setup ready", "dispatches": []}, "seconds": 999}]},
            "conversation.json": [{"kind": "initial", "user_reply": "Original task with earlier prose", "shown_to_user": ""}],
            "turns.json": [{"index": 0, "role": "user", "stage": "discover", "session": "original-user"}, {"index": 1, "role": "agent", "stage": "discover", "session": "original-agent"}],
            "turns/001-agent-discover/response.json": {"status": "ask", "message": "Pending confirmation?", "dispatches": []},
        }
        for name, value in data.items():
            p = source / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(value))
        return source, task

    def test_copy_is_independent_and_retains_pending_question(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            source, task = self.fixture(root)
            candidate = root / "copy"
            recovered = runner.prepare_recovery(task, "gennady", source, candidate)
            (candidate / "source.txt").write_text("continued source")
            self.assertEqual((source / "workspace/source.txt").read_text(), "saved partial source")
            self.assertEqual((candidate / "specs/context.md").read_text(), str(candidate) + "/source.txt")
            self.assertEqual(recovered["agent_session"], "original-agent")
            self.assertEqual(recovered["pending_response"]["message"], "Pending confirmation?")
            self.assertEqual(recovered["stages"][0]["seconds"], 999)

    def test_resume_skips_completed_stage_and_counts_only_new_interactions(self):
        calls = []

        class FakeCodex:
            def __init__(self, directory, settings):
                self.turns = []
                self.dispatch_count = 0

            def call(self, role, cwd, prompt, session=None, stage="", **kwargs):
                calls.append((role, stage, session, prompt, cwd))
                self.turns.append({"role": role, "seconds": 0, "usage": {}, "estimated_api_cost_usd": 0})
                return session or "new-session", {"status": "done", "message": "Approved." if role == "user" else "Stage complete.", "dispatches": []}

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            source, task = self.fixture(root)
            settings = json.loads((HERE.parent / "evaluation.json").read_text())
            stages = [("setup", "Setup {task}", True), ("discover", "Discover {task}", True), ("execute", "Execute {task}", False)]
            with patch.object(runner, "Codex", FakeCodex), patch.object(runner, "stages", return_value=stages), patch.object(runner, "fingerprint", return_value={"sha256": "test"}), patch.object(runner, "grade", return_value={"fixture": True}), patch.object(runner, "git", return_value=""), patch.object(runner, "changes", return_value=[]):
                result = runner.run_one(task, "gennady", root / "continuation", settings, source)
            self.assertEqual(result["status"], "completed")
            self.assertFalse(any(c[1] == "setup" for c in calls))
            self.assertEqual(calls[0][:3], ("user", "discover", "original-user"))
            self.assertIn("Pending confirmation?", calls[0][3])
            self.assertEqual(calls[1][:3], ("agent", "discover", "original-agent"))
            self.assertEqual(next(c for c in calls if c[:2] == ("agent", "execute"))[2], None)
            self.assertEqual(result["user_interactions"], 3)
            self.assertEqual(result["user_words"], 3)
            self.assertEqual(result["questions"], 1)
            self.assertEqual((source / "workspace/source.txt").read_text(), "saved partial source")


if __name__ == "__main__":
    unittest.main()
