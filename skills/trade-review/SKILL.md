---
name: trade-review
description: Review trading performance from the trade journal - win rate, average win and loss, profit factor, expectancy, R-multiples, winning and losing streaks, drawdown of realised P&L, and breakdowns by setup, by month and by whether the plan was followed. Use when the user asks how their trading is going, wants a weekly or monthly review, asks which setups work for them, what their expectancy or win rate is, or whether breaking their rules is costing them.
---

# Trade Review

Reads the journal kept by the `trade-journal` skill and reports on closed trades.

```bash
python scripts/review.py                                   # everything
python scripts/review.py --from 2026-11-01 --to 2026-11-30 # one month, by exit date
```

## Reading the numbers

| Field | Meaning |
|---|---|
| `expectancy_per_trade` | Average profit or loss per trade in money |
| `avg_r`, `total_r` | Average and total result in units of planned risk. `avg_r` of 0.3 means each trade made 0.3x what it risked, on average |
| `win_rate_pct`, `payoff_ratio` | How often, and average win divided by average loss. Judge them together: 35% winners with a payoff ratio of 3 is a good system |
| `profit_factor` | Gross profit / gross loss. Above 1 is profitable |
| `max_drawdown_of_realised_pnl` | Largest peak-to-trough fall in cumulative closed P&L |
| `longest_losing_streak`, `current_streak` | Negative current streak = consecutive losses now |
| `by_setup`, `by_month` | The same statistics per setup tag and per month |
| `by_plan_adherence` | Trades where the plan was `followed`, `broke`, or `not recorded` |

## How to give the review

1. **Start with sample size.** Under 30 closed trades the script says the figures are unreliable. Say so first and present patterns as hints, not conclusions. Never call a setup "proven" or "broken" on a handful of trades.
2. **Lead with expectancy and average R**, not win rate. Win rate alone misleads.
3. **Compare `followed` with `broke`.** If trades that broke the plan lose more, that is the most actionable finding in the journal: put a number on it ("the 6 trades where you broke the plan cost 41,000; the 19 where you followed it made 63,000").
4. **Look across setups** for ones with enough trades to mean something, and point out any with clearly negative expectancy.
5. **Name the worst trade** and check whether it had a stop and followed the plan.
6. End with at most two or three specific, checkable changes that follow from the data (for example "no trade without a recorded stop"), not general advice.

Report what the data shows. Do not soften a losing record, and do not moralise about it either. If the journal has gaps (trades with no stop, plan adherence not recorded), say which statistics that weakens - `trades_without_a_stop` are missing from every R figure.

## Limits

- Only closed, journalled trades are counted. Open positions and unrecorded trades are invisible.
- Realised P&L drawdown is not account drawdown: it ignores open losses and deposits or withdrawals.
- These are past results from a small personal sample; they do not predict the next trade.
