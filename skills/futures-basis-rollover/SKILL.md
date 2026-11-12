---
name: futures-basis-rollover
description: Analyse NSE futures against spot - the basis (premium or discount), annualised cost of carry, open interest across expiries, the near-to-next calendar spread and rollover percentage - for an index or stock, or a market-wide table of the highest and lowest rollovers and the deepest discounts and premiums. Use when the user asks about futures premium or discount, cost of carry, rollover data or rollover percentage, whether positions are being carried forward, calendar spreads, or cash-futures arbitrage.
---

# Futures Basis and Rollover

```bash
python scripts/basis_rollover.py --symbol NIFTY
python scripts/basis_rollover.py --symbol RELIANCE --date 2026-11-11
python scripts/basis_rollover.py --top 15 --min-oi-units 1000000      # market-wide table
```

## Reading the output (one symbol)

- `spot`: the underlying's close in the same file.
- `contracts`: for each expiry, `price`, `basis` (futures minus spot), `basis_pct`, `annualised_basis_pct`, `open_interest_units`, `oi_change_units`, `share_of_open_interest_pct`, `days_to_expiry`.
- `rollover_pct`: open interest in the later expiries as a share of all open interest.
- `near_to_next_spread`: next-month price minus near-month price, the cost of rolling a long.
- `previous_session`: yesterday's rollover and near-month basis, for the direction.

The market-wide table lists `highest_rollover`, `lowest_rollover`, `deepest_discount` and `highest_premium`.

## How to interpret

**Basis.** A future normally trades above spot by roughly the interest cost to expiry, less any dividend expected before expiry. So:
- A premium in line with interest rates is normal and says nothing.
- **A discount is very often just a dividend.** Before reading a discount as bearish, check whether the stock goes ex-dividend before expiry (`dividend-screener` shows recent dividends and their timing).
- For the index, a discount or a thin premium against the usual carry is sometimes read as cautious positioning. Present that as an interpretation.
- `annualised_basis_pct` blows up in the last few days before expiry because the days divisor is small; do not quote it then.

**Rollover.** It rises mechanically through expiry week as traders move to the next month, so today's figure only means something against the **same day of previous expiries**, which this script does not have. Compare with `previous_session` for direction, and say that a proper read needs the historical average for that day. High rollover shows positions being carried forward; it does not say whether they are long or short. Combine with `institutional-positioning` for who holds what.

**Arbitrage.** A basis wider than the carry cost is not free money: both legs have charges (`trade-cost-calculator`), margin is tied up, and stock futures settle by delivery. Do not present a gap as an arbitrage without those.

## Limits

NSE end-of-day settlement prices. No historical rollover averages, no intraday basis, no dividend adjustment of the fair value, no currency or commodity futures.
