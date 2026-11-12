---
name: backtest-reviewer
description: Audit a backtest result for the ways backtests mislead - too few trades, no out-of-sample test, collapse out of sample, survivorship bias, failing to beat buy and hold, parameter sensitivity, results too good to be true, and drawdowns nobody would hold through - and give a verdict. Use when the user shares or has just run a backtest and asks whether it can be trusted, whether a strategy is overfitted, why live results differ from a backtest, or before they commit money to a tested strategy.
---

# Backtest Reviewer

Run this on every backtest before describing a strategy as working. It reads the JSON report printed by `backtest-runner`.

```bash
python ../backtest-runner/scripts/backtest.py --market IN --pit-universe 100 --strategy momentum_rotation \
  --range 10y --benchmark ^NSEI --split-date 2023-01-01 --alloc-pct 10 --max-positions 10 > report.json
python scripts/review_backtest.py report.json
```

## Checks and thresholds

| Check | High | Medium |
|---|---|---|
| `sample_size` | Under 30 closed trades | 30 to 99 |
| `history_length` | - | Under 5 years |
| `out_of_sample` | Out-of-sample return at or below zero, or under half of in-sample | No out-of-sample test was run |
| `benchmark` | Lower return and at least as deep a drawdown as buy and hold | Lower return only; out-of-sample return below the benchmark; no benchmark given |
| `survivorship_bias` | A momentum strategy tested on today's index members | Any other strategy on today's index members, or a hand-picked symbol list |
| `too_good` | - | Profit factor above 4 or win rate above 80% |
| `drawdown` | Above 60% | Above 40% |
| `parameter_sensitivity` | - | Under 60% of swept settings profitable; best setting more than double the median; hand-set parameters with no sweep |

**Verdict:** any high finding gives "do not rely on this result"; two or more medium findings give "weak evidence"; otherwise "no red flags on these checks".

## Delivering the verdict

State the verdict first, then the high findings with their numbers, then the medium ones. For each, give the specific re-run that would address it: add `--split-date`, switch to `--pit-universe`, add `--sweep` over neighbouring values, add `--benchmark`.

Be exact about what a clean review means. "No red flags on these checks" says the test was run properly. It does not say the strategy will make money: markets change, the remaining survivorship bias still flatters results, and a strategy that beat the index in one decade can lag in the next. Never upgrade a clean review to "this strategy works".

Equally, do not soften a bad one. If the result fails out of sample or loses to buy and hold, say that the tested rule shows no edge and that holding the index was the better choice over the period. That is a useful finding: it stopped money going into a rule that did not work.

A worked example worth quoting: `momentum_rotation` on today's Nifty 100 members showed 29% a year over ten years. The same rule on a point-in-time universe showed 12%, the same as the index, with a deeper drawdown. The first report gets "do not rely on this result"; the second gets "weak evidence".

## Limits

It audits the report, not the strategy logic or the data. It cannot detect lookahead inside a custom rule, wrong corporate-action handling, or unrealistic fills beyond what the runner already enforces. Thresholds are rules of thumb. It only reads reports from `backtest-runner`.
