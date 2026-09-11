# Harness calibration

These attempts are engineering calibration, not independent benchmark repetitions. All raw directories remain in `runs/`. The accepted pilot and subsequent full matrix use a frozen code/configuration fingerprint. The suite must not combine results from different fingerprints.

| Attempt | Finding and action |
|---|---|
| `pilot` | The simulated developer could emit the worker-dispatch variant of the response schema. Restricted the developer schema to answers and review corrections. |
| `pilot-v2` | Restricted Codex filesystem profiles exposed tool/runtime problems, including shell versus built-in patch behavior. The interrupted arm is retained. |
| `pilot-v3` | Gennady setup implemented the requested source change before planning approval. Added filesystem-enforced source/test protection to every planning stage. |
| `pilot-v4` | The simulator demanded completed implementation while reviewing setup, contradicting the stage boundary. Added explicit stage-specific review criteria for every preparation stage. Another arm was deliberately interrupted during calibration. |
| `pilot-v5` | Tool lookup, login-shell PATH rewriting, Git configuration access, and Node runtime visibility were inconsistent under the restricted profile. Stopped active calibration arms and fixed the shared runtime environment centrally. |
| `pilot-v6` | Three arms completed. Gennady reached nested phase execution, but its mandatory verifier could not write `.git/gennady-verify.lock`. Stopped the affected calibration after preserving the blocker evidence. Added a write grant for that exact transient lock; other Git metadata remains protected. |
| `pilot-v7` | The expanded preflight passed, including actual SDD verification and Git metadata protection. Prompt and plan completed. OpenSpec was interrupted by the CLI account usage limit. Gennady's own approval question caused the simulator to authorize implementation inside setup; extended stage context from final reviews to all planning-stage questions and reinforced the stage boundary on resume. |
| `pilot-v8` | Stage-specific approval handling worked. Prompt and plan completed; OpenSpec reached independent review; Gennady progressed through discovery. The CLI usage-limit error interrupted both remaining arms despite settings showing quota. Session metadata confirmed Luna was selected. |
| `pilot-v9` | Continues preserved v8 artifacts with recovery provenance instead of repeating finished planning. Adds bounded same-session retries for the reported quota bug, fallback token counters with partial-estimate flags, anonymous reviewer directories, and direct visible-prose accounting. All 12 harness tests passed before continuation. No reset credit was consumed. |

Additional grader calibration fixed hidden-file isolation, `/dev/null` access, and pytest ancestor-configuration discovery. The final validation records are in `.eval-cache/validation-v2/`; older validation directories are retained as engineering evidence. All three historical tasks have verified failing tests on the base and passing tests on the original fix.

Runtime preflights are timestamped under `.eval-cache/preflight-*/result.json`; the pilot's environment record identifies its probe. The expanded probe checks actual tool execution events for Node, Git, OpenSpec, Gennady and `sdd verify --wip`, permitted artifact writes, denied planning-source writes, denied unrelated Git metadata writes, and denied hidden-file reads.

Calibration changed orchestration and runtime behavior after observing model runs. Accordingly, the pilot is not an unbiased performance sample, and its timing/cost should not be pooled into the full matrix. The full matrix reruns every task/approach from a fresh base tree. Failures in that frozen matrix remain outcomes rather than being silently replaced by successful retries.
