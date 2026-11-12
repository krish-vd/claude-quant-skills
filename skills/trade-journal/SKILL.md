---
name: trade-journal
description: Keep a trade journal in a local file - record each trade when it is opened (symbol, direction, entry, size, stop, target, setup, thesis), close it with the exit, fees, whether the plan was followed and lessons, and list open or closed trades. Works for stocks, futures and options in India or the US. Use when the user says they bought or sold something, wants to log, record or journal a trade, asks what positions they have open, or wants to close out and note a trade.
---

# Trade Journal

One JSON file on the user's machine (`~/.market-skills/journal.json` unless `--journal` is given). Nothing leaves the machine. The `trade-review` and `risk-circuit-breaker` skills read the same file.

## Run it

```bash
# Opened: bought 100 INFY at 500 with a stop at 480
python scripts/journal_cli.py open --symbol INFY --direction long --entry 500 --quantity 100 \
  --stop 480 --target 560 --setup breakout --thesis "Base breakout on results, volume 2x"

# Futures: 2 lots of NIFTY short at 25000 (lot size 65 goes in --multiplier)
python scripts/journal_cli.py open --symbol NIFTY --direction short --entry 25000 --quantity 2 \
  --multiplier 65 --stop 25100 --setup reversal

# Closed
python scripts/journal_cli.py close --id 1 --exit 540 --fees 240 --followed-plan \
  --notes "Exited at target. Entry was late by a day."

python scripts/journal_cli.py list                    # open trades
python scripts/journal_cli.py list --status closed --symbol INFY
```

## Recording an open trade

Collect and record at entry, not afterwards:

- **Symbol, direction, entry price, quantity.** For futures or options entered in lots, put the number of lots in `--quantity` and the lot size or contract multiplier in `--multiplier` (from `market-data`). For shares the multiplier is 1.
- **Stop.** This defines the planned risk, which every later statistic is measured against. If the user has no stop, record the trade anyway and tell them plainly that it cannot be measured in R and its risk is invisible to the circuit breaker. Do not invent a stop for them.
- **Setup:** a short, consistent tag (`breakout`, `pullback`, `earnings`, `reversal`). Reuse existing tags - run `list --status all` if unsure - or the per-setup review fragments.
- **Thesis:** the user's reason, in their own words. Do not write it for them or improve it.
- `--date` defaults to today; set it for trades entered earlier.

## Closing a trade

- `--exit`, `--fees` (the round-trip charges; get them from `trade-cost-calculator` if unknown).
- **`--followed-plan` or `--broke-plan`.** Ask the user directly. This is the most valuable field in the journal: it lets the review separate bad luck from broken rules. Leave it out if they do not answer; do not guess.
- `--notes`: what happened and what they would do differently.

The output shows `pnl` and `r_multiple` (profit or loss divided by planned risk). State both.

## Limits and care

- One entry and one exit per trade. For a partial exit, close the trade and open a new one for the remainder at the same entry price; say you are doing this.
- Closed trades cannot be edited by the script. To correct a mistake, edit the JSON file by hand; show the user the path in the output.
- The journal records what the user tells it. It is not a broker statement and does not fetch fills.
- Be matter-of-fact about losses. Record them the same way as wins; do not console or lecture.
