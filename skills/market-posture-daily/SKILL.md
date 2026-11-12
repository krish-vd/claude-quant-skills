---
name: market-posture-daily
description: Produce a one-page daily read of market conditions for India or the US - index trend, breadth, new highs and lows, volatility index, FII positioning and cash flows (India), leading and lagging sectors - with a rule-based checklist labelled constructive, mixed or defensive. Use when the user asks for a morning or daily market summary, a market health check, whether conditions favour taking new trades, or a quick overview before the session.
---

# Market Posture Daily

One command that combines `market-breadth`, `institutional-positioning` and `sector-rotation` into a single page.

```bash
python scripts/posture.py --market IN                    # breadth on the Nifty 200
python scripts/posture.py --market IN --index nifty500
python scripts/posture.py --market US --symbols-file sp500.txt
```

The first run of the day fetches prices and takes a few minutes; later runs reuse the cache.

## The checklist

Each item is `supportive`, `caution` or `neutral` by a fixed rule:

| Item | Supportive | Caution |
|---|---|---|
| `index_above_200_day_average` | Index above it | Below |
| `index_50_day_above_200_day` | 50-day above 200-day | Below |
| `stocks_above_200_day_average` | 50% of stocks or more | 40% or fewer |
| `breadth_direction` | More stocks above their 50-day than 20 sessions ago | Fewer |
| `net_new_highs` | More 52-week highs than lows | More lows |
| `volatility_index` | In the lower half of its one-year range | In the top fifth |
| `fii_index_futures_positioning` (India) | FII long share higher than a week earlier | Lower |

**Label:** `constructive` with five or more supportive and at most one caution; `defensive` with four or more cautions; otherwise `mixed`.

## Writing the summary

Keep it to what fits on one screen:

1. Date (`as_of`) and the label, with the counts ("5 supportive, 2 cautions").
2. The cautions, each with its number. These are what a trader should know first.
3. Index and breadth in one or two sentences, including the direction of breadth.
4. Positioning and flows (India): FII long share now and a week ago, and the day's FII and DII net cash figures.
5. Sectors: leaders, laggards and anything moving up.
6. Any `data_problems`, stated plainly. A missing input means fewer checklist items; say which.

Tie it to the user's own process without telling them what to do: with a `defensive` label many traders reduce size or stand aside from breakouts; with `constructive` conditions breakout and momentum setups have historically had better odds. If they use `risk-circuit-breaker` or `pre-trade-checklist`, this is the context step before those.

The label is a count of rules, not a model and not a forecast. Do not say the market "will" do anything, and do not translate the label into buy or sell. Conditions can change within a session; this is yesterday's close until today's is final.

## Limits

End-of-day. Breadth uses today's index members on unofficial prices (recent gaps are filled from NSE). US has no positioning data and needs a symbol file for breadth. No news, macro calendar, earnings calendar or global cues.
