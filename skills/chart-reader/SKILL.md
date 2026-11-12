---
name: chart-reader
description: Read a price chart - a chart image the user uploads or a symbol - describing trend, swing structure (higher highs and lows), support and resistance zones, moving averages, volatility and the 52-week range, and check the reading against levels computed from actual prices. Stocks, indices, commodities and crypto, daily or weekly. Use when the user shares a chart screenshot, asks what a chart shows, where support or resistance is, whether a stock is in an uptrend, or wants a technical read.
---

# Chart Reader

```bash
python scripts/chart_levels.py RELIANCE --market IN
python scripts/chart_levels.py ^NSEI --timeframe weekly
python scripts/chart_levels.py GC=F
python scripts/chart_levels.py BTC-USD --market CRYPTO
```

## Two ways in

**A symbol:** run the script and read from its numbers.

**A chart image:** read the image, then, whenever the symbol is identifiable and covered, run the script and compare. Images mislead (compressed axes, log versus linear scale, indicators with unknown settings). Where your reading and the computed levels differ, trust the data and say so. If the symbol cannot be identified, say the levels are estimated by eye.

## What the script returns

- `structure` from the last three swing highs and lows.
- `support_zones` below and `resistance_zones` above the close: clusters of swing points within 1.5%, with range, mid, distance, number of touches and last touch. More and more recent touches matter more.
- `moving_averages` (20, 50, 200), `atr14` and `atr14_pct`, 52-week high and low.

## Writing the read

1. **Trend:** position against the 50 and 200-day averages, and the swing structure.
2. **Where price sits:** nearest support and resistance, distances in percent and in ATRs.
3. **Volatility:** ATR as a percent of price, i.e. how much room a stop needs.
4. **What would change the picture:** the level whose break ends the current structure (for an uptrend, the last swing low).

Pattern names (flag, cup, head and shoulders) are fine when clearly present, but say they are interpretations. No price targets, and never say a level "will" hold. If the user wants a trade plan, entry and stop are theirs; `position-sizer` and `pre-trade-checklist` follow.

## Limits

Levels from swing points only: no volume profile, trendlines or automatic pattern detection. Unofficial, split-adjusted prices. `--swing` and `--zone-pct` change what counts as a level.
