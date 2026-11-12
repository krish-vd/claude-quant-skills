---
name: pre-trade-checklist
description: Run a planned trade through a rule gate before the order is placed - is there a stop on the right side, is the risk within the per-trade limit, is the position too large, does reward justify risk, is the loss circuit breaker clear, is there room under the open-risk cap, is this adding to an existing position. Returns approved or blocked with the reason for each rule. Use when the user says they are about to buy, sell or enter a trade, asks whether a trade is okay to take, wants a sanity check on a setup, or asks for a pre-trade checklist.
---

# Pre-Trade Checklist

The last step before an order. It checks the plan against the trader's own rules; it does not judge the idea.

```bash
# Shares
python scripts/pretrade.py --account 1000000 --symbol WIPRO --direction long \
  --entry 500 --stop 480 --target 550 --quantity 200

# Futures: quantity in lots, lot size in --multiplier, and --leveraged
python scripts/pretrade.py --account 1000000 --symbol NIFTY --direction long \
  --entry 25000 --stop 24900 --target 25300 --quantity 1 --multiplier 65 --leveraged
```

Limits (override any of them with the user's own): `--max-risk-pct` 1, `--min-reward-to-risk` 2, `--max-position-pct` 20, and the circuit-breaker limits `--daily-loss-pct` 2, `--weekly-loss-pct` 4, `--monthly-loss-pct` 8, `--max-consecutive-losses` 3, `--max-open-risk-pct` 6. It reads the trade journal for losses and open risk.

## The rules

| Rule | Fails when |
|---|---|
| `stop_defined` | No stop, or the stop is on the wrong side of entry |
| `risk_per_trade` | Planned loss at the stop exceeds the per-trade limit |
| `position_size` | Position value exceeds the cap (warning only with `--leveraged`: check margin instead) |
| `reward_to_risk` | Distance to target divided by distance to stop is below the minimum (warning if no target) |
| `circuit_breaker` | A daily, weekly or monthly loss limit, or the losing-streak limit, is breached |
| `open_risk_room` | This trade's risk does not fit under the cap on total open risk |
| `not_already_open` | Warning: the symbol already has an open trade in the journal |

## How to respond

- **Approved:** say so in a sentence, give the planned risk in money and as a percent of the account, and mention any warnings. Then offer to record it with `trade-journal` once the order is filled.
- **Blocked:** lead with the failed rules and their numbers. Then give the adjustment that would pass, computed, not vague: for too much risk, the quantity that fits (use `position-sizer`); for poor reward to risk, the target or entry needed; for a breached circuit breaker, there is no adjustment - the answer is not today.
- Do not help the user get around a failed rule by loosening a limit in the moment. If they say their limits are different, use the limits they state as standing rules, and say which limits were applied. If they want to change a rule right after it blocked a trade, note once that rules are better changed when no trade is pending, then do as they ask - it is their account.
- A missing stop is the most important failure. Do not supply one. Ask where the trade idea would be proven wrong.

Keep it short. The user is about to place an order; give the verdict first.

## Limits

- It checks process and risk only. A plan that passes every rule can still be a poor trade.
- It knows only journalled trades. Positions and losses not in the journal are invisible to it.
- Correlated positions are not detected: five bank stocks count as five independent risks.
- Costs are not included in the risk figure; add them with `trade-cost-calculator` for small or frequent trades.
