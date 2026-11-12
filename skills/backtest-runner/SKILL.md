---
name: backtest-runner
description: Backtest a rule-based stock strategy on Indian (NSE) or US stocks with real trading costs, then stress it - out-of-sample split, parameter sweep, market-regime filter, Monte Carlo on the trade sequence, and a buy-and-hold benchmark. Use when the user asks whether a strategy works, wants to backtest breakouts, moving-average crossovers, RSI pullbacks or momentum, asks what CAGR, drawdown or win rate a rule had, wants to compare a strategy with holding the index, or wants to know if a backtest result is overfitted.
---

# Backtest Runner

Tests a long-only, daily-bar strategy across many stocks with one shared pool of capital. The engine cannot look ahead: a signal uses the day's close and fills at the next day's open, stops that gap fill at the worse open price, and every fill pays costs and slippage.

## Run it

```bash
# Basic: 55-day breakout on the Nifty 50, 5 years, compared with the index
python scripts/backtest.py --market IN --index nifty50 --strategy donchian_breakout \
  --benchmark ^NSEI --dp-charge 15.34

# US symbols with a commission
python scripts/backtest.py --market US --symbols AAPL,MSFT,NVDA,JPM,XOM \
  --strategy trend_momentum --benchmark SPY --brokerage 1

# The full examination
python scripts/backtest.py --market IN --index nifty100 --strategy trend_momentum --range 10y \
  --benchmark ^NSEI --regime-filter ^NSEI --split-date 2023-01-01 \
  --sweep near_high_pct=5,10,15 --sweep atr_mult=2,3,4 --monte-carlo 2000
```

Universe: `--index` (India: nifty50, niftynext50, nifty100, nifty200, nifty500, niftymidcap150, niftysmallcap250), `--symbols A,B,C`, `--symbols-file`, or `--pit-universe N`. Large universes take minutes on the first run; prices are cached for 12 hours.

**Prefer `--pit-universe N` for Indian backtests.** Instead of today's index members it rebuilds, for each past quarter, the N most traded NSE company shares as of that quarter, from bhavcopies dated before it. Stocks are bought only while they are in the universe, and ranking strategies rank within it. This removes most of the hindsight in the stock list. The first run downloads about ten years of daily files and several hundred price series, which takes several minutes. The output's `point_in_time_universe` section lists the historical members with no price history (delisted or merged): those are still missing, and they are mostly the worst performers, so the result is less biased, not unbiased.

```bash
python scripts/backtest.py --market IN --pit-universe 100 --strategy momentum_rotation --range 10y \
  --alloc-pct 10 --max-positions 10 --benchmark ^NSEI --split-date 2023-01-01
```

## Strategies and their parameters (`--param NAME=VALUE`)

| Strategy | Rule | Parameters (defaults) |
|---|---|---|
| `donchian_breakout` | Buy a close above the prior N-day high; sell a close below the prior M-day low; ATR stop | `entry_n` 55, `exit_n` 20, `atr_n` 20, `atr_mult` 2 |
| `sma_cross` | Buy when the fast average crosses above the slow; sell on the cross back | `fast_n` 50, `slow_n` 200, `atr_mult` 0 (no stop) |
| `rsi_pullback` | In an uptrend (close above SMA), buy when short RSI is oversold; sell on a close above a short SMA | `trend_n` 200, `rsi_n` 2, `rsi_below` 10, `exit_n` 5, `atr_mult` 0 |
| `trend_momentum` | Buy when close > SMA50 > SMA200 and near the 52-week high; sell a close below SMA50; ATR stop | `high_n` 252, `near_high_pct` 10, `atr_mult` 3 |
| `momentum_rotation` | Every `rebalance_days`, rank the whole universe by return from `lookback` to `skip` sessions ago; buy the top `top_n`, sell holdings that fall below rank `hold_n` or below their own SMA(`trend_n`) | `lookback` 126, `skip` 21, `top_n` 10, `hold_n` 20, `rebalance_days` 21, `trend_n` 200 (0 = off) |

`momentum_rotation` ranks stocks against each other, so it needs a real universe (an index, or 30+ symbols) and has no stop: set `--alloc-pct` to about 100 / `top_n` and `--max-positions` to `top_n`, for example `--param top_n=10 --alloc-pct 10 --max-positions 10`.

Sizing: with a stop, each trade risks `--risk-pct` of equity (default 1). Without one, each position takes `--alloc-pct` of equity (default 10). `--max-positions` (10) and `--max-position-pct` (20) cap concentration. When more signals fire than there are free slots, the strongest by the strategy's score are taken and the rest are counted in `skipped_entries`.

## How to judge the result - in this order

1. **Against the benchmark.** A strategy that makes less than buy-and-hold with similar drawdown has no reason to exist. Compare `cagr_pct` and `max_drawdown_pct` with `benchmark_buy_and_hold` first. Most simple rules lose this comparison; say so plainly.
2. **Trade count.** Under 30 closed trades, the statistics mean little. The script flags this.
3. **Out of sample** (`--split-date`). If out-of-sample CAGR or profit factor is far below in-sample, the rule was fitted to the past.
4. **Parameter sweep** (`--sweep`). Look at `profitable_share_pct` and the gap between `cagr_best_pct` and `cagr_median_pct`. Robust rules work across neighbouring settings. If only one setting works, it is noise. With `--split-date`, `best_out_of_sample` shows what the best in-sample setting did on unseen data: that, not the in-sample best, is the honest number.
5. **Monte Carlo** (`--monte-carlo 2000`). `max_drawdown_pct.p95` is a more realistic worst case than the single historical drawdown. Ask whether the user could sit through it.
6. **Costs.** `total_costs` against final profit. High-turnover rules often die here.

Always relay the `cautions` list. Never present a backtest as a forecast, and never tune parameters until the result looks good and then report that result as the expectation.

## What the numbers do not include

- **Survivorship bias.** An index universe is today's membership; stocks that were dropped (often after falling) are missing. This flatters every result. A hand-picked symbol list is worse: it was chosen knowing what did well.
  It is most severe for momentum strategies. Today's Nifty 100 contains the stocks that grew large by rising for years, and a momentum rule "finds" them with hindsight. A real ten-year run of `momentum_rotation` showed 29% a year on today's Nifty 100 members and 12% a year on a point-in-time top-100 universe, against 12% for the index: the difference was the bias. For Indian tests use `--pit-universe`; otherwise always pass `--split-date`, lead with the out-of-sample result, and describe earlier figures as an upper bound, never as the expected return.

After any run, pass the JSON to the `backtest-reviewer` skill for a verdict before describing the strategy to the user.
- **Dividends** are excluded on both sides (strategy and benchmark).
- **Costs are today's rates** applied to all years, not historical rates. Default slippage is 5 bps per fill; raise `--slippage-bps` for small caps.
- Long only. No shorting, intraday, F&O, liquidity or circuit-limit modelling.
- Prices come from Yahoo (unofficial), adjusted for splits and bonuses.
