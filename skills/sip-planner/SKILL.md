---
name: sip-planner
description: Plan a SIP or a savings goal - project what a monthly SIP grows to, or work out the monthly SIP needed to reach a target, with a yearly step-up, a starting lumpsum, an inflation adjustment and a comparison across return assumptions. Use when the user asks how much their SIP will be worth, how much to invest each month to reach an amount (retirement, a house, education), what a 10% step-up does, or how a goal looks in today's money.
---

# SIP Planner

Exact SIP arithmetic. Run the script; do not estimate compound growth by hand.

```bash
# What will 25,000 a month become in 20 years at 11%, stepping up 10% a year?
python scripts/sip_planner.py --monthly 25000 --years 20 --return-pct 11 --step-up-pct 10 --inflation-pct 6

# What SIP reaches 1 crore in 15 years, starting with 2 lakh already invested?
python scripts/sip_planner.py --target 10000000 --years 15 --return-pct 11 --step-up-pct 10 \
  --lumpsum 200000 --scenarios 8,10,12
```

Give exactly one of `--monthly` or `--target`.

## The return assumption is the user's, and it is the whole answer

`--return-pct` drives everything, and nobody knows it in advance. So:

- **Ask the user what they want to assume**, or offer a range. Do not pick one number and present its result as what they will get.
- **Always run `--scenarios`** with a lower, middle and higher return, and show the spread. For an equity fund something like 8, 10, 12 is a reasonable set to illustrate; for debt, lower. Present these as illustrations, not forecasts.
- Say clearly that real returns arrive unevenly: a constant 11% is a planning device. A market fall near the goal date can leave the corpus well short. For goals within about five years, say that a high equity return assumption is risky.

## Reading the output

- `future_value`, `total_invested`, `gain`, and a `yearly` table.
- `required.required_monthly_sip` when solving for a target: this is the instalment in year one; with a step-up it rises each year (see the `yearly` table).
- `future_value_in_todays_money` when `--inflation-pct` is given. Lead with this for long goals: 1 crore in 20 years buys far less than 1 crore today.
- `convention`: by default the monthly rate is the annual return divided by 12 with the instalment at the start of the month, which matches most fund-house calculators. `--effective` treats the return as a true annual rate and gives slightly lower figures. Mention the convention if the user compares with another calculator.

## Limits

- Taxes on gains are not deducted (equity gains above the yearly exemption are taxed at redemption). For the tax on an actual redemption, use `india-capital-gains`.
- No modelling of variable returns, sequence risk or changing allocation over time.
- To see what a SIP in a specific fund actually earned in the past, use `mf-returns`. Past fund returns are not a basis for the assumption here beyond a sanity check.
- This is arithmetic for the user's own plan, not a recommendation of a product, an amount or an asset allocation.
