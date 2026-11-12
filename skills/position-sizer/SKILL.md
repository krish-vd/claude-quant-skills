---
name: position-sizer
description: Calculate how many shares, futures lots or option lots to trade so that a stop-out loses a fixed percent of the account. Covers Indian and US stocks, NSE index and stock futures and options (lot sizes read live from NSE), MCX commodities (gold, silver, crude, natural gas, copper) and US futures (ES, NQ, GC, SI, CL, NG and micros). Use when the user asks how many shares or lots to buy, how much to risk, what position size fits their stop-loss, or whether an F&O lot is too big for their account.
---

# Position Sizer

Sizes a position from risk: `size = (account x risk %) / (distance from entry to stop)`, always rounded down. Run the script; do not do this arithmetic by hand.

## Run it

```bash
# Stock, long: Rs 10 lakh account, risk 1%, buy 500, stop 480, cap the position at 20% of account
python scripts/position_sizer.py --instrument cash --account 1000000 --risk-pct 1 \
  --entry 500 --stop 480 --max-position-pct 20

# Nifty futures: the lot size is fetched live from NSE
python scripts/position_sizer.py --instrument futures --account 1000000 \
  --entry 25000 --stop 24900 --symbol NIFTY --margin-per-contract 250000

# MCX gold mini, or US micro gold: the multiplier comes from the contract table
python scripts/position_sizer.py --instrument futures --account 500000 --entry 125000 --stop 124200 --symbol GOLDM
python scripts/position_sizer.py --instrument futures --account 50000 --risk-pct 2 --entry 3978 --stop 3950 --symbol MGC

# Buying an option: premium 120, planning to exit if it falls to 60
python scripts/position_sizer.py --instrument option --account 1000000 \
  --premium 120 --stop-premium 60 --symbol NIFTY
```

A stop above entry is treated as a short. US fractional shares: add `--fractional-step 0.0001`.

## What to collect first

1. Account size, in the same currency as the instrument (INR for NSE/MCX, USD for US).
2. Risk per trade. If the user has no number, use 1% and say so. Do not suggest more than 2% without the user asking.
3. Entry and stop. If the user has no stop, do not invent one: sizing without a stop is meaningless. Ask where the trade idea is wrong.
4. For futures: the margin per lot from the broker's margin calculator. Without it the script cannot check affordability and says so.

To include costs, get the round-trip cost per unit from the `trade-cost-calculator` skill and pass `--cost-per-unit`.

## Reading the output

- `units`: shares, or lots/contracts. `quantity`: underlying units (lots x lot size).
- `binding_constraint`: `risk`, `max_position_pct`, `margin` or `account_cash` - tell the user which limit set the size.
- `units` of 0 means one share or lot already risks more than the budget. Say that plainly and offer the real options: a smaller contract (mini or micro), a tighter stop, or no trade. Never round up to 1.
- `contract.source_kind`: NSE lots are `primary` (live exchange file). MCX and US futures multipliers come from a table marked `secondary` or `unverified`: tell the user to confirm against the exchange contract page, or pass `--multiplier` themselves.

## Limits

- Option **selling** is not sized here: its loss is not capped by the premium.
- A stop does not guarantee the exit price. Gaps, circuit limits and illiquid options can lose more than the planned amount; mention this for overnight positions.
- The script sizes one position. It does not know about other open positions or correlated risk.
- This calculates size from the user's own plan. It does not recommend the trade.
