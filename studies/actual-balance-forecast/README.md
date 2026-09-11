# Actual Budget Balance Forecast comparison

This additional four-approach study replays [Actual Budget PR #7310](https://github.com/actualbudget/actual/pull/7310). The PR explicitly declares AI assistance; it is **not a human-only reference**. Results remain separate from the completed 3-task library matrix in `../../runs/suite/COMPARISON.md`.

## Completed results

All four trials, grading, quality dispositions, browser replays and the final audit are complete. Read the [comparison](COMPARISON.md), [browser/visual evidence](QA_REPORT.md), [measurements](MEASUREMENTS.json) and [audit](AUDIT.json). Prompt, plan and OpenSpec pass seven common browser obligations after adapting controls; Gennady submitted no implementation. All workflows reached a predeclared bound. These are bounded results, not a general approach ranking.

## Protocol

- Base: `2e0342574f9fded0d47113226904d17ba2bdfef1`; completed squash: `e8d95fdf6baaa03c896e8d11bc1d8dd18fb2f79c`.
- Identical product-only brief in `task.md`; no source paths, implementation plan, reference code, or future tests are exposed to actors.
- Codex CLI `0.153.4`, Luna medium simulated developer, Luna xhigh agents and fresh workflow workers. Real CLI exec/resume IDs and usage events are recorded.
- Four approaches: direct prompt, plan then implement, OpenSpec, Gennady SDD. Same pinned workflow packages as the original matrix. Gennady's Python-specific project label and gates are adapted to this TypeScript application, with explicit typecheck/lint/core/web gates.
- Public historical code may have appeared in model training; filesystem isolation cannot establish absence of memorization. One fresh run each, seeded order OpenSpec → Gennady → plan → prompt; concurrency 1 for trial workflows; separate post-trial quality reviews may overlap the next workflow. Wall time still reflects shared-service variability. Maximum 30 minutes per CLI call, 4 hours per approach, a 20M-token budget checked between CLI turns, 64 dispatches, and 8 questions/revisions per stage. A single CLI turn can overshoot the token threshold before its aggregate usage is reported.
- Human involvement counts developer replies, presented summaries, questions and reviews. Estimated reading/writing/decision time is a proxy; it excludes reading the full implementation/specification and is not a measured human study.
- API-equivalent cost is estimated from recorded tokens using the rates in `evaluation.json`; it is not measured subscription billing. No reset credit is used.

## Interpretation of bounded outcomes

This is a budget-constrained first pass. Prompt, plan and OpenSpec reached the 30-minute implementation-call cap; Gennady reached the eighth answered discovery request before a ninth confirmation could be delivered. These are censored workflow outcomes, not proof that the approaches cannot finish with larger budgets. The four-hour global cap does not remove the effect of a per-call cap, which can affect workflows with different stage sizes differently.

The initial brief and simulated-developer policy are identical, but downstream conversations can expand scope. Gennady's interview elicited separate mixed-currency series/minima, absent from the common brief, and switched to Russian. These are recorded process observations; extra scope is not rewarded by the common-task grader, and word-rate human-time estimates remain approximate across languages. Its first-pass result contains no product implementation, so code qualities are N/A rather than invented low or high scores.

## Runtime and isolation

Node 22.22.2, repository Yarn 4.13.0 and unchanged project `yarn.lock`; full immutable dependency installation. Playwright/Chromium 1.59.1, Vitest 4.1.4 and a separately locked matching coverage provider. Electron binary is omitted because this is the browser application. Production builds use `--skip-translations` to avoid fetching unpinned translations.

Every candidate gets a source-only base export, a new local `[AI]` snapshot commit, no upstream remotes/future objects, and separate CoW dependency trees preserving relative workspace links. Dependencies are read-only to actors except explicit generated caches. Planning stages cannot modify product source or tests. Simulator/reviewer sessions have no tools. Agent network access is mediated by the CLI proxy with localhost allowlisting and explicit local binding; this permits local previews and excludes external domains. Reference servers are stopped before measured actors run. Direct Chromium launch under Codex crashes because of macOS IPC restrictions. An evaluator-owned local browser runner accepts only a JavaScript path inside the candidate, runs it under separate Seatbelt filesystem/loopback restrictions, preserves planning source protection and dependency/Git protection, strips credentials, and returns recorded output. It is exposed uniformly through ACTUAL_BROWSER_RUNNER; each script has a maximum 240-second execution time. Native multi-agent/app/web/plugin/host-skill discovery is disabled; workflow worker dispatches use the recorded harness protocol.

`YARN_ENABLE_STRICT_SETTINGS=false` tolerates the CLI proxy's injected `YARN_NO_PROXY` variable, which Yarn 4 rejects as an unknown setting. Immutable installs and offline dependency settings remain enabled. This calibration change is applied uniformly before the study starts.

Evaluator-generated code runs under a separate macOS Seatbelt profile with access only to its replay/runtime/output directories inside the user's home. Test commands have no network; the browser/server adapter has loopback-only networking. Each browser uses a new profile/IndexedDB budget. Evaluator date instrumentation freezes browser and worker JavaScript at 2017-01-01; a recurring-payment assertion validates backend clock behavior. This is practical local isolation, not a claim of hostile-code VM isolation.

## Measurements and validation

`validation/gate.json` must pass before `run_study.py` starts. It requires base/completed builds, types and lint; full baseline unit tests; historical feature tests; discriminating browser checks; and real CLI medium/xhigh role/runtime/permission preflights. Original baseline has 622 core + 603 web tests passing, with 3 skipped. Regression obligations cover these two affected workspace suites; unrelated workspace suites and end-to-end bank synchronization are not included. The completed reference adds 15 core + 7 web tests.

The browser oracle uses only pre-existing account/schedule/transaction RPCs to create an empty deterministic budget and checks behavior through the visible UI: feature opt-in, dashboard entry, a year of monthly payments, exact minimum amount/date, daily agreement, shorter date range, saved settings after reload, and response to a posted debit. It does not import private forecast functions. Hidden tests also exercise historical edge cases, but their private-module imports are explicitly labeled **reference-structure compatibility**. A failure to match a UI selector requires inspection before declaring that an alternative implementation lacks that behavior. Unchecked edge cases remain limitations, not assumed successes. [Browser adjudication policy](QA_POLICY.md) preserves the original oracle while allowing separately recorded locator/format-only checks for alternative valid interfaces.

The grader replays product changes separately, restores original tests/fixtures/configuration for regression checks, runs candidate-authored tests separately, and measures production build/type/lint, added tests, and changed-production-file statement-line coverage. Test deletions/weakening cannot remove original regression obligations. Candidate tests, hidden historical checks, workflow completion and product behavior are separate outcomes. Coverage includes unexecuted source, and is not path coverage or a maintainability proof.

Upstream screenshot helpers are no-ops without VRT, and their stored images target Chromium/Linux. This macOS study uses deterministic local screenshots for review, **not** an assertion that upstream Linux visual snapshots pass. UI/reference similarity is not functional correctness.

## Commands

From the workspace root, use `.venv/bin/python studies/actual-balance-forecast/validate.py` for adapter validation and `.venv/bin/python studies/actual-balance-forecast/run_study.py` for the gated matrix. `preflight.py` checks user/agent permissions; `preflight_build.py` checks real actor build/tests/browser execution. Review recorded failures before retrying; the runner refuses to silently restart an incomplete trial. Original reports and engine files remain preserved under `../../runs/suite/frozen-harness/`.
