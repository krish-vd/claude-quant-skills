---
name: growth-leader-screener
description: Screen for growth leaders - stocks with strong year-on-year earnings and sales growth in the latest reported quarter (from company filings with NSE or the SEC), ideally accelerating, that are also price leaders (high relative strength, above their 150- and 200-day averages, near 52-week highs). Use when the user asks for growth stocks, earnings growth leaders, stocks with accelerating earnings, a fundamentals-plus-momentum screen, or the companies behind the strongest charts.
---

# Growth Leader Screener

```bash
python scripts/growth_screen.py --market IN --index nifty200
python scripts/growth_screen.py --market IN --index nifty500 --min-eps-growth 30 --min-rs 80
python scripts/growth_screen.py --market US --symbols NVDA,MSFT,AAPL,AMZN,META,AVGO,LLY,COST,NFLX
```

## Criteria (defaults, all adjustable)

| Test | Default |
|---|---|
| EPS growth, latest quarter vs same quarter last year | 25% or more |
| Revenue growth, same comparison | 15% or more |
| Relative-strength rank within the universe | 70 or more |
| Below the 52-week high | at most 25% |
| Above the 150- and 200-day averages | required |

Price tests run first, so filings are read only for price leaders. Each Indian company needs two to four filings (about 2 MB each, cached permanently), so a first run on a large index takes several minutes.

## Reading results

Each row: EPS and revenue growth, whether EPS growth is accelerating against the previous quarter, profit growth, RS rank, distance from the high, trend-template count. Sorted by EPS growth.

Put acceleration first, then check each name for traps:

- **Low base:** growth off a tiny or loss-making year-ago quarter looks huge. Check absolute numbers with `company-fundamentals`.
- **One-offs:** a gain on sale can inflate one quarter's profit. Profit growth far above revenue growth deserves a look.
- **Banks** (`bank_format`): revenue is interest income; compare them only with each other.

Follow-ups: `company-fundamentals`, `results-calendar`, `chart-reader`, `earnings-reaction`.

Candidates for research, not recommendations. No valuation is applied; fast growers often trade at high multiples.

## Limits

India: filings in the current format only (from the December 2024 quarter). US: SEC data with derived fourth quarters. Relative strength is within the universe screened.
