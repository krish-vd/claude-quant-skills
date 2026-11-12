---
name: macro-regime
description: Read the cross-asset macro backdrop - US yield curve (10-year minus 3-month), credit risk appetite (high-yield versus investment-grade bonds), growth versus safety (copper versus gold), stocks versus bonds, the dollar, USD/INR, oil and volatility - each with trend and five-year range position, and a rule-based risk-on / mixed / risk-off summary. Use when the user asks about the macro environment, whether markets are risk-on or risk-off, the yield curve, inverted yield curve, credit spreads, the dollar's effect on emerging markets, or the big-picture backdrop before positioning.
---

# Macro Regime

```bash
python scripts/macro_regime.py
```

## What it measures

| Item | Series | Read as |
|---|---|---|
| Yield curve | ^TNX minus ^IRX | Inverted (short above long) has often preceded US recessions, with long and variable lags |
| Credit appetite | HYG / LQD | Rising = investors accept more credit risk |
| Growth vs safety | Copper / gold | Rising = industrial demand favoured |
| Stocks vs bonds | SPY / TLT | Rising = equities favoured |
| Volatility | VIX, one-year percentile | Top fifth = stress |
| Dollar | Dollar index trend | Rising usually tightens conditions for emerging markets, India included |
| Also shown | USD/INR, Brent, gold, Nifty, yields | Levels, 3-month change, five-year percentile |

Trends are each series against its 50-day average (±1%). Label: `risk_on` with four or more supportive items and at most one caution; `risk_off` with four or more cautions; otherwise `mixed`.

## Presenting it

Lead with the label and the cautions, then two or three sentences on what stands out: the curve, the direction of credit and copper/gold, and the dollar and rupee for an Indian investor. Point out disagreements between signals; they are common and informative.

Macro moves slowly and acts on markets with long, variable lags; a risk-off backdrop can coexist with rising stocks for months. Present this as background for position size and asset allocation, not as a timing tool, and do not forecast recessions, rate decisions or index levels.

For what is scheduled (RBI and Fed meetings, budget, inflation releases) use `market-news-brief`: there is no reliable free macro calendar, so dates must come from dated sources.

## Limits

US-centred: there is no reliable free source of Indian government bond yields or Indian macro data. Prices from an unofficial source (Yahoo); bond ETFs stand in for credit spreads. Five years of history.
