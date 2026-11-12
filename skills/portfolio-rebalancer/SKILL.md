---
name: portfolio-rebalancer
description: Calculate the buys and sells that bring a portfolio back to its target asset allocation - showing each asset's drift from target - with options to rebalance using only new money so nothing is sold, to ignore small drifts inside a tolerance band, and to handle a withdrawal. Use when the user asks how to rebalance, whether their allocation has drifted, where to put new money or this month's SIP to stay on target, or how to move to a new equity/debt/gold split.
---

# Portfolio Rebalancer

```bash
# Full rebalance to 60/30/10
python scripts/rebalance.py --holding equity=1420000 --holding debt=480000 --holding gold=100000 \
  --target equity=60 --target debt=30 --target gold=10

# Put 1 lakh of new money where it is most needed; sell nothing
python scripts/rebalance.py --holding equity=700000 --holding debt=300000 \
  --target equity=60 --target debt=40 --new-money 100000 --no-sell

# Only act on assets more than 5 points off target
python scripts/rebalance.py --holding equity=630000 --holding debt=370000 \
  --target equity=60 --target debt=40 --band 5
```

Holdings are current values; targets are percentages adding to 100. Names can be asset classes or individual funds. `--new-money` may be negative for a withdrawal.

## Reading the output

Per asset: `current_pct`, `target_pct`, `drift_pct_points`, the `trade` in currency (positive buy, negative sell), and `pct_after`. Totals: `total_bought`, `total_sold`, `largest_drift_pct_points`.

## Choosing the method - raise this with the user

Selling to rebalance usually triggers capital gains tax, and in funds sometimes an exit load. So the order of preference is:

1. **New money only (`--no-sell`).** If the user is investing regularly, directing contributions to the underweight assets fixes drift at no tax cost. It may not close the whole gap in one go; `pct_after` shows how far it gets.
2. **A band (`--band`).** Small drifts are not worth trading. A common convention is to act only beyond about 5 percentage points. Present that as a convention, not a rule.
3. **Full rebalance with sales** when drift is large or no new money is coming. Estimate the tax first: `india-capital-gains` for the gain on what would be sold, and `tax-harvest-planner` to see how much long-term gain the yearly exemption still covers.

Mention the tax and exit-load point whenever the plan includes a sale.

## What not to do

- **Do not choose the target allocation.** That depends on the user's goals, horizon and tolerance for loss, and this tool does not know them. If they have no target, say that it is their decision (or their adviser's) and show how the arithmetic works for an allocation they name.
- Do not describe rebalancing as improving returns. It controls risk by keeping the mix where the investor chose; whether it adds return depends on the period.

## Limits

Trades are in currency value: convert to units at the current price or NAV and round to tradable quantities. No tax, cost or exit-load calculation here. One level only: it does not look inside funds, so two "equity" funds holding the same stocks count as separate assets.
