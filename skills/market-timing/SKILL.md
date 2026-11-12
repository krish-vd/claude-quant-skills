---
name: market-timing
description: Check the index's price-and-volume timing signals - distribution days (heavy-volume declines) over the last 25 sessions, whether a rally attempt has produced a follow-through day after a correction, and a market-top warning checklist - for the Nifty 50 or the S&P 500. Use when the user asks whether the market is under distribution, if a correction has bottomed, whether there has been a follow-through day, if the market is topping, or whether conditions favour adding exposure.
---

# Market Timing

```bash
python scripts/market_timing.py --market IN
python scripts/market_timing.py --market US --with-breadth
python scripts/market_timing.py --market IN --index ^NSEBANK
```

## The rules (fixed and stated in the output)

| Signal | Rule |
|---|---|
| Distribution day | Index closes down 0.2% or more on higher volume than the previous session. Counted over the last 25 sessions; dropped once the index closes 5% or more above that day |
| Rally attempt | After a fall of at least 5% from the high, day 1 is the first up close off the low |
| Follow-through day | On day 4 or later of the attempt, a close up 1.25% or more on higher volume. The attempt fails if the index closes below the rally low |
| Top checklist | Five or more distribution days; close below the 21-day EMA; below the 50-day average; 50-day below 200-day; 7% or more off the 52-week closing high; (with `--with-breadth`) under 40% of stocks above their 50-day average. 0-1 warnings = low, 2-3 = elevated, 4+ = high |

For India the index has no volume in the free data, so the script uses the combined traded value of the Nifty 50 stocks as the volume series, and says so.

## Reading and presenting it

Report the date, the distribution count with the dates, the rally state (`no_correction`, `no_rally_attempt`, `rally_attempt` with its day number, `follow_through` with its date and gain, `follow_through_failed`, `attempt_failed`) and the top-checklist level with the items that are on.

How traders use it: a cluster of distribution days and an elevated or high checklist argue for smaller size and fewer new entries; a follow-through day marks the point where a new uptrend becomes possible, not certain. Combine with `market-posture-daily` (breadth) and `market-breadth`.

Be candid about the record: many follow-through days fail, and the market sometimes rises through a distribution cluster. These are risk-management context, never buy or sell instructions. Do not say the market "will" bottom or top.

## Limits

One index at a time, end of day, unofficial prices (Yahoo). India's volume is a proxy. Thresholds are conventions; the 1.25% follow-through threshold is a common modern setting, others use 1.5% or 1.7% (`--min-ftd-gain`).
