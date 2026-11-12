---
name: option-payoff-builder
description: Work out the expiry payoff of any option position - single options, spreads, straddles, strangles, iron condors, butterflies, covered calls, protective puts, futures hedged with options - giving exact breakevens, maximum profit, maximum loss, reward-to-risk and P&L at chosen prices, net of costs. Use when the user describes an options strategy and asks what they can make or lose, where the breakevens are, whether the risk is capped, or wants two structures compared.
---

# Option Payoff Builder

Computes profit and loss at expiry for any combination of calls, puts and the underlying. Breakevens and extremes are exact (the payoff is piecewise linear between strikes), not read off a grid.

## Run it

Each leg is `SIDE:KIND:STRIKE:PRICE:QUANTITY`:

- `SIDE` buy or sell; `KIND` call, put or underlying (a future or shares)
- `PRICE` the premium per unit, or the entry price for the underlying (strike is ignored: use 0)
- `QUANTITY` units, which is lots x lot size (get the lot from `market-data`: `nse-lot NIFTY`)

```bash
# Bull call spread on NIFTY, 1 lot of 65
python scripts/option_payoff.py --leg buy:call:25000:200:65 --leg sell:call:25300:80:65

# Iron condor with total charges and a P&L table
python scripts/option_payoff.py \
  --leg buy:put:24500:20:65 --leg sell:put:24700:60:65 \
  --leg sell:call:25300:55:65 --leg buy:call:25500:15:65 \
  --costs 250 --at 24600,25000,25400

# Covered call: 100 shares at 500, sold 520 call at 10
python scripts/option_payoff.py --leg buy:underlying:0:500:100 --leg sell:call:520:10:100
```

For `--costs`, total the legs from `trade-cost-calculator` (segment `options`, price = premium). Costs matter most for cheap far-out-of-the-money legs.

## Reading the output

- `breakevens`: underlying prices at expiry where P&L is zero.
- `max_profit`, `max_loss`: `null` means unlimited; check `unlimited_profit` and `unlimited_loss`.
- `payoff_at_zero`: the result if the underlying went to zero - the real downside of positions with net short puts or long stock.
- `net_premium`: positive is a net credit received, negative a net debit paid.
- `reward_to_risk`: max profit divided by max loss, when both are finite.
- `warnings`: unlimited-loss and net-short-put positions are flagged. Always repeat these.

## How to present a position

State, in this order: what it costs or brings in now, the most it can lose and where, the most it can make and where, the breakevens, and then the conditions under which it loses. Lead with the loss side for any position with an uncapped or large loss. If the user asks which of two structures is better, compare them on the same underlying view and say what each gives up; do not pick for them without knowing their view and risk limit.

## Limits

- **Expiry only.** Before expiry the position's value also depends on time left and implied volatility. Use `option-pricer` on each leg for today's value and greeks.
- Margin is not computed. Short options and futures need margin far larger than the premium; point the user to their broker's margin calculator.
- European, cash-settled logic. Indian stock options are physically settled: an in-the-money position held to expiry means taking or giving delivery of shares, with delivery margin in the last week. Mention this for stock options.
- In India a bought option exercised in the money pays STT on intrinsic value; add it to `--costs` if the plan is to hold to expiry.
- All legs are assumed to share one expiry. Calendar and diagonal spreads are not supported.
