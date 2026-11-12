---
name: mf-returns
description: Analyse an Indian mutual fund's track record from its NAV history - trailing returns (1 month to 10 years), rolling-return distribution, maximum drawdown, volatility, and what a monthly SIP actually earned (XIRR) - and compare funds side by side. Use when the user asks how a mutual fund has performed, wants to compare two funds, asks for rolling returns, the worst fall of a fund, or what their SIP in a fund would have made.
---

# Mutual Fund Returns

```bash
python scripts/mf_returns.py --scheme-code 122639
python scripts/mf_returns.py --scheme-code 122639 --scheme-code 120716 --sip-amount 15000
```

Find scheme codes with the `market-data` skill: `mf-search "parag parikh flexi cap direct growth"`. Pick the exact plan and option the user holds or would buy. Direct and Regular plans have different returns; use the **Growth** option for return analysis (IDCW NAVs drop at each payout, so their returns here are understated).

## Reading the output

| Field | Meaning |
|---|---|
| `trailing_returns_pct` | Returns ending at the latest NAV. Up to 1 year absolute; 3y, 5y, 10y annualised |
| `rolling_returns` | For every 1, 3 or 5-year window in the fund's history: minimum, quartiles, median, maximum, and the share of windows that lost money |
| `risk.max_drawdown_pct` | The fund's worst peak-to-trough fall, with dates |
| `risk.annualised_volatility_pct` | Variability of daily returns, annualised |
| `sip_actual` | What a monthly SIP over the last 3, 5, 10 years and since inception returned, as XIRR |
| `official_check` | Whether the mirror's latest NAV agrees with AMFI's official file |

## How to present and compare

- **Prefer rolling returns to trailing returns.** A trailing figure depends entirely on today's date and the start date; the rolling distribution shows what investors typically got and the worst case. Quote the median and the minimum together.
- **Put the drawdown next to the return.** "18% a year with a 31% fall in 2020" is the honest statement.
- Compare funds only **within the same category** and over the **same period**. A newer fund has not been through the same markets: check `history_from` before comparing, and say when two histories differ.
- Report differences as they are. If two funds are close, say they are close; do not manufacture a winner.
- State `official_check`. `matches AMFI` is the normal case. "Mirror does not have AMFI's latest date yet" means the history is a day or two behind - fine for return analysis. A `MISMATCH` means do not rely on the figures.

Do not say a fund "will" return anything, and do not recommend buying, selling or switching. Past returns, including rolling returns, do not predict future returns; a fund's manager, size and strategy change.

## Limits

- NAV history comes from mfapi.in, a community mirror of AMFI data (secondary source), cross-checked against AMFI's latest NAV only.
- NAV-based returns already include the fund's expenses, but not exit loads or the investor's taxes.
- No benchmark or category-average comparison, no portfolio holdings, no risk-adjusted ratios beyond volatility and drawdown.
- India only.
