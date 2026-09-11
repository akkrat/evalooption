# Reporting, original solutions, and sharing

The HTML report is an offline artifact built from saved evidence. Open `reports/comparison/index.html`; it also works through `python3 -m http.server 8000` from the project root. No CDN, external fonts, analytics, model calls, or network requests are required to view or rebuild it.

## Rebuild an existing report

```sh
python3 reporting/build_report.py --from-data reports/comparison/data.json
```

Validate all metric mappings and artifact links with `python3 reporting/validate_report.py`. This uses only the Python standard library. The output is reproducible from the saved JSON and template. Its generation date and input hashes are preserved when rebuilding. Keep the report inside the extracted project: artifact links are relative to that project root.

The data schema records task and commit provenance, separate initial/continuation phases, original solution measurements, candidate metrics, judged quality and its evidence, exact model prompts and responses, developer-facing exchanges, three-way code diffs, and a searchable artifact index. Missing measurements use `null`, not zero. The HTML renders untrusted text as text; code and dialogue are not executed.

## Generate a comparison from this study's raw results

```sh
.venv/bin/python reporting/export_repositories.py
.venv/bin/python reporting/baselines.py
.venv/bin/python reporting/build_report.py
```

`export_repositories.py` requires the local upstream Git caches and exports the exact before-task and reference commits with their original licenses and lockfiles. `baselines.py` makes **new test and Luna xhigh review calls** in `analysis/references/`. It never modifies the frozen trials. The original solution gets the same library grading adapter and baseline-context quality rubric; Actual Budget uses the same full core/web coverage adapter and application review rubric. Its already-measured reference build, type, lint, and browser outcomes are reused. The library baseline harness also checks preservation of pre-change tests.

Reference reviews are post-study model judgments. They use anonymous reviewer workspaces and the same rubric and task context, but are not a new randomized or independently calibrated study. The reference's own historical tests helped define the task, so they are not independent acceptance evidence. The Actual reference is explicitly AI-assisted.

Reference measurement creation refuses to overwrite partial workspaces. Completed measurements and reviews are reused. A interrupted or failed analysis should be inspected and archived before using a new analysis location; never silently overwrite a failed trial to make a report look complete. `build_report.py` currently imports the fixed library suite and Actual Budget study layout; for another study, add an importer into the normalized report schema. The general CLI can already report arbitrary suites in Markdown.

## Reading the comparison

- **Before-task baseline** is the commit before the change. **Original solution/reference** is the historical completed change. Candidates are compared with both. Exact code agreement does not prove quality; different architectures can be valid.
- **Workflow completion** is distinct from historical acceptance, preserved regressions, and browser replay. The initial application trials were capped; continuation resumes those same sessions. Cumulative time, prose, tokens and cost must not be added again to initial values.
- **Actor cost** includes simulated developer, coordinator/implementer, and dispatched workers, excluding independent review. This normalizes the older library summary, which highlighted agent-only costs. Partial usage is a lower bound. These are API-equivalent estimates using the recorded 2026-09-09 rate card, not subscription charges.
- **Workflow minutes** exclude setup and grading. Library workflow time is recorded implementation plus simulated-user time; application time uses its explicit workflow timer. Human minutes are a reading/writing/interaction proxy, not measured human labor. Full code and spec review time is unknown.
- **Coverage** compares the newly added executable Python lines or Istanbul statement-start lines. These definitions are not interchangeable across languages. Type-only lines, comments and continuation lines are excluded. Missing mappings remain visible. Whole-changed-file coverage is also retained in raw grades but is not substituted for added-line coverage.
- **Quality** uses a 1–5 rubric for maintainability, readability, test quality, performance, and security; the app adds requirements and UI/accessibility. No benchmark or security audit was performed. Model scores are fallible and not suitable for statistical rankings. Reviewer inputs and outputs are preserved.
- **Browser evidence** distinguishes the strict original checker from later equivalent-control adjudication. The three implemented app candidates pass the seven common checks, with documented remaining visual defects. A private-import test-suite load failure does not mean a zero-obligation pass.
- **Dialogues** distinguish prose shown to the simulated developer from harness prompts and worker exchanges. The execution trace includes all saved role/stage calls; raw CLI events remain linked. Continuation prose does not duplicate the original phase.

## Export, verify, restore

```sh
python3 reporting/archive_results.py --list
python3 reporting/archive_results.py --output exports/evaluation-results.tar.gz
python3 reporting/archive_results.py --verify exports/evaluation-results.tar.gz
python3 reporting/archive_results.py --extract exports/evaluation-results.tar.gz \
  --destination /tmp/evaluation-review
cd /tmp/evaluation-review
python3 reporting/build_report.py --from-data reports/comparison/data.json
python3 -m http.server 8000
```

The default archive includes all local runs, including calibration and failed attempts, application validation/preflight evidence, candidate source/test workspaces, frozen execution engines, prompts, conversations, model and test logs, coverage databases/JSON, screenshots, reference analysis, exact upstream source archives, report data, and the authored harness/report code. `ARCHIVE_MANIFEST.json` records every included file's size and SHA-256, the harness Git commit, exclusions, and restoration instructions. A sibling `.sha256` covers the entire compressed archive.

Dependency trees, browser binaries, Git object databases, caches, generated application build bundles, and known credential filenames are excluded. Evaluator build logs are retained. Symlinks are recorded as exclusions and never followed. Original locks and source licenses are retained. All original included evidence is byte-preserved, including historical absolute host paths: this is a reproducible research bundle, not an anonymized dataset. It never reads the global Codex auth or session store. Review the dialogue and logs before sharing beyond your intended audience.

The verifier checks all file hashes, missing/extra/duplicate entries, unsafe paths and non-regular members. Extraction verifies first, requires a new destination, and uses Python's data extraction filter. It does not execute anything from the archive. Refuse to treat a matching self-contained manifest as proof of authorship: validate the externally supplied archive SHA-256 when authenticity matters.

The archive can be large because it includes raw evidence and repeated evaluation trees. `--list` shows its scope before compression; failed creation leaves a `.partial` file rather than a misleading completed archive. Stop active studies before exporting. Dependencies must be installed separately to execute tests; HTML reconstruction does not require them. Source snapshots have no Git history, but their provenance identifies exact upstream commits. The harness Git repository intentionally contains authored source/configuration/docs, not multi-gigabyte generated evidence. This release also includes `analysis/harness.bundle`: use `git clone analysis/harness.bundle /path/to/new-checkout` to recover its Git history independently of the result trees.

## Extension points and missing dimensions

The schema preserves evidence rather than collapsing it into a single winner score. Further studies should add repeated randomized trials, independent human review, mutation testing, branch/path coverage, realistic performance datasets, actual human interaction timing, delayed maintenance tasks, and adversarial or accessibility checks. Those dimensions are currently unmeasured, not silently treated as satisfactory. Repeated tasks, larger samples and reviewed task briefs are needed before drawing general conclusions about a workflow.

## Additional library continuations

When `studies/library-continuation-01/MEASUREMENTS.json` exists, the HTML imports the two benchmark continuations plus the original and continued calibration pilot. For a library continuation, unresumed approaches carry their original measurements and an explicit label. The pilot is available only through its separate calibration phase choices. Do not average it into the benchmark or interpret carried-forward arms as having received the new budget. The first application and library evidence archives remain historical snapshots; create a new export filename for updated results.
