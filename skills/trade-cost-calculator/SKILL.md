---
name: trade-cost-calculator
description: Calculate the exact charges on a trade in India (NSE equity delivery, intraday, ETFs, futures, options; BSE cash; MCX commodity futures and options) or on US stocks - STT/CTT, exchange transaction charges, SEBI fee, stamp duty, GST, DP charges, SEC fee, FINRA TAF - plus net P&L and breakeven for a round trip. Use when the user asks what a trade costs, what their charges or breakeven are, why a contract note shows a certain STT, or how the April 2026 STT hike affects an F&O trade.
---

# Trade Cost Calculator

Computes every statutory and exchange levy on a trade from a dated, cited rulebook. Never work these out by hand or from memory: rates changed on 1 Oct 2024, 1 Mar 2026 and 1 Apr 2026, and the script picks the rate in force on the trade date.

## Run it

```bash
# India, round trip (buy and sell), delivery
python scripts/trade_cost.py --market IN --segment equity_delivery \
  --buy-price 1000 --sell-price 1010 --quantity 100 --date 2026-11-12 --dp-charge 15.34

# India, one leg: selling 10 lots of a Nifty option (lot 65) at a premium of 100
python scripts/trade_cost.py --market IN --segment options --side sell \
  --price 100 --quantity 650 --brokerage-flat 20

# MCX: 1 lot of GOLD (multiplier 100) bought at 125000 per 10 g
python scripts/trade_cost.py --market IN --segment commodity_futures --side buy \
  --price 125000 --quantity 100

# US stock round trip
python scripts/trade_cost.py --market US --buy-price 200 --sell-price 210 --quantity 100
```

Segments: `equity_delivery`, `equity_intraday`, `etf_delivery`, `futures`, `options`, `commodity_futures`, `commodity_options`.

## Inputs to get right

- **Quantity is units, not lots.** For NSE derivatives it is lots x lot size (get the lot from the `market-data` skill: `nse-lot SYMBOL`). For MCX it is lots x the contract multiplier (`contract SYMBOL`).
- **Price for options is the premium**, not the strike.
- **Brokerage is the user's own plan.** Ask if unknown; do not assume a broker. "Rs 20 or 0.03%, whichever is lower" is `--brokerage-pct 0.0003 --brokerage-cap 20`.
- **DP charge** applies only to delivery sells and varies by broker. Pass the GST-inclusive amount.
- **Date matters.** It defaults to today. Use the actual trade date when checking a contract note.

## Reading the output

Each line has the levy, amount, rate and `source_kind`:

- `primary`: read from the exchange or regulator's own document.
- `secondary`: cross-checked against a broker's published charges only (MCX fees, stamp duty, SEBI fee, BSE).
- `unconfirmed`: a filed but unconfirmed change (currently the FINRA TAF pause for Oct-Dec 2026).

Always pass the `warnings` on to the user in plain words. Amounts are exact; a real contract note rounds STT to the nearest rupee and other levies to paise, so differences of about a rupee per levy are expected.

## Limits - say so, do not improvise

- Trade dates before 1 Oct 2024 (India) are refused. Do not estimate older trades from current rates.
- BSE is supported for cash equity only. BSE derivatives, currency derivatives, US options and US futures fees are not in the rulebook.
- STT on an exercised (in-the-money at expiry) bought option is a separate charge on intrinsic value: mention it when a user holds options to expiry.
- This is a cost calculation, not advice on whether to take the trade.
