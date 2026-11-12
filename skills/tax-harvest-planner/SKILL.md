---
name: tax-harvest-planner
description: Plan year-end tax moves on listed Indian shares and equity funds - how much of the Rs 1.25 lakh long-term capital gains exemption is unused, exactly how many shares of which holding could be sold to use it, which positions carry losses that could be realised, and which short-term gains are about to become long-term. Use when the user asks about tax harvesting, tax-loss harvesting, booking LTCG before 31 March, using the 1.25 lakh exemption, whether to sell now or wait for long-term, or how to reduce capital gains tax.
---

# Tax Harvest Planner

```bash
python scripts/harvest.py --trades trades.csv                  # prices from the latest NSE close
python scripts/harvest.py --trades trades.csv --prices px.csv --fmv fmv.csv --date 2027-03-20
```

`trades.csv` is the standard trade CSV with the **full history** of every holding (build it with `tradebook-importer`). `--prices` (`symbol,price`) overrides the NSE close, and is needed for mutual fund units. `--fmv` gives 31 Jan 2018 values for shares bought before 1 Feb 2018.

## The three ideas

| Output | Idea | The trade-off |
|---|---|---|
| `gain_harvest` | Long-term gains up to the exemption are tax-free each year, and unused exemption does not carry forward. Selling shares with that much gain and buying back raises the cost base, so that gain is never taxed | Costs on two trades; the market can move between the sale and the repurchase; the holding period restarts |
| `loss_harvest_candidates` | Realising a loss creates a loss to set against gains (short-term losses against any capital gain, long-term losses against long-term gains only) | Only worth it if there are gains to offset or the loss is worth carrying forward; same costs and repurchase risk |
| `wait_for_long_term` | A short-term gain is taxed at 20%, long-term at 12.5%. If a lot turns long-term within the window, waiting saves the difference | The price can fall while waiting |

## FIFO is the constraint that surprises people

Shares leave a demat account **oldest first** within each stock. You cannot choose to sell the profitable lot or the long-term lot. So:

- `gain_harvest.sales` only uses long-term lots at the **front** of each stock's queue, and stops at whole units that fit the exemption.
- `sellable_now_as_long_term: false` on a long-term lot means older shares ahead of it would be sold first.
- A loss lot is a candidate only if nothing ahead of it blocks it.

Explain this when the plan looks smaller than the user expects.

## Presenting the plan

1. State the financial year, `realised_long_term_gain_so_far` and `ltcg_exemption_left`.
2. Give the gain-harvest sales as a short table (symbol, units, gain), the total, and `future_tax_avoided` - describe it as tax avoided later on that gain, not cash saved today.
3. List loss candidates with amounts and term, and say what they could offset. Do not net them off yourself: the script reports, the taxpayer chooses the set-off.
4. List anything in `wait_for_long_term` with its date.
5. Give the costs side: get round-trip charges from `trade-cost-calculator` and compare with the benefit. For small gains the charges can exceed the tax avoided - say so when it happens.
6. Repeat the `notes` and `warnings`.

This is arithmetic on the user's own holdings. Whether to act depends on things outside it: their other income and gains, whether they want to keep the position, and views on the price. Do not tell them to sell. For anything near the year end or with large amounts, recommend confirming with a chartered accountant - in particular how the tax department may view a sale and immediate repurchase done purely for tax purposes.

## Limits

- Listed equity (`listed_equity`) only; other asset classes are listed under `symbols_not_covered`.
- Uses realised gains from the trade file for this financial year only. Gains from other brokers, other asset classes, carried-forward losses and surcharge are not included: ask the user about them.
- Sales before 1 Apr 2025 are outside the tax rulebook's coverage.
- Prices are the last official close, not live.
