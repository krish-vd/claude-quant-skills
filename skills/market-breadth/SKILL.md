---
name: market-breadth
description: Measure market breadth and regime for Indian or US stocks - percent of stocks above their 20, 50 and 200-day averages, advances and declines, new 52-week highs and lows, the index trend, and the volatility index (India VIX or VIX) with its one-year percentile. Use when the user asks how the market is doing, whether the rally is broad or narrow, if it is a good environment for breakouts or swing trades, what market breadth or the advance-decline ratio is, or wants a daily market health check.
---

# Market Breadth

Shows how many stocks are taking part in a move, which the index alone hides.

```bash
python scripts/breadth.py --market IN --index nifty500          # default universe for India
python scripts/breadth.py --market IN --index niftysmallcap250
python scripts/breadth.py --market US --symbols-file sp500.txt  # US needs a symbol list
```

The first run on a large index takes a few minutes; prices are then cached for 12 hours.

## Reading the output

| Field | Reading |
|---|---|
| `pct_above_sma200` | Long-term participation. Above 60% is a broad uptrend; below 40% a broad downtrend |
| `pct_above_sma50`, `pct_above_sma50_20_sessions_ago` | Medium-term participation and whether it is rising or falling |
| `pct_above_sma20` | Short-term; swings fast |
| `advances`, `declines`, `advance_decline_ratio` | The latest session only |
| `new_52w_highs`, `new_52w_lows`, `net_new_highs` | Leadership. Rising index with shrinking new highs is a divergence worth naming |
| `posture`, `flags` | `broad_uptrend`, `broad_downtrend` or `mixed`, plus `washed_out` (20% or fewer above the 50-day) or `stretched` (85% or more). The exact rules are in `posture_rules` |
| `index_trend` | The index against its own 50 and 200-day averages and 52-week high |
| `volatility_index` | Level of India VIX or VIX and where it sits in its one-year range |
| `history` | Daily percent above the 50 and 200-day averages, to see the direction |

## Giving the read

State the date (`as_of`) and universe, then three things: the long-term picture (200-day participation and index trend), the direction (is the 50-day figure rising or falling against 20 sessions ago), and anything notable (a flag, a divergence between index and breadth, an extreme volatility percentile).

Link it to what the user does: breakout and momentum trades have historically worked better with broad participation and worse in a `broad_downtrend`. Say this as context for their own decision. The `backtest-runner` skill can test it for their strategy with `--regime-filter`.

Do not turn the posture label into a call. `washed_out` describes a condition; it is not a signal that the market will bounce. Breadth can stay weak or strong for months.

## Limits

- The universe is today's index members, on unofficial prices (Yahoo). For India, recent gaps in that source are filled from the official NSE bhavcopy and listed in `gaps_filled_from_official_nse_file`.
- Unfinished sessions are excluded, so during market hours the reading is for the previous session.
- No sector breakdown, no cumulative advance-decline line, no institutional flow data yet.
