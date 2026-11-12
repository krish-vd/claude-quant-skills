---
name: institutional-positioning
description: Show how FIIs, DIIs, proprietary desks and retail clients are positioned in Indian equity derivatives (index and stock futures, index and stock options) from NSE's official participant-wise open interest, with day-on-day changes and the FII index-futures long/short ratio history, plus the latest FII/DII cash-market buying and selling. Use when the user asks what FIIs or DIIs are doing, about FII long-short ratio, FII/DII data or flows, institutional activity, participant-wise OI, or whether foreign investors are net long or short.
---

# Institutional Positioning

```bash
python scripts/positioning.py                         # latest published day, 10 days of history
python scripts/positioning.py --date 2026-11-11 --history-days 20
python scripts/positioning.py --no-cash               # derivatives only
```

Both data sets are NSE's own. Derivative positions come from the exchange archive and are available for past dates. Cash-market flows are published for the latest day only, so each run adds that day to a local log; the cash history is as long as the number of days the skill has been run.

## Reading the output

- `positions[participant][group]`: `long`, `short`, `net` (contracts) and `long_pct` for Client, DII, FII and Pro, across `index_futures`, `stock_futures`, `index_calls`, `index_puts`, `stock_calls`, `stock_puts`.
- **`FII.index_futures.long_pct`** is the widely quoted "FII long-short ratio": longs as a percent of FII longs plus shorts in index futures. `fii_index_futures_history` shows its path, with the client figure beside it.
- `change_in_net_since_previous_session`: how each group's net position moved in one session.
- `cash_market_rs_crore`: FII and DII buy, sell and net values for the latest day, in Rs crore.

## Interpreting it without overreaching

- **A net short is not a forecast of a fall.** FIIs hold large cash portfolios and short index futures to hedge them. DIIs' large stock-futures short is mostly arbitrage and hedging against holdings. Say what the position is, then note the hedging caveat.
- **Options columns need care.** "Index call long" and "index call short" are both in the file; a net figure hides whether a group is running spreads. Do not label a group bullish or bearish from net option contracts alone.
- **Changes matter more than levels.** A long ratio rising from 21% to 31% over four sessions (short covering) is more informative than either number. Describe the direction and pace.
- **Extremes persist.** A low FII long ratio has at times stayed low for weeks while the market rose. Present extremes as context, not as a contrarian signal, unless the user asks how others read it - then attribute it as a common interpretation.
- Every long has a matching short, so the four groups sum to zero in each column pair (NSE's file is occasionally off by a contract through rounding).

Always state `as_of`: these are end-of-day figures published in the evening.

## Limits

India only. Contracts, not rupee value: index and stock contracts differ greatly in notional size, so do not add them across groups. No FII sector-wise or stock-wise data, no provisional versus final revisions of cash figures. If NSE blocks the cash-flow request, the script returns the derivative data with an error for the cash part; report that plainly.
