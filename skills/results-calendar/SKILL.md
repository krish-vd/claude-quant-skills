---
name: results-calendar
description: List upcoming quarterly results dates for NSE-listed companies (board meetings notified to the exchange) and upcoming ex-dates for dividends, bonuses and splits - for the whole market, an index, a watchlist, or the positions open in the trade journal. Use when the user asks when a company's results are, which results are due this week, whether any of their holdings report soon, what the earnings calendar looks like, or about upcoming dividends and ex-dates.
---

# Results Calendar

```bash
python scripts/results_calendar.py --days 7 --index nifty200
python scripts/results_calendar.py --symbols INFY,TCS,RELIANCE --days 30
python scripts/results_calendar.py --open-trades          # only stocks you currently hold, from the trade journal
python scripts/results_calendar.py --days 3 --all-purposes
```

Data is NSE's own event calendar and corporate-actions list. Without a filter it covers every NSE company, which in results season is hundreds of names a week: use `--index`, `--symbols` or `--open-trades`.

## Output

- `results_by_day`: date, then the companies whose board meets that day to approve results.
- `upcoming_ex_dates`: dividends (with the amount per share where stated), bonuses and splits (with the ratio), rights, demergers and buybacks.

## Why it matters to a trader

- **Results are the single largest scheduled risk for a position.** A stock can gap well beyond any stop on the next open. Before a new swing trade, check whether results fall inside the expected holding period; with `--open-trades`, check existing positions each week.
- **Timing:** results are usually released the day of the board meeting, often after the market closes, so the reaction is typically the next session. Say "on or after" the date, not that the move will happen that day.
- **Ex-dates:** the share price normally drops by about the dividend on the ex-date; that is not a loss of value. A bonus or split changes the share count and price together. Stock futures and options are adjusted by the exchange for bonuses, splits and large dividends.
- A stock future trading at a discount to spot before an ex-dividend date is usually just the dividend (see `futures-basis-rollover`).

When listing results for the user's holdings or watchlist, give the date and the number of trading days away. Do not predict whether results will be good or how the stock will react. To look at the company's recent numbers, use `company-fundamentals`.

## Limits

- India only. There is no free, reliable source of future US earnings dates, so US companies are not covered.
- A date appears only once the company has notified the exchange, often one to two weeks ahead; companies can also reschedule. An empty result does not mean no results are coming.
- Board-meeting dates, not announcement times. No estimates or consensus figures.
- If NSE blocks the request the script says so; do not fill in dates from memory.
