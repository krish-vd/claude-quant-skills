---
name: strategy-idea-pipeline
description: Turn a trading idea or market observation into a precise, testable rule, backtest it without writing code (a JSON rule file run by the backtest engine), stress it out of sample and across nearby settings, judge it with the backtest reviewer, and keep a record of each idea and its verdict. Use when the user has a trading idea to test ("buy when RSI is oversold in an uptrend", "does buying 52-week highs work"), wants to develop or improve a strategy, asks how to backtest their own rules, or wants to know whether a pattern they noticed is real.
---

# Strategy Idea Pipeline

From "I noticed something" to "this does or does not survive testing", in fixed stages. Most ideas fail; finding that out cheaply is the point.

## 1. Write the hypothesis

Get from the user: what they observed, why it might work (what behaviour it exploits, who is on the other side), market and universe, holding period. Write one testable sentence, for example: "Nifty 200 stocks above their 200-day average with a 2-day RSI under 10 outperform over the next few days."

If the idea depends on news, judgment or fundamentals over time, say the engine cannot test it directly and propose the nearest testable version.

## 2. Express it as a rule file

```json
{
  "entry": [["close", ">", "sma:200"], ["rsi:2", "<", 10]],
  "exit":  [["close", ">", "sma:5"]],
  "exit_mode": "any",
  "stop_atr_mult": 3,
  "rank_by": "roc:126"
}
```

- All `entry` conditions must hold. `exit_mode`: `any` (default) or `all`.
- Condition: `[left, op, right]`; ops `>` `<` `>=` `<=` `crosses_above` `crosses_below`.
- Terms: numbers; `close` `open` `high` `low` `volume`; `sma:N` `ema:N` `rsi:N` `atr:N` `roc:N` (fraction); `highest:N` `lowest:N` (the N sessions before today); `volume_sma:N`; `close_pct_of_highest:N`.
- `stop_atr_mult` sizes positions by risk and sets a stop; `rank_by` decides which signals win when slots are full. A rule needs an exit or a stop.

Examples: 52-week-high breakout `["close", ">", "highest:252"]`; volume surge `["volume", ">", "volume_sma:50"]` plus a price condition; golden cross `["sma:50", "crosses_above", "sma:200"]`.

Show the rule to the user and confirm it says what they meant.

## 3. Test

```bash
python ../backtest-runner/scripts/backtest.py --market IN --pit-universe 200 --rules idea.json \
  --range 10y --benchmark ^NSEI --split-date 2022-01-01 --monte-carlo 2000
```

Point-in-time universe for India, always a benchmark and a split date. For robustness, write two or three variants (for example RSI under 5, 10 and 15) and run each: a real effect survives nearby settings.

## 4. Judge

Run `backtest-reviewer` on each report, then state the verdict, whether out-of-sample results held, whether it beat buy and hold after costs, and the worst drawdown the user would have sat through.

## 5. Record

Offer an idea log in the user's working folder (markdown): date, hypothesis, rule file, settings, results, verdict, next step. Keeping rejected ideas with their numbers stops them being retested and fooling the user the second time.

## Discipline

- Never tune until the result looks good and report only that. Say how many variants were tried.
- Prefer simple rules with few parameters.
- A passing idea is a candidate for paper trading, not proof; suggest tracking it in `trade-journal` under its own setup tag first.
- Help the user test their ideas; do not offer ideas as "profitable strategies".
