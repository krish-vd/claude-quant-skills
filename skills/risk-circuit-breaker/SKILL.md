---
name: risk-circuit-breaker
description: Check whether new trading risk is allowed today, using loss limits the trader set in advance - daily, weekly and monthly loss limits, a pause after consecutive losses, and a cap on total open risk - read from the trade journal. Use before any new entry, when the user asks if they should keep trading after losses, mentions revenge trading or a losing streak, asks how much risk they have open, or wants a pre-trade risk check.
---

# Risk Circuit Breaker

A circuit breaker stops a bad day from becoming a bad month. The limits are decided when calm and applied mechanically.

```bash
python scripts/circuit_breaker.py --account 1000000
python scripts/circuit_breaker.py --account 1000000 --daily-loss-pct 1.5 --weekly-loss-pct 3 \
  --monthly-loss-pct 6 --max-consecutive-losses 3 --max-open-risk-pct 5
```

| Check | Breached when | Default |
|---|---|---|
| `daily_loss` | Realised loss today reaches the limit | 2% of account |
| `weekly_loss` | Realised loss since Monday reaches the limit | 4% |
| `monthly_loss` | Realised loss this calendar month reaches the limit | 8% |
| `consecutive_losses` | The most recent closed trades are all losses, this many in a row | 3 |
| `open_risk` | Sum of planned risk on open trades reaches the limit | 6% |

The defaults are common conventions, not rules. If the user has their own limits, use those every time; if they have none, use the defaults and say they are defaults.

## Giving the answer

- `new_risk_allowed: false` - say so in the first sentence, name the breached check and the numbers ("down 21,500 today against a 20,000 limit"). The answer to "can I take one more trade?" is then no, until the period resets. Do not help find a way around it (a smaller size, a "sure thing", a different account). If the user wants different limits, that is a decision for a calm moment, not mid-drawdown; say that once, plainly.
- `new_risk_allowed: true` - give the headroom: `used_pct_of_limit` on each loss check and `room_for_new_risk` on open risk. If a check is above about 75% used, mention it. A new trade's planned risk should fit inside `room_for_new_risk`.
- Always report `open_trades_without_a_stop`. Those positions carry risk the breaker cannot count.
- After a breach, the useful suggestions are: stop for the period, review the losing trades with `trade-review`, and check whether the plan was followed.

Be direct and brief. Someone asking this after losses needs a clear answer, not reassurance and not a lecture.

## Limits

- It sees only what is in the journal. Trades not recorded, and unrealised losses on open positions, are not counted. If the user mentions losses that are not journalled, say the check understates the damage.
- It is a check, not an enforcement mechanism: it cannot stop an order.
- The weekly window starts on Monday; the monthly window on the 1st.
