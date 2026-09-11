from pathlib import Path
import os
import shutil

from .core import CACHE, PYTHON, checked, dump

APPROACHES = ("prompt", "plan", "openspec", "gennady")
TOOLING = CACHE / "tooling/node_modules"


def install(approach, tree, task):
    if approach == "openspec":
        env = dict(os.environ, OPENSPEC_TELEMETRY="0", DO_NOT_TRACK="1")
        checked([TOOLING / ".bin/openspec", "init", tree, "--tools", "codex",
                 "--profile", "core", "--no-animation"], env=env)
    elif approach == "gennady":
        package = TOOLING / "gennady"
        shutil.copytree(package / "ai/directives", tree / "ai/directives")
        shutil.copytree(package / "ai/skills", tree / ".agents/skills")
        # Upstream skills have a machine-specific author checkout. Adapt only the
        # installation path; preserve the directives themselves byte-for-byte.
        for path in (tree / ".agents/skills").rglob("SKILL.md"):
            path.write_text(path.read_text().replace("~/Developer/gennady/", ""))
        # Gennady's anystack plugin discovers this explicit non-Node gate.
        (tree / "gennady.yaml").write_text(
            "stack:\n  use: [anystack]\n  anystack:\n    extraGates:\n      - id: tests\n        argv: [" +
            ", ".join('"' + str(s) + '"' for s in [PYTHON, "-m", "pytest", "-q", "-c", "/dev/null", "--rootdir=.", "--confcutdir=.", "-o", "addopts=", *task["test_targets"]]) + "]\n")


def stages(approach):
    if approach == "prompt":
        return [("implement", "Do the task. Here is the task:\n{task}", False)]
    if approach == "plan":
        return [
            ("plan", "Plan the given task. Inspect the repository and write the resulting concrete plan to .workflow/plan.md. Ask the user about material ambiguity. Present the plan for review. Do not implement yet.\n{task}", True),
            ("implement", "Implement the approved plan in .workflow/plan.md. Read it in full, implement and verify it.\n{task}", False),
        ]
    if approach == "openspec":
        return [
            ("propose", "Read .agents/skills/openspec-propose/SKILL.md and follow it for this task. Do not implement yet.\n{task}", True),
            ("apply", "The user has reviewed and approved the proposal. Read .agents/skills/openspec-apply-change/SKILL.md (or find the generated openspec-apply skill) and apply the approved change.\n{task}", False),
            ("archive", "Read the generated openspec archive skill and follow it, including validation and spec synchronization. The user authorizes local archiving of this completed change.\n{task}", False),
        ]
    return [
        ("setup", "Read .agents/skills/sdd-setup/SKILL.md and apply it. Bootstrap a portal for this existing Python library, scoped to the requested change and the minimal relevant infrastructure.\n{task}", True),
        ("discover", "Read .agents/skills/sdd-discover/SKILL.md and follow it to discover the library scope for this task, using the portal. Interview the user as required.\n{task}", True),
        ("decompose", "Read .agents/skills/sdd-module-decomposition/SKILL.md and follow it for the discovered library scope. Keep the decomposition proportional to this task.\n{task}", True),
        ("scaffold", "Read .agents/skills/sdd-scaffold/SKILL.md and follow it to generate the task DAG for the requested change.\n{task}", True),
        ("critic", "Read .agents/skills/sdd-critic/SKILL.md and follow it for the generated specs and task tickets. Use fresh dispatches for independent critics, as the directive requires.\n{task}", True),
        ("execute", "Read .agents/skills/sdd-execute-batch/SKILL.md and .agents/skills/sdd-execute/SKILL.md in full. Execute all ready tickets via the specified fresh phase agents and audits, carrying handoffs until the task DAG is done or blocked. You are the orchestrator: use status=dispatch to launch each required isolated worker via the harness. Workers can run shell and edit code directly.\n{task}", False),
    ]
