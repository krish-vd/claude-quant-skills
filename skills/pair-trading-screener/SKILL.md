---
name: pair-trading-screener
description: Find statistically related pairs among a group of stocks and analyse them for pair trading - hedge ratio, Engle-Granger cointegration test, half-life of mean reversion, current spread z-score and return correlation - for NSE or US stocks. Use when the user asks about pair trading, statistical arbitrage, market-neutral trades, whether two stocks move together, or which pair in a sector has diverged.
---

# Pair Trading Screener

```bash
python scripts/pairs_screen.py --market IN --symbols HDFCBANK,ICICIBANK,KOTAKBANK,AXISBANK,SBIN
python scripts/pairs_screen.py --market US --symbols KO,PEP --range 5y
```

Give 2 to 30 symbols, ideally from the same industry. Every pair is tested on the dates both share.

## Method

1. Regress log(A) on log(B): the slope is the hedge ratio.
2. Augmented Dickey-Fuller test on the spread, compared with Engle-Granger critical values (1% -3.90, 5% -3.34, 10% -3.05). More negative means stronger evidence that the spread returns to its mean.
3. Half-life: sessions a gap typically takes to halve.
4. z-score: today's spread against its last 60 sessions.

## Presenting results

Lead with pairs cointegrated at 1% or 5% **and** with a business reason to be linked. Testing many pairs produces chance passes (about 5 per 100 at 5%); say so whenever several symbols were tested. `stretched_now` lists cointegrated pairs two or more standard deviations out, with which leg is rich.

Explain the structure without recommending it: long the cheap leg, short the rich leg, sized by value in the hedge ratio, exit as the spread returns towards its mean, stop if it widens further or the relationship breaks. Mention:

- In India, a short held overnight needs stock futures: lot sizes rarely match the hedge ratio, both legs need margin, positions roll at expiry.
- Costs on four legs (`trade-cost-calculator`) can eat a small spread.
- Relationships end (mergers, regulation, a change in one business). Re-test before trading.

## Limits

Two-stock pairs only; unofficial, split-adjusted prices; one lag in the test; the hedge ratio uses the whole window, which a live trade would not have known. Candidates for research, not recommendations.
