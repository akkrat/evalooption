from __future__ import annotations

import json
import copy
import os
from pathlib import Path
import re
import shutil
import time
import datetime

from .core import ROOT, PYTHON, command, dump

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "status": {"type": "string", "enum": ["done", "ask", "blocked", "dispatch"]},
        "message": {"type": "string"},
        "dispatches": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["status", "message", "dispatches"],
}


class BudgetExceeded(RuntimeError):
    """A measured resource limit, not a broken evaluation harness."""

PROTOCOL = """You participate in a coding workflow. Return the specified JSON response.
Editing transport: use shell-based file edits in this workspace. The installed
Codex apply_patch tool does not work with this restricted permission profile.
Do not attempt apply_patch; use Python or another shell file-edit method directly.
Use non-login shells (login=false); do not launch bash -l or zsh -l. The harness
provides the complete Python, Node, Git and workflow-tool environment.
Use status=ask for a question requiring the user's response, done when this requested
stage is complete, blocked for an unresolvable obstacle. The message is shown to the
user verbatim, including the full plan/spec summary needed for review. Do not hide
questions in status=done. Do not call request_user_input: use status=ask instead.
Execute work yourself using your shell and edit tools. Only when an explicitly
loaded workflow directive requires a fresh subagent, return status=dispatch and put its
complete prompt in dispatches; the harness launches isolated Codex CLI sessions
with the SAME model and effort and resumes you with their responses. Use this
transport instead of native multi-agent tools or launching codex yourself.
Only solve the supplied task. Do not access the internet, other runs, original fixes,
or external project copies. The current repository is your entire project context.
Do not commit, alter git configuration, or modify the evaluation runtime. Validate
your work with available tests. Use the provided Python executable without installing
dependencies. All process invocations must remain within the sandbox.
"""


def toml_value(value):
    if isinstance(value, dict):
        return "{" + ", ".join(json.dumps(k) + " = " + toml_value(v) for k, v in value.items()) + "}"
    return json.dumps(value)


def usage_from_events(events):
    keys = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens",
            "output_tokens", "reasoning_output_tokens")
    total = dict.fromkeys(keys, 0)
    found = False
    for event in events:
        if event.get("type") == "turn.completed" and "usage" in event:
            found = True
            for key in keys:
                total[key] += event["usage"].get(key, 0)
    return total if found else None


def rollout_counter(paths, started_at):
    latest = None
    for path in paths:
        for line in Path(path).open():
            try:
                event = json.loads(line)
                timestamp = datetime.datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00")).timestamp()
                payload = event.get("payload", {})
                if timestamp < started_at or event.get("type") != "event_msg" or payload.get("type") != "token_count":
                    continue
                info = payload.get("info")
                if info and (latest is None or timestamp >= latest[0]):
                    latest = timestamp, info["total_token_usage"]
            except (ValueError, KeyError, TypeError):
                continue
    if latest is None:
        return None
    return {k: latest[1].get(k, 0) for k in ("input_tokens", "cached_input_tokens", "cache_write_input_tokens", "output_tokens", "reasoning_output_tokens")}


def estimate_cost(usage, rates):
    if usage is None:
        return None
    # Cached and cache-write inputs are subsets of input; reasoning is in output.
    regular = max(0, usage["input_tokens"] - usage["cached_input_tokens"]
                  - usage.get("cache_write_input_tokens", 0))
    return (regular * rates["input"] + usage["cached_input_tokens"] * rates["cached_input"]
            + usage.get("cache_write_input_tokens", 0) * rates["cache_write_input"]
            + usage["output_tokens"] * rates["output"]) / 1_000_000


class Codex:
    def __init__(self, run_dir, settings):
        self.run_dir = Path(run_dir)
        self.settings = settings
        self.turns = []
        self.started = time.monotonic()
        self.dispatch_count = 0
        self.schema = self.run_dir / "response.schema.json"
        dump(self.schema, SCHEMA)

    def call(self, role, cwd, prompt, session=None, stage="", read_only=False, artifact_only=False, _retry=0):
        if not all(p.resolve().is_relative_to(Path.home().resolve())
                   for p in (ROOT, Path(cwd), self.run_dir)):
            raise RuntimeError("Model runs require checkout and run directories under your home directory; "
                               "the supported Codex CLI does not isolate temporary-directory checkouts reliably.")
        used = sum((t.get("usage") or {}).get("input_tokens", 0)
                   + (t.get("usage") or {}).get("output_tokens", 0) for t in self.turns)
        if used >= self.settings["max_run_tokens"]:
            raise BudgetExceeded("Run token budget exhausted")
        remaining = self.settings["max_run_seconds"] - (time.monotonic() - self.started)
        if remaining <= 0:
            raise BudgetExceeded("Run wall-time budget exhausted")
        index = len(self.turns)
        label = f"{index:03d}-{role}-{re.sub(r'[^a-zA-Z0-9_-]', '_', stage)}"
        directory = self.run_dir / "turns" / label
        directory.mkdir(parents=True)
        scratch = (directory / "tmp").resolve()
        scratch.mkdir()
        (directory / "prompt.txt").write_text(prompt)
        cwd = Path(cwd).resolve()
        node_bin = Path(shutil.which("node") or "/opt/homebrew/bin/node").resolve().parent
        git_bin = Path("/Library/Developer/CommandLineTools/usr/bin")
        actor_path = ":".join(map(str, [PYTHON.parent, node_bin,
            ROOT / ".eval-cache/tooling/node_modules/.bin", git_bin])) + ":/usr/bin:/bin:/usr/sbin:/sbin"
        actor_env = {
            "PATH": actor_path, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_OPTIONAL_LOCKS": "0", "OPENSPEC_TELEMETRY": "0", "DO_NOT_TRACK": "1",
            "OPENSSL_CONF": "/dev/null", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "TMPDIR": str(scratch),
            "XDG_CONFIG_HOME": str(cwd / ".runtime-config"),
            "XDG_CACHE_HOME": str(cwd / ".runtime-cache"),
        }
        effort = self.settings["user_effort" if role == "user" else "agent_effort"]
        args = [shutil.which("codex") or "codex", "exec"]
        if session:
            args += ["resume", session]
        schema = copy.deepcopy(SCHEMA)
        if role != "agent":
            schema["properties"]["status"]["enum"] = ["done", "ask"] if role == "user" else ["done"]
            schema["properties"]["dispatches"]["maxItems"] = 0
        response_schema = directory / "schema.json"
        dump(response_schema, schema)
        args += ["--ignore-user-config", "--skip-git-repo-check", "--json",
                 "--model", self.settings["model"], "--output-schema", str(response_schema),
                 "--output-last-message", str(directory / "last.json")]
        settings = {
            "model_reasoning_effort": effort,
            "approval_policy": "never", "web_search": "disabled",
            "allow_login_shell": False,
            "project_doc_max_bytes": 0, "skills.include_instructions": False,
            "skills.bundled.enabled": False, "features.skip_host_skill_discovery": True,
            "features.plugins": False, "features.apps": False,
            "features.memories": False, "features.multi_agent": False,
            "suppress_unstable_features_warning": True,
            "features.shell_snapshot": False,
            "features.shell_tool": role == "agent",
            "features.apply_patch_freeform": False,
            "features.view_image": False,
            "shell_environment_policy.inherit": "core",
            "shell_environment_policy.exclude": ["*_KEY", "*_TOKEN", "*_SECRET", "*_PASSWORD"],
            "shell_environment_policy.set": actor_env,
            "default_permissions": "evaluation",
            "permissions": {"evaluation": {"filesystem": {
                ":minimal": "read",
                str(cwd): "read" if role != "agent" or read_only or artifact_only else "write",
                str(ROOT / ".venv"): "read",
                str(ROOT / ".eval-cache/tooling"): "read",
                str(Path(shutil.which("codex") or "codex").resolve().parent.parent): "read",
                str(Path(shutil.which("codex") or "codex")): "read",
                str(Path(shutil.which("node") or "/opt/homebrew/bin/node").resolve().parent.parent): "read",
                str(git_bin.parent.parent): "read",
                str(PYTHON.resolve().parent.parent): "read",
                str(scratch): "write",
            }, "network": {"enabled": False}}},
            "developer_instructions": ("You are simulating the human developer. Never use tools. "
                                       "Only return the requested JSON." if role == "user" else PROTOCOL)
        }
        if artifact_only:
            settings["developer_instructions"] += (
                "\nThis is a PLANNING-ONLY stage. Complete only the named stage. "
                "Source and tests are read-only. Write planning artifacts only; never implement the requested fix yet.\n")
            for name in (".workflow", "openspec", "specs", "tasks", ".sdd", ".runtime-config", ".runtime-cache", "AGENTS.md", "gennady.yaml"):
                settings["permissions"]["evaluation"]["filesystem"][str(cwd / name)] = "write"
        if role == "agent":
            # Codex protects Git metadata even inside a writable workspace.
            # Gennady's mandatory --wip verifier needs only this transient lock.
            settings["permissions"]["evaluation"]["filesystem"][str(cwd / ".git/gennady-verify.lock")] = "write"
        for key, value in settings.items():
            args += ["-c", f"{key}={toml_value(value)}"]
        args += ["-"]
        env = os.environ.copy()
        env.update(actor_env)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONNOUSERSITE"] = "1"
        env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        # Do not forward model credentials into child-agent command environments.
        settings_note = {k: v for k, v in settings.items() if k != "developer_instructions"}
        dump(directory / "settings.json", settings_note)
        print(f"  {label} ({effort})", flush=True)
        started_at = time.time()
        result = command(args, cwd, min(remaining, self.settings["turn_timeout_seconds"]), prompt, env)
        (directory / "events.jsonl").write_text(result.pop("stdout"))
        (directory / "stderr.log").write_text(result.pop("stderr"))
        events = []
        for line in (directory / "events.jsonl").read_text().splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        for event in events:
            if event.get("type") == "thread.started":
                session = event["thread_id"]
        usage = usage_from_events(events)
        usage_source = "turn.completed" if usage is not None else "unavailable"
        if usage is None and session and re.fullmatch(r"[0-9a-f-]{36}", session):
            home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
            usage = rollout_counter((home / "sessions").rglob("*" + session + ".jsonl"), started_at)
            if usage is not None:
                usage_source = "session_rollout_counter"
                dump(directory / "session-usage.json", dict(usage=usage, started_at=started_at,
                    note="Counter for this CLI invocation; may be partial after interruption."))
        record = dict(index=index, role=role, stage=stage, session=session, effort=effort,
                      model=self.settings["model"], usage=usage,
                      usage_source=usage_source, usage_is_partial=usage_source != "turn.completed", retry=_retry,
                      estimated_api_cost_usd=estimate_cost(usage, self.settings["cost_rates_per_million"]),
                      **result)
        self.turns.append(record)
        dump(self.run_dir / "turns.json", self.turns)
        failure = next((e for e in events if e.get("type") == "turn.failed"), None)
        if result["timed_out"]:
            raise BudgetExceeded(f"CLI turn timed out: {label}; partial usage may be unavailable")
        if result["returncode"] or failure:
            detail = failure.get("error", {}) if failure else {}
            if isinstance(detail, dict):
                detail = detail.get("message", "")
            if "usage limit" in str(detail).lower() and _retry < 3:
                record["interruption"] = "usage_limit"
                dump(self.run_dir / "turns.json", self.turns)
                delay = (5, 15, 30)[_retry]
                print(f"  Usage-limit interruption; resuming {label} in {delay}s (retry {_retry + 1}/3)", flush=True)
                time.sleep(delay)
                answer = self.call(role, cwd,
                    "Continue the previous interrupted request. Inspect saved progress and do not repeat completed actions. Return the required final JSON for the current stage." if session else prompt,
                    session, stage, read_only, artifact_only, _retry + 1)
                record["recovered"] = True
                dump(self.run_dir / "turns.json", self.turns)
                return answer
            raise RuntimeError(f"CLI failed: {label}: {detail or 'nonzero exit'}; see {directory}")
        if usage is None or session is None:
            raise RuntimeError(f"Missing completed-turn usage/session: {label}")
        try:
            response = json.loads((directory / "last.json").read_text())
            assert response["status"] in ("done", "ask", "blocked", "dispatch")
            assert isinstance(response["message"], str)
            assert isinstance(response["dispatches"], list)
        except (ValueError, OSError, KeyError, AssertionError) as exc:
            raise RuntimeError(f"Malformed protocol response: {label}") from exc
        dump(directory / "response.json", response)
        return session, response
