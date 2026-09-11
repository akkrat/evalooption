> Historical study material. Saved runs, validation records, dependencies, and resumable sessions are not included in Git. These instructions require that separate study state; use the root README to start a new standalone evaluation.

# Observations from the continuation

This is additional work in resumed sessions, not a second independent trial. The original bounded results remain frozen. All actor decisions below came from the simulated developer and its agents; the evaluator supplied no grader or prior visual-review findings.

## OpenSpec

The resumed apply stage completed, followed by specification synchronization, local archiving, and simulated developer acceptance. Independent build, types and product lint passed, with no new original-suite regressions and 16 passing added tests. The agent workspace’s generated skill Markdown still caused full-root formatting failures; those files were byte-identical to the original workspace. The product replay excludes workflow artifacts, so its lint result answers a different question.

The continuation changed five product files: route loading, the card, the spreadsheet adapter, and core calculation/test code. The graph component was unchanged. See the separate browser/visual replay before concluding whether earlier UI issues remain.

Evidence: archive completion (local generated evidence), developer acceptance (local generated evidence), independent result (local generated evidence), blind review (local generated evidence).

## Gennady SDD

The original discovery cap was cleared. The workflow completed discovery, two-module decomposition, four-ticket scaffolding and critic reviews. Its root, module and infrastructure specifications and task tickets were revised repeatedly before being declared clean. Execution began only after roughly 150 additional CLI minutes.

A concrete handoff defect occurred during scaffolding: the coordinator included draft scenarios in its message but omitted them from the dispatch text. The fresh worker could not see the draft, asked the simulated developer, and reviewed the specification only. Later dispatches pointed to written ticket files, avoiding that omission. This is an observed interaction between the actor’s dispatch content and the harness’s explicit-message handoff, not evidence that every SDD implementation has this problem.

Execution stopped at the first infrastructure prerequisite. Node/Yarn checks, existing core/web tests, and browser-runner smoke checks passed. The worker reported 25 formatting discrepancies outside the ticket’s Target Files and a canonical E2E command that failed before configuration loading with a duplicate `/dev/null` argument. The simulated developer authorized a bounded specification/ticket correction. The retry passed an E2E test through the browser runner, but the mandatory formatting gate and canonical command remained blocked. The coordinator then returned a terminal blocked result rather than continuing product tickets.

The only submitted non-planning change was the Node version file. No feature implementation was submitted. Thus zero feature obligations were verified, and implementation quality is not assessable. The failure combines the workflow’s gates, the agent-authored verification contract, and the constrained execution environment; it does not establish that the feature itself is impossible to implement with SDD.

Evidence: omitted draft handoff (local generated evidence), worker review (local generated evidence), file-based handoff (local generated evidence), first blocked execution (local generated evidence), developer authorization (local generated evidence), retry evidence (local generated evidence), terminal result (local generated evidence).

The inherited SDD scope includes separate currency projections, an expansion beyond the common task brief elicited in the original discovery. The common-task grader does not reward that extra scope. One task and one continuation per approach cannot establish general superiority.

## Plan then implement

The original implementation session resumed, made further changes to the forecast spreadsheet adapter, shared rule handling, core tests and report E2E tests, then returned completion. The simulated developer accepted the completion report. Report controls and rendering source remained byte-identical to the original candidate, allowing the same equivalent-control replay bindings to be used; behavior is still checked again against the continued core/adapter implementation.

Evidence: implementation completion (local generated evidence), developer acceptance (local generated evidence), independent result (local generated evidence).

## Direct prompting

The original implementation session resumed and changed the core report calculation and its test. Report UI source remained byte-identical to the original candidate. After the first completion message, the simulated developer asked for explicit confirmation of five requirements; the agent revised its completion prose and the developer accepted it. This extra exchange is counted as developer involvement. Acceptance of that statement is not independent proof of those behaviors.

Evidence: implementation completion (local generated evidence), developer revision request (local generated evidence), revised statement (local generated evidence), acceptance (local generated evidence), independent result (local generated evidence).
