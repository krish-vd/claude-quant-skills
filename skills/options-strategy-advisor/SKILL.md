---
name: options-strategy-advisor
description: Lay out the standard option structures for a stated view - bullish, bearish, neutral or volatile - on one expiry and compare them on cost, maximum profit and loss, breakevens, reward to risk, probability of profit at the implied volatility, and position delta, theta and vega. Uses actual NSE settlement prices and implied volatility when given a symbol (NIFTY, BANKNIFTY, F&O stocks), or model prices from a forward and volatility. Use when the user has a view and asks which options strategy fits, how a spread compares with buying an option, whether to sell premium, or how an iron condor or straddle would look on the current chain.
---

# Options Strategy Advisor

```bash
python scripts/strategy_compare.py --view bullish --symbol NIFTY
python scripts/strategy_compare.py --view neutral --symbol BANKNIFTY --expiry 2026-11-25
python scripts/strategy_compare.py --view volatile --forward 230 --iv 0.35 --days 30 --strike-step 2.5 --quantity 100
```

## Structures per view

| View | Compared |
|---|---|
| bullish | long call, bull call spread, bull put spread, short put |
| bearish | long put, bear put spread, bear call spread, short call |
| neutral | iron condor, iron butterfly, short strangle |
| volatile | long straddle, long strangle |

Strikes sit at the money and at half, one and one-and-a-half expected moves (forward x IV x sqrt(days/365)), rounded to the strike grid.

## Reading the comparison

Each structure gives its legs and premiums (`pricing`: `market` = official settlement prices of strikes that traded, `model` = Black-76 at the at-the-money IV), net premium, maximum profit and loss, breakevens, reward to risk, probability of profit, and position delta, theta per day and vega per volatility point.

Help the user see the trade-offs:

- **Probability and payoff move against each other.** Short premium wins more often and loses much more when it loses; long options lose more often and are capped at the premium.
- **Volatility.** Positive vega gains if implied volatility rises, negative vega if it falls. Ask what they expect for volatility, not only direction.
- **Time.** Theta per day is the cost or income of waiting.
- **Unlimited-loss structures** (short call, short strangle): flag first; they need an exit plan and margin.

Then let the user choose. Do not pick a structure or say which will make money. For one they like, offer `option-payoff-builder` (P&L at chosen prices, with costs) and `trade-cost-calculator`.

## Limits

Single expiry, European pricing, no skew in model prices (out-of-the-money puts usually cost more than the model shows). Probability of profit is risk-neutral at expiry, not a forecast. Margin and costs not included. End-of-day chain.
