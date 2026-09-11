# Methodology

## Unit of comparison

A run is `(task, approach, model, efforts, repetition)`. Every arm starts from the same exported base tree. Repositories have a newly initialized single-commit history with no remotes, original fix objects, or hidden tests. Runtime network access, web search, plugins, memories, and native untracked subagents are disabled. Custom filesystem permissions grant only minimal system reads, the current actor's workspace and shared runtime dependencies. The simulator has its own directory and no shell. Its input is only general project context, the task, and messages actually presented to it.

The installed Codex CLI's built-in patch tool fails under the restricted permission profiles tested here, while shell edits work. All evaluated actors are therefore explicitly instructed to use shell-based edits. Failed preliminary probes/pilot attempts are retained separately. Pytest runs with an explicit empty configuration and a repository-local root/conftest boundary; this avoids discovering evaluator-parent configuration. Baseline and candidate test selection use the same explicit target list and settings. Projects that depend on additional pytest settings require adapter changes.

All agent profiles permit the exact transient `.git/gennady-verify.lock` needed by Gennady's mandatory `--wip` verification. Other Git metadata remains protected. The expanded runtime preflight executes that verifier and checks both allowed and denied operations. The frozen run allowance is three hours per arm, with a ten-minute limit per CLI call; exhausted limits remain recorded outcomes.

The saved seed controls task selection and run ordering, not model sampling. Model calls are stochastic. Absolute runtime paths, package locks, commit pins, and transcripts make a run auditable; they do not guarantee byte-identical future responses. Two baseline Boltons failures concern socket tests blocked by the validation sandbox; the older stream task also has a Python-version-sensitive frozendict API test. Their exact test identities and output are retained in validation records.

Gennady requests for subagents are transported through structured `dispatch` responses; the Python harness starts fresh CLI sessions and resumes the orchestrator with worker outputs. Every worker uses Luna xhigh and is included in usage/cost. Plan implementation also starts fresh. Questions resume the same actor session. The simulation cannot supply facts absent from its brief: it answers that it does not know and asks the implementer to inspect the repository.

The initial persona reviews the agent's returned summaries. It does not open linked artifacts or inspect the final code diff. Consequently, human-time estimates describe **summary-review interaction burden**, not the cost of a thorough human code/specification review. Generated artifacts remain available for separate inspection, and the independent code reviewer sees the candidate diff. A full-artifact-review persona should be a separate controlled experiment rather than an unreported change between arms.

`scripts/report_details.py` is the reporting pass for human effort: it excludes simulator-only stage coaching and review instructions from reading words, and saves derived records in `MEASUREMENTS.json`. Legacy raw results through pilot-v8 retain their full-prompt proxy. New runs record only agent-visible prose directly. Use `COMPARISON.md` for consistent estimates. Reply words, interaction counts, tokens, timings, and test outcomes are unchanged. Word-rate estimates also do not normalize differences between languages.

## Measurements and grades

| Quality | Evidence | Interpretation |
|---|---|---|
| Correctness | Original fail-to-pass tests passing on candidate sources | Percentage plus all-passed indicator |
| Regression safety | Previously passing original tests still pass | New failures and preservation percentage |
| Developer involvement | Messages, questions, approvals, reply words, visible review words | Direct prose/interaction measurements |
| Human effort | Reading at 200 wpm, writing at 40 wpm, 20 seconds per decision | Configurable estimate; **not observed human time** |
| Usage | Completed CLI turn input, cached-input, output, reasoning tokens by role | Reasoning is a subset of output; cached input is a subset of input |
| Cost | Saved model rates applied to usage with cache distinctions | API-equivalent estimate; **not Codex subscription billing** |
| Latency | CLI duration, simulator duration, setup, run wall time | Network/model latency included; concurrency recorded |
| Coverage | Candidate-suite branch/line coverage and executable changed-line coverage | Coverage demonstrates execution, not assertion quality |
| Test contribution | Added test cases and pass outcomes | Original hidden tests remain evaluator-owned |
| Maintainability/readability | Fresh blind rubric review with evidence; source size/branch/function metrics | Judgment and static proxies, not long-term maintenance observations |
| Performance/security | Blind review flags, task tests where applicable | No generalized benchmark or security guarantee |
| Scope discipline | Changed files and source/documentation/test breakdown | Review unrelated churn; smaller is not inherently better |
| Workflow compliance | Stage boundaries, artifacts, fresh-session dispatches | Planning cannot silently implement before review |
| Reliability | Completed, blocked, harness-error outcomes and raw logs | Failed arms remain in reports |

Do not collapse these into an unexplained weighted winner. Correctness and regression safety are primary outcomes; compare costs and effort among outcomes that meet the task. Higher token use can be justified by better behavior. Model review uses the same family as implementers and may share biases.

The reviewer receives a fresh session, the task, source/test diff and measured outcomes. The review prompt omits the approach label and reference fix. Legacy reviews through pilot-v8 exposed the approach in their CLI working-directory path. New runs use opaque reviewer working-directory names and record `review_context_anonymous`. Source style can still hint at an approach, and the reviewer shares the implementer's model family; ratings remain model judgments.

The first matrix exposed a further review limitation: the prompt includes candidate failure counts and new-regression identities, but omits full baseline failure explanations and unchanged source. Several spooled-stream reviews penalize the three pre-existing failures or infer missing behavior from a diff. Preserve those ratings as recorded, but do not rank approaches on them. `scripts/review_context.py` applies a second protocol uniformly across the matrix: baseline failure identities/counts, complete changed source files, and newly added test files accompany the original evidence. Its `context-review/` artifacts, scores, time, and cost are separate from the original trial; no candidate or original score is changed. The detailed report displays both protocols and separately charges this extra assessment. The reviewers still share the implementer's model family and can make mistakes.

After the matrix, `scripts/complete_reviews.py` assesses candidates whose trials ended before quality review, using the same prompt and Luna xhigh setting. It preserves original workflow statuses and wall times, backs up pre-assessment results, and adds the assessment's tokens/cost to the reviewer totals. Supplemental assessment duration is stored separately, so an interrupted workflow never becomes "completed" just because its code was subsequently reviewed.

The CLI can report a usage-limit error while account settings still show remaining quota. No reset credit is consumed automatically. The harness retries that specific error up to three times by resuming the same session, with 5/15/30-second delays. Every interrupted invocation is retained. If its final JSONL usage event is missing, the evaluator reads only the matching session's token counters within that invocation's time window. Those counters reset per CLI invocation, so the last counter is used rather than summing cumulative updates or subtracting the previous resume's total. Recovered counters are flagged potentially partial; reports mark cost estimates accordingly. A recovered transport interruption can pass the pilot gate once orchestration and grading complete, but an unrecovered missing-usage failure cannot.

`pilot --recover-from <previous-pilot>` copies preserved candidate artifacts and resumes the first unfinished stage in a fresh session with previous user exchanges. It retains the original Git snapshot commit and records recovery provenance. Completed stages are inherited; code is independently regraded and reviewed. Recovery metrics describe the continuation, not a fresh performance trial. The full matrix always starts from clean historical snapshots and never uses pilot recovery artifacts.

## Independent grading

The evaluator exports another clean base tree and replays package source changes. It first runs original baseline tests, then installs the original changed test files and runs hidden acceptance tests. Candidate test edits cannot remove these assertions. A separate candidate tree runs the agent's own tests and measures coverage. Generated code runs in a separate Seatbelt sandbox without network or hidden evaluator-file contents, and with an environment whitelist. Filesystem metadata remains readable because Python and pytest need ancestor-path metadata. This starter adapter is deliberately for Python package-source tasks; packaging, dependency, build, database, UI, and distributed-system tasks require a task-specific evaluator and environment.

The test suite checks token accounting, process timeout cleanup, literal filesystem permission paths, no-future-history snapshots, JUnit outcome distinctions, and the actual historical fail-to-pass fixtures.

## Limits and follow-on experiments

Three public historical tasks and one repetition cannot establish statistical superiority. Model training may contain their fixes. Task descriptions are curated and relatively complete; ambiguity is not independently manipulated. User effort estimates omit interruptions, emotional/cognitive load, domain learning, and real review quality. New workflow bootstrap is charged per run; production amortization is a separate experiment. Gennady's large discovery protocol may expose a meaningful fixed cost on small tasks.

A stronger study should add multiple languages and repository sizes, ambiguous and complete briefs, bugs/features/refactors, prospective/private tasks, multiple repeats with paired uncertainty estimates, blinded human review, follow-up change tasks that directly measure maintenance, mutation testing of added tests, performance workloads, and an amortized-existing-spec arm. Record failures without tuning prompts selectively for the losing workflow.
