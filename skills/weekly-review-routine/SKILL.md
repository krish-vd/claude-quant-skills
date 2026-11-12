---
name: weekly-review-routine
description: Run a weekly trading and portfolio review by chaining the other skills - performance and rule adherence from the journal, open positions and their risk, upcoming results and ex-dates, market and sector changes over the week, and a short list of adjustments for next week. Use when the user asks for a weekly review, a weekend review, how their week went, what to prepare for next week, or a monthly review of their trading.
---

# Weekly Review Routine

Done once a week with the market closed. It looks back, then forward. It takes the user's journal as the record; if trades were not journalled, say that the review covers only what was recorded.

For a monthly review, run the same steps with the month's dates and compare with the previous month.

## 1. Results (`trade-review`)

Run for the week (`--from`, `--to`) and for the last 90 days for context. Report trades closed, net result, average R, and the split between trades that followed the plan and those that broke it. With fewer than 30 trades in the longer window, say the statistics are not yet reliable and treat patterns as hints.

Name the best and worst trade of the week and, for the worst, whether it had a stop and followed the plan.

## 2. Open positions (`trade-journal`, `market-data`, `risk-circuit-breaker`)

List open trades. For each, get the latest official close and show the distance to the stop and the unrealised result in R. Flag any position without a stop, and any that has moved through its stop but is still open. Then run the circuit breaker for the open-risk total and the month-to-date loss position.

## 3. What is coming (`results-calendar`, `fno-expiry-calendar`)

Holdings with results or ex-dates in the next two weeks. For derivatives traders, the expiries in the coming week and any holding in the F&O ban list.

## 4. The market's week (`market-posture-daily`, `sector-rotation`, `institutional-positioning`)

How the posture label and breadth changed over the week, which sectors moved up or down the ranking, and for India the direction of FII positioning and the week's FII and DII cash flows. Describe the change; do not forecast next week.

## 5. Process check

From steps 1 and 2, identify at most three specific, checkable points, for example: "two of five trades had no recorded stop", "both losses above 1R were trades that broke the plan", "open risk is 5.4% against a 6% cap". Use the user's own numbers. Avoid general advice.

## 6. Next week

A short list: positions needing a decision before a results date, stops to review, setups the user wants screened on Monday (`stock-screener`), and one process rule to hold to.

## Output

One page: results, open risk, events, market change, the three process points, next week's list. Lead with whatever needs action before Monday's open.

## Boundaries

Report the record as it is: do not soften a losing week or praise a winning one on a handful of trades. Do not tell the user to close or add to a position; give them the numbers and the dates. A week with no trades is a valid week: say so and review the market and the open positions only.
