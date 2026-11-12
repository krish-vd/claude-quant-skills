---
name: dividend-screener
description: Rank Indian or US stocks by dividends - trailing 12-month yield, number of consecutive years paid, consecutive years of increases, and 3- and 5-year dividend growth - across an NSE index or a symbol list. Use when the user asks for high dividend yield stocks, consistent dividend payers, dividend growth stocks, the dividend history or yield of a company, or wants income candidates.
---

# Dividend Screener

```bash
python scripts/dividend_screen.py --market IN --index nifty200 --min-yield 3 --min-years-paid 5
python scripts/dividend_screen.py --market IN --index nifty500 --sort growth --min-growth 10
python scripts/dividend_screen.py --market US --symbols KO,PG,JNJ,XOM,T,VZ --sort streak
```

Filters: `--min-yield` (percent), `--min-years-paid` (consecutive complete years with a dividend), `--min-growth` (3-year dividend growth, percent a year). Sort by `yield`, `growth` or `streak`.

## Reading a row

- `yield_ttm_pct`: dividends paid in the last 12 months divided by the latest close.
- `dividends_ttm`, `payments_ttm`, `last_dividend`.
- `annual_totals`: dividends per share for up to six complete calendar years. **Always look at this.**
- `consecutive_years_paid`, `consecutive_years_of_increase`, `years_paid` out of `years_of_history`.
- `dividend_cagr_3y_pct`, `dividend_cagr_5y_pct`: growth in the annual total.

## Reading yield without being fooled

A high trailing yield has three common causes, and only one is good:

1. A steady, well-covered payout (what the user wants).
2. **A one-off special dividend** inflating the last 12 months. `annual_totals` shows it as one year far above the others. The yield will not repeat.
3. **A falling share price.** The dividend is unchanged but the market expects a cut. Check the stock's trend with `stock-screener`.

So never present the top of a yield-sorted list as the best income stocks. Show `annual_totals` beside the yield, call out any year that is out of line, and prefer consistency (`consecutive_years_paid`, steady growth) to the single highest number.

This screen has no earnings data, so it cannot check the payout ratio or whether the dividend is covered by profits or cash flow. Say that, and suggest the user check coverage before relying on a yield.

For Indian investors, dividends are taxed at slab rates in the holder's hands, so the after-tax yield is lower than shown and depends on their bracket.

## Limits

- Dividend amounts come from an unofficial source (Yahoo), adjusted for splits and bonuses, with up to ten years of history. Verify any figure that matters against the company's announcements.
- The current calendar year is excluded from annual totals and growth because it is incomplete.
- No payout ratio, earnings cover, ex-dividend dates ahead, or buybacks.
- A large index takes a few minutes on the first run.
- Candidates for research, not recommendations. Dividends are not guaranteed and can be cut.
