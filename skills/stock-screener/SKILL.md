---
name: stock-screener
description: Screen Indian (Nifty 50 to Nifty 500, midcap, smallcap) or US stocks for strength - relative-strength rank, Minervini-style trend template, 52-week-high breakouts on volume, and volatility contraction (VCP-style tight bases) - with liquidity filters and an official NSE price cross-check. Use when the user asks which stocks are strongest, wants momentum or breakout candidates, asks for stocks in a stage-2 uptrend or near 52-week highs, wants a relative strength ranking, or wants a watchlist to research.
---

# Stock Screener

Ranks a universe by price strength and returns candidates with the numbers behind each one. It finds stocks worth researching; it does not say what to buy.

## Run it

```bash
# Nifty 500 stocks passing all eight trend-template conditions, liquid ones only
python scripts/screener.py --market IN --index nifty500 --screen trend_template --min-turnover 100000000

# Breakouts to a new 52-week closing high on 1.5x volume
python scripts/screener.py --market IN --index nifty200 --screen breakout

# US: relative-strength ranking of a list
python scripts/screener.py --market US --symbols AAPL,MSFT,NVDA,GOOGL,AMZN,META,JPM,XOM --screen rs --top 5
```

Screens (`--screen`):

| Screen | Passes when |
|---|---|
| `trend_template` | All eight: price above the 150 and 200-day averages; 150 above 200; 200 rising for a month; 50 above 150 and 200; price above 50; at least 30% above the 52-week low; within 25% of the 52-week high; RS rank 70 or more |
| `breakout` | Close above every close of the prior 252 sessions, on volume at least 1.5x the 50-day average |
| `new_high` | New 52-week closing high, any volume |
| `contraction` | Volatility contraction (a tight base, in the spirit of a VCP): close > SMA50 > SMA200; within 15% of the 52-week high; the last 10 sessions span at most 8% of price and under half the span of the last 40; and 10-day average volume below 80% of the 50-day average. Each row gives `pivot` (the 10-day high), `pct_below_pivot`, `range_10d_pct`, `range_40d_pct` and `volume_10d_vs_50d` |
| `rs` | Everything with a rank, sorted strongest first |

Filters: `--min-price`, `--min-turnover` (20-day average daily traded value, in rupees or dollars), `--min-rs`, `--top` (default 25). Results are sorted by RS rank, then closeness to the 52-week high.

## Reading a row

- `rs_rank` (1-99): percentile of a weighted 3/6/9/12-month return **within the universe screened**. A rank of 90 in the Nifty 50 is not the same as 90 in the Nifty 500. State the universe when quoting a rank.
- `trend_template_passed`: how many of the eight conditions hold; `trend_template_conditions` shows which.
- `volume_ratio_vs_50d`, `pct_below_52w_high`, `avg_daily_turnover_20d`: context for judging the setup and whether the stock is tradable at the user's size.
- `close_check` (India): the close compared with the official NSE bhavcopy for that date. `matches` means within 0.5%. If it says `differs`, a corporate action or bad data is likely: drop that row or verify it before using it.
- `as_of`: the session the screen describes. An unfinished session is never used, so during market hours this is the previous trading day. Always state it.

## What to do with the output

Present the top rows as a table, state the universe, date and screen, and repeat the `notes`. Then suggest the next research steps a careful trader would take: check results dates and news, look at the chart, and size any trade with `position-sizer` from a real stop. Offer to test the idea with `backtest-runner` (the `trend_momentum` strategy uses the same trend logic).

Do not rank the results as "best buys", predict that any of them will rise, or drop the caveats. A strong chart says nothing about valuation, earnings or governance.

## Limits

- Needs about a year of history; newer listings are skipped and listed in the notes.
- Price and volume only. No fundamentals, results, shareholding or news.
- US has no built-in index lists: pass symbols.
- First run on a large index fetches hundreds of price series and takes a few minutes.
