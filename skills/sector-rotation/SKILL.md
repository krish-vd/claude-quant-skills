---
name: sector-rotation
description: Rank market sectors by relative strength against the index and show which are gaining or losing leadership - Nifty sector indices for India (Bank, IT, Auto, Pharma, FMCG, Metal, Realty, Energy, PSU Bank and others), sector ETFs for the US - with returns over 1 week to 12 months, trend status, rank change over the last month, and breadth by industry within an Indian index. Use when the user asks which sectors are leading or lagging, about sector rotation, where money is moving, the strongest or weakest sector, or wants to narrow a stock search to strong sectors.
---

# Sector Rotation

```bash
python scripts/sector_rotation.py --market IN
python scripts/sector_rotation.py --market US --shift 42
python scripts/sector_rotation.py --market IN --industry-breadth nifty500
```

## Reading the output

- `ranked_sectors`: one row per sector, strongest first.
  - `returns_pct`: 1w, 1m, 3m, 6m, 12m price returns.
  - `excess_vs_benchmark_pct`: the same, minus the benchmark (Nifty 50 or SPY).
  - `relative_strength_score`: 0.2 x 1-month + 0.4 x 3-month + 0.2 x 6-month + 0.2 x 12-month excess return. A blend, so one hot week does not dominate.
  - `rank`, `rank_before`, `rank_change`: today's rank, the rank `--shift` sessions ago (default 21), and the move. Positive means it climbed.
  - `above_sma50`, `above_sma200`: the sector's own trend.
- `leaders`, `laggards`, `biggest_rank_gainers`, `biggest_rank_losers`: shortcuts into the table.
- `industry_breadth` (with `--industry-breadth`): for each industry in the index with at least three members, the median 3-month return and the share of stocks above their 50-day average. This is an equal-weight view, so it can differ from the cap-weighted sector index when a few large stocks carry it.

## Giving the read

Present the table, then three observations: who leads and whether their trend confirms it (above both averages), who is moving up the ranks fastest (emerging strength, usually more useful than the current leader), and where index strength and industry breadth disagree.

To act on it, the natural next step is `stock-screener` on the leading sectors' stocks: run it on an index and look at the `industry` column of the results. Whether leadership persists is an empirical question; `backtest-runner` with `momentum_rotation` tests the stock-level version of the idea.

Keep the language descriptive. Sector leadership rotates, sometimes sharply after a policy or earnings surprise. Do not say a sector "will" outperform, and do not recommend an allocation.

## Limits

- Price returns only: no valuations, earnings or flows.
- India uses NSE sector indices and the US uses SPDR sector ETFs, both priced from an unofficial source (Yahoo). Sector index symbols on Yahoo occasionally change; a sector that fails to load is named in the notes.
- Sectors overlap (Bank sits inside Financial Services; PSU Bank inside Bank). Do not treat ranks as independent.
- A shortened history (new index) gives no score, and the sector is listed unranked.
