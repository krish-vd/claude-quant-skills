---
name: option-pricer
description: Price a European option and compute delta, gamma, theta, vega and rho, or solve for implied volatility from a market premium, using Black-76 (index options and options on futures - NIFTY, BANKNIFTY, MCX, CME) or Black-Scholes (spot with dividend yield). Use when the user asks for option greeks, implied volatility, whether an option is cheap or expensive, how much premium decays per day, how an option will move if the underlying or volatility changes, or the delta of a position.
---

# Option Pricer

Run the script for every pricing or greeks question. Do not approximate greeks from rules of thumb.

## Run it

```bash
# Implied volatility and greeks from a market premium: NIFTY 25000 call, 14 days out,
# futures at 25050, premium 210, position of 1 lot (65 units)
python scripts/option_pricer.py --kind call --underlying 25050 --strike 25000 \
  --days 14 --rate 0.065 --price 210 --quantity 65

# Theoretical price and greeks at a volatility you choose
python scripts/option_pricer.py --kind put --underlying 25050 --strike 24800 \
  --expiry 2026-11-26 --rate 0.065 --vol 0.13

# Spot model with a dividend yield
python scripts/option_pricer.py --kind call --model black_scholes --underlying 100 \
  --strike 105 --days 30 --rate 0.05 --dividend-yield 0.01 --vol 0.25
```

Give exactly one of `--vol` (get a price) or `--price` (get implied volatility), and one of `--days` or `--expiry`.

## Choosing the model and the underlying price

| Option | Model | `--underlying` is |
|---|---|---|
| NIFTY, BANKNIFTY and other index options | `black_76` (default) | The **futures** price of the same expiry, not the spot index |
| NSE stock options | `black_76` | The stock future of the same expiry |
| MCX and CME options on futures | `black_76` | The futures price |
| A quick spot-based estimate | `black_scholes` | Spot, with `--dividend-yield` |

Using the spot index in `black_76` is the most common error: it shifts implied volatility for every strike. If there is no future for that expiry (weekly index options beyond the monthly futures), approximate the forward as spot x (1 + rate x days/365) and say you did.

`--rate`: the risk-free rate as a decimal. Ask the user or look up the current 91-day T-bill yield (India) or 3-month T-bill (US). Do not assume a remembered value; for options under a month it barely matters, and the output notes when it was left at 0.

`--quantity`: units held, lots x lot size (get the lot from the `market-data` skill). Use a negative number for a sold option so the position greeks have the right sign.

## Reading the output

- `greeks_per_unit` are for one unit of the underlying. `greeks_for_position` are scaled by quantity: position delta is the equivalent number of underlying units; `theta_per_day` is the rupee or dollar decay per calendar day; `vega_per_vol_point` is the change for a one-point move in implied volatility.
- `time_value` is premium minus intrinsic value: what the buyer loses if the underlying does not move.
- If no implied volatility exists, the premium is inconsistent with the inputs. Check for a stale quote, the wrong underlying price, or spot used in place of the future.

## Limits

- European exercise. Correct for NSE index and stock options. US single-stock options are American: puts and calls on dividend payers are worth more than this shows.
- One volatility for all strikes; real markets have a skew, so do not use one option's implied volatility to price a distant strike.
- "Cheap" or "expensive" needs a comparison (the same option's history, or realised volatility). A single implied volatility number does not say either; do not claim it does.
- Greeks are local. For large moves, re-run at the new price instead of extrapolating delta.
