---
name: earnings-reaction
description: Study how a stock reacts to its quarterly results - for every past announcement, the opening gap, the day's move against the index and the drift over the next 5 and 20 sessions - and scan an index for companies that just reported and how the market took the numbers (post-earnings drift and earnings-gap candidates). NSE stocks from exchange filing times, US stocks from SEC 8-K filing times. Use when the user asks how a stock usually moves on results, about post-earnings drift, earnings gaps, which stocks reacted best or worst to recent results, or whether to hold through results.
---

# Earnings Reaction

```bash
python scripts/earnings_reaction.py --symbol INFY                     # India, full history
python scripts/earnings_reaction.py --market US --symbol AAPL
python scripts/earnings_reaction.py --recent-index nifty100 --days 7 --with-growth
```

## Reaction day

Results published during market hours move that day; after the close (15:30 IST, 16:00 New York) they move the next session. India uses NSE broadcast times from the company's filings; the US uses the SEC acceptance time of the 8-K with item 2.02 (results of operations). Both are primary records.

## Output

**One stock:** a summary (events, average absolute move and gap, up and down reactions, average 20-day drift against the index after each, the largest move) and every event with announcement time, reaction date, gap, day move, move against the index, volume against its 20-day average, and 5- and 20-day drift.

**Recent scan:** index companies that reported within `--days`, sorted by reaction against the index, optionally with revenue and profit growth.

## Using it

- **Before holding through results:** the average absolute move is the risk to expect. A stock that typically moves 5% on results can gap far past a 3% stop; compare with stop distance and size.
- **Post-earnings drift:** a strong reaction on heavy volume with strong growth, followed by continued outperformance, is what drift traders look for. The 20-day columns show whether this stock has tended to continue or reverse. Present it as this stock's history.
- **The recent scan** is a candidate list. Follow with `company-fundamentals` and `chart-reader`.

A dozen events is a small sample; never present an average as what will happen next time.

## Limits

India: history from NSE's filing lists, older records may be missing. US: depends on 8-K item tagging. Unofficial prices; drift ignores dividends and costs.
