# evalooption

Compare coding workflows by replaying completed Git tasks from their pre-change commits. A simulated developer receives only project context and a task brief; a separate coding agent asks questions and implements the change. The evaluator checks the result against historical tests and measures correctness, regressions, coverage, developer interaction, time, tokens, and estimated cost.

Four workflows are included: direct prompting, plan then implement, [OpenSpec](https://github.com/Fission-AI/OpenSpec), and [Gennady SDD](https://github.com/RubaXa/gennady). Package versions and internal workflow identifiers are pinned in [the workflow lock](tasks/workflows.lock.json).

This is a standalone, checkout-based tool for **macOS**, with a Python/pytest grading adapter. It does not need the original author's workspace, saved results, or private projects. Running model trials requires an authenticated Codex CLI and access to the configured model. Linux/Windows execution needs a different sandbox adapter; this repository is not a self-contained wheel or hosted service.

## Set up a fresh checkout

Prerequisites: Python 3.12+, Node 20.19+ with npm, Git, Apple Command Line Tools, and Codex CLI on `PATH`. Use a Python executable that meets the version requirement. The runner uses macOS `sandbox-exec` for test isolation. Clone under your home directory, as shown below. The supported CLI’s temporary-directory access rules do not reliably isolate checkouts under `/tmp`; bootstrap, doctor, and model calls reject checkouts outside the home directory.

```sh
mkdir -p ~/Projects
cd ~/Projects
git clone https://github.com/akkrat/evalooption.git
cd evalooption
python3 scripts/bootstrap.py
.venv/bin/python -m approach_eval.cli list
.venv/bin/python -m approach_eval.cli validate
.venv/bin/python -m approach_eval.cli doctor
.venv/bin/python -m pytest -q
.venv/bin/python scripts/check_docs.py
```

Bootstrap creates `.venv/`, installs pinned Python and workflow dependencies, and clones the public task repositories into `.eval-cache/`. It needs network access but makes no model calls. Validation executes historical tests to confirm that they fail before the fix and pass afterward. Doctor returns a nonzero status until dependencies and all task validations are ready. Tests that exercise macOS isolation must run in a normal terminal; nesting them inside another restrictive sandbox can prevent `sandbox-exec` from launching.

Authentication is needed for model runs, not for fixture validation or unit tests. The defaults in [evaluation.json](evaluation.json) select Luna medium for the simulated developer and Luna xhigh for planning, implementation, workers, and review. Adjust the configuration to models available to your account before starting a pilot. Recorded prices are dated API-equivalent assumptions, not measured subscription charges.

## Run an evaluation

The following commands make model calls and consume account usage. Start with the runtime probe, then a pilot before the full matrix:

```sh
.venv/bin/python scripts/preflight.py
.venv/bin/python -m approach_eval.cli pilot --output runs/my-pilot --jobs 1
.venv/bin/python -m approach_eval.cli suite --pilot runs/my-pilot --output runs/my-suite --jobs 1
.venv/bin/python -m approach_eval.cli report runs/my-suite
```

The pilot draws one task using the configured seed and runs all four workflows. The suite requires a passing pilot protocol/measurement gate for the same code, configuration, task set, and dependency locks. A workflow can fail to solve the task and still satisfy the instrumentation gate. The default suite is three tasks × four workflows × one repetition; its serial schedule avoids concurrency affecting elapsed-time comparisons.

Keep run output directories under your home directory as well. Use new output directories when changing configuration or retrying completed trials. `pilot --recover-from runs/previous-pilot --output runs/new-pilot` supports calibration recovery. A suite always starts fresh. Budget and usage-limit failures stay visible; reset credits are never consumed automatically.

## Read your results

The `report` command writes `REPORT.md` and `results.json` inside the chosen output directory. Each trial preserves prompts, dialogues, session IDs, raw events, candidate changes, independent test results, coverage, and quality-review evidence. These files are generated locally and are excluded from Git.

Optional post-processing creates a more detailed comparison and fills missing reviews:

```sh
.venv/bin/python scripts/complete_reviews.py runs/my-suite
.venv/bin/python scripts/review_context.py runs/my-suite
.venv/bin/python scripts/report_details.py runs/my-suite
```

The first two commands make additional model calls. The last writes `COMPARISON.md` and `MEASUREMENTS.json` from saved evidence. See [methodology](docs/methodology.md) for metric definitions and limits.

The [HTML reporting guide](docs/reporting.md) covers an additional report builder for the historical four-task study and rebuilding an existing `data.json`. Its original results are not distributed in this repository. For a new/custom suite, use the CLI Markdown report above; the historical HTML importer needs adaptation to another study layout.

## Add a completed task

Write a brief describing the problem and desired behavior, without hints from the original implementation. Supply the base and completed commits, changed historical test files, and Python source roots:

```sh
.venv/bin/python scripts/add_task.py \
  --id my-task --repository /path/to/repository \
  --base BEFORE_SHA --fix COMPLETED_SHA \
  --brief /path/to/task.txt --project 'General project description' \
  --complexity medium --test-file tests/test_feature.py \
  --source-root my_package
```

The importer clones the repository and registers the task only after its tests distinguish the base from the completed implementation. Run a new pilot after changing the suite. This adapter handles Python package-source changes with pytest-compatible tests; additional dependencies, build systems, UI, or databases require an environment/grading adapter. Use `--full-test-target` when the project uses a different test layout.

The bundled fixtures are [Boltons #336](https://github.com/mahmoud/boltons/pull/336), [more-itertools #777](https://github.com/more-itertools/more-itertools/pull/777), and [Boltons #305](https://github.com/mahmoud/boltons/pull/305). Exact commits, briefs, source roots, and test targets live in [tasks/suite.json](tasks/suite.json).

## Repository map

| Path | Purpose |
|---|---|
| [approach_eval](approach_eval/) | CLI, sessions, workflows, isolation, grading |
| [tasks](tasks/) | Public fixtures and pinned workflow dependencies |
| [scripts](scripts/), [tests](tests/) | Setup, import, checks, post-processing |
| [reporting](reporting/) | Historical HTML report builder and optional local archiving |
| [docs](docs/) | Methodology, sources, reporting, calibration history |
| [studies](studies/) | Historical application and continuation adapters; require separate saved study state |

`runs/`, `.eval-cache/`, `analysis/`, `reports/`, and `exports/` are generated local directories. No result archive is committed or required to start a new library evaluation. Historical study notes describe earlier executions, not additional fresh-checkout setup steps. See [sources](docs/sources.md) for provenance and [calibration notes](docs/calibration-log.md) for known orchestration limits.
