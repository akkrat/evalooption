# Remaining exhausted runs

This study resumes three terminal `budget_exhausted` records: two library benchmark arms and the final Gennady calibration pilot. The four exhausted Actual Budget originals were already continued in `../actual-balance-forecast/continuation-01`, so they are not repeated. `agent_blocked` is a distinct outcome and is not automatically retried here.

The selected originals are:

- `runs/suite/boltons-spooled-io--prompt--0`
- `runs/suite/more-itertools-classify-unique--gennady--0`
- `runs/pilot-v9/boltons-copy-function--gennady` (calibration only)

See [PROTOCOL.md](PROTOCOL.md) for budget and measurement boundaries. `recovery.py` reconstructs the suspended single-child dispatch chain, resumes the interrupted leaf session, then hands its actual response back to each waiting parent session. Both Gennady originals stopped during nested audits. Completed stages and prior human prose are inherited context, not newly charged work.

The continuation retains Luna medium for the simulated developer and Luna xhigh for all agent/worker/reviewer calls. The source repositories are copied; every resumed CLI invocation explicitly selects its new directory. Existing snapshots, results, conversations, and evaluation evidence are preserved. No reference or evaluator feedback is supplied to participants.

Run from the project root:

```sh
.venv/bin/python -m pytest -q studies/library-continuation-01/test_recovery.py
# The following calibration runs only once in a fresh continuation study.
.venv/bin/python studies/library-continuation-01/preflight.py
.venv/bin/python studies/library-continuation-01/run_continuation.py
.venv/bin/python studies/library-continuation-01/finish.py
.venv/bin/python reporting/build_report.py
.venv/bin/python reporting/validate_report.py
```

Completed preflight/results are retained. Do not rerun preflight into its existing folder. The runner skips terminal result files, refuses uninspected partial directories, and checks its frozen fingerprint before resuming a schedule. A further budget extension requires a new study, not overwriting this one.

`MEASUREMENTS.json` and `COMPARISON.md` separate incremental and cumulative effort and label the pilot as calibration. Pilot cumulative totals include its v8 and v9 recovery lineage; the initial HTML pilot view shows just the v9 segment. Earlier harness versions and quota interruptions make those pilot totals unsuitable for benchmark aggregation. `AUDIT.json` verifies original artifacts and execution-code preservation. The HTML's library continuation view carries forward unresumed original arms with an explicit label; the pilot has separate initial and cumulative selectors and is excluded from benchmark summaries. Raw prompts, leaf/parent session IDs, tests, and reviews remain in `runs/`.

## Calibration context limitation

The v9 pilot itself recovered from v8. In this continuation, the runner's supplemental “Original task” reminder took v9's first reply, a discover-stage approval summary, rather than v8's original initial request. The original task still existed in the resumed sessions, saved brief, and specifications. The two benchmark continuations began from first-generation runs and used their actual initial requests. This limitation is recorded in `RESUME_AUDIT.json` and the comparison; the pilot is not a controlled benchmark. A future multi-hop recovery adapter should explicitly resolve the initial request through its ancestry. The executed, frozen runner is preserved rather than rewritten after measurement.
