# Browser result adjudication

Written before any application trial result was recorded. The original browser oracle and raw results remain immutable.

A valid implementation may use different labels, routes, date/currency formatting, or a different save/navigation flow. An automated locator failure alone is not evidence that the required behavior is absent. Where the raw browser flow fails, inspect the submitted UI/code and, if necessary, record an additional candidate-specific browser run.

Permitted adaptations are limited to finding the corresponding visible control, navigating to the same saved report, or normalizing equivalent displayed date/currency formats. Keep the empty database, baseline fixture RPCs, account balance, transaction amounts, schedule recurrence, frozen time, selected date ranges, expected minimum values/dates, persistence check and posted-activity check unchanged. Do not invoke a candidate's private forecast API as a substitute for visible product behavior. Do not repair candidate code or change an expected result to match it.

Record the script, exact locator/format changes, observed values, screenshots, and statuses in a separate `adjudication` directory under the trial. Distinguish passed, proven behavior failure, unavailable functionality, and unverified due to infrastructure/selector mismatch. Extra QA time/cost is separate from actor workflow cost. Do not feed hidden checks, QA findings, or reference details back into any measured actor. Uniformly inspect every failed flow; preserve failures of the originally frozen oracle in reports.

The seven browser feature checks remain only a subset of the full brief. Transfer/filter/account-less edge cases require their own evidence; historical private-module tests are still compatibility evidence rather than architecture-neutral public behavior proof.
