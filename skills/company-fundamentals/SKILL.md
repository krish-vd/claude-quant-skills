---
name: company-fundamentals
description: Show a company's reported financials from regulatory filings - revenue, profit, EPS, margins, year-on-year growth, trailing four-quarter earnings and price-to-earnings - for NSE-listed Indian companies (quarterly results filed with the exchange) and US companies (SEC 10-K and 10-Q data, with return on equity, free cash flow and debt to equity), and compare companies side by side. Use when the user asks about a company's results, earnings growth, sales growth, margins, P/E, whether profits are rising, how the last quarter went, or wants the fundamentals behind a stock a screen turned up.
---

# Company Fundamentals

Figures come from what the company filed with the regulator: NSE integrated filings for India, the SEC for the US. No API key.

```bash
python scripts/fundamentals.py --market IN --symbol INFY
python scripts/fundamentals.py --market IN --symbol TCS --symbol INFY --symbol HCLTECH     # compare
python scripts/fundamentals.py --market IN --symbol RELIANCE --standalone
python scripts/fundamentals.py --market US --symbol AAPL --symbol MSFT
```

The first run for an Indian company downloads one filing per quarter (about 2 MB each) and takes a little while; they are then cached permanently.

## What you get

**India** (rupees, consolidated unless `--standalone`): for each of the last quarters, `revenue`, `net_profit`, `eps_diluted`, `net_margin_pct`, `pbt_margin_pct` and growth against the same quarter a year earlier; `trailing_four_quarters` with summed EPS and `price_to_earnings` on the latest official NSE close; and the latest `balance_sheet` equity and assets where the filing includes them.

**US** (dollars): for each of the last fiscal years, revenue, net income, diluted EPS, growth, net margin, `return_on_equity_pct`, `free_cash_flow` (operating cash flow less capital expenditure) and `debt_to_equity`; 3-year revenue and EPS growth rates; the last eight quarters with year-on-year growth; and trailing EPS with price-to-earnings.

## Reading it properly

- **Compare a quarter with the same quarter last year**, not the previous quarter: most businesses are seasonal. That is what the growth columns do.
- **Growth is blank when the year-ago figure was zero or a loss.** Say "moved from a loss to a profit" instead of quoting a percentage.
- **One quarter is not a trend.** Look down the column: is growth speeding up, steady or slowing? That direction is usually more informative than the latest number.
- **Check profit against revenue.** Profit growing much faster than sales for long usually means margin expansion or one-off items; check which.
- **Price-to-earnings** here is price over the last four quarters' reported diluted EPS. It includes one-off gains and losses, and by itself says nothing about whether a stock is cheap. Compare with the company's own growth and with peers run in the same command.
- **Banks and lenders** (`bank_format: true`): "revenue" is interest earned, and margins are not comparable with other companies. Compare banks only with banks.
- **US fourth quarters are derived** (the year minus three filed quarters) and flagged. Fiscal years differ between companies, so line up periods before comparing.
- For Indian consolidated results, net profit is the group figure as filed; EPS reflects the shareholders' portion.

State the period and the basis (consolidated or standalone) whenever quoting a number.

## Using it with the other skills

After `stock-screener` finds strong charts, run the candidates here to see whether earnings support the price move. Use `results-calendar` to see when the next results are due before entering a trade.

Do not turn the figures into a rating or a recommendation, and do not forecast next quarter. This is reported history.

## Limits

- India: only results filed in the current format (from the quarter ending December 2024 onward), so about two years of history. No cash flow or detailed balance sheet, no segment data, no shareholding.
- US: companies that file 10-K and 10-Q. Foreign companies filing other forms, and some that use unusual accounting tags, will be missing figures; `tags_used` shows what was found.
- Restatements: the latest filed value is used.
- No analyst estimates, guidance or earnings surprises.
