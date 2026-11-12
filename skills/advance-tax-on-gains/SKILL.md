---
name: advance-tax-on-gains
description: Work out the advance-tax instalments on capital gains realised during an Indian financial year - the cumulative amount due by 15 June, 15 September, 15 December and 15 March, taking account of when each gain arose - and the shortfall against what has been paid. Use when the user has sold shares or funds at a profit and asks whether they owe advance tax, how much to pay and by when, or how to avoid interest on a capital gain made late in the year.
---

# Advance Tax on Capital Gains

```bash
python scripts/advance_tax.py --trades trades.csv --fy 2026-27
python scripts/advance_tax.py --trades trades.csv --fy 2026-27 --paid 2026-06-15=5000 --paid 2026-09-15=12000
```

`trades.csv` is the standard trade CSV with full history (see `tradebook-importer`). `--fy` defaults to the current financial year. `--paid` records advance tax already paid on or before an instalment date.

## How the schedule works

Advance tax is paid in four cumulative instalments: 15% of the year's tax by 15 June, 45% by 15 September, 75% by 15 December, 100% by 15 March.

Capital gains cannot be estimated in advance, so there is relief: tax on a gain is not expected before the gain arises. The script therefore computes, for each due date, that date's percentage of the tax on gains **realised up to that date**. A gain made in October adds nothing to the June and September figures; 75% of its tax is due by 15 December and the rest by 15 March. Tax on gains made after 15 March is due by 31 March.

## Reading the output

- `special_rate_tax_for_the_year`: tax with cess on the 20% and 12.5% buckets.
- `advance_tax_applies`: false when that tax is under Rs 10,000 (but see below).
- `instalments`: for each due date, `tax_on_gains_realised_by_then`, `cumulative_amount_due`, `cumulative_paid`, `shortfall`.
- `next_due`: the next instalment from today.
- `tax_on_gains_after_15_march_due_by_31_march`.

Give the user the next due date and amount first, then the full table.

## This is only part of the picture - say so every time

Advance tax is assessed on **all income together**. This skill covers only capital gains taxed at the special rates. Not included:

- Gains taxed at slab rates (short-term foreign shares, debt funds): reported by `india-capital-gains` as `gains_taxed_at_slab_rates`.
- Salary, business and F&O income, interest, rent.
- TDS already deducted, which reduces what is due. A salaried person whose employer deducts tax may owe advance tax only on the gains.
- Surcharge for higher incomes.
- The Rs 10,000 test applies to total tax after TDS, not to capital gains alone, so `advance_tax_applies: false` here does not settle it.

So the figures are a floor for the capital-gains part. Ask the user what other income they have that is not covered by TDS.

Interest for late or short payment is not computed. If the user has missed an instalment, tell them interest runs monthly on the shortfall and that paying the balance promptly limits it, and suggest they confirm the amount with a tax professional.

## Limits

Resident individuals; transfers from 1 April 2025. Senior citizens without business income are exempt from advance tax, which the script does not check. The instalment percentages and the capital-gains relief were confirmed against secondary sources, not the statute text.
