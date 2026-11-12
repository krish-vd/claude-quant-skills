---
name: fno-business-income
description: Summarise a year of Indian futures and options trading for the income-tax return - net profit or loss after charges, and F&O turnover for the tax-audit test computed under both readings in current use - with the audit thresholds. Use when the user asks how F&O is taxed, what their F&O turnover is, whether they need a tax audit, how to report F&O losses, or which ITR form F&O traders file.
---

# F&O Business Income

```bash
python scripts/fno_income.py --trades fno_trades.csv
```

`fno_trades.csv`, one row per **closed** trade in the financial year:

```csv
kind,pnl,charges,sale_value
future,50000,1200,
future,-30000,900,
option,20000,400,150000
option,-45000,500,60000
```

- `kind`: `future` or `option`.
- `pnl`: sell value minus buy value for that trade, before charges.
- `charges`: brokerage, exchange charges, STT, stamp duty, GST for that trade.
- `sale_value` (options): premium x quantity on the sell leg.

Most brokers' tax P&L reports give these per trade. Build the file from that report, and reconcile the totals with it.

## The settled part

- F&O profit or loss is **non-speculative business income**, not capital gains. It is added to other income and taxed at slab rates.
- It is reported in ITR-3 (or ITR-4 if the presumptive scheme is chosen).
- Expenses incurred for trading (the `charges`, and reasonable costs such as data, internet and advisory fees) can be deducted. STT is deductible here, unlike for capital gains.
- A loss can be set off against other income of the year except salary, and the balance carried forward for eight years, but only if the return is filed by the due date.

State these as general position, then say the return should be reviewed by a chartered accountant.

## The unsettled part: turnover

Turnover decides whether a tax audit is needed. **Sources disagree on the current rule**, so the script reports both:

| Output | Method |
|---|---|
| `turnover_absolute_method` | Sum of the absolute profit and loss of every trade |
| `turnover_absolute_plus_option_premium` | The same, plus premium received on option sales |

Older ICAI guidance added the option premium. The 2022 edition was widely read as dropping it. Some sources say a 2025 revision, applying from assessment year 2026-27, restores it. This could not be confirmed from the ICAI text.

So: present both figures. If `methods_agree` is true (no options sold), there is nothing to resolve. If both fall on the same side of the thresholds, the audit answer does not depend on the method; say so. If they straddle a threshold, tell the user plainly that the answer depends on which method their chartered accountant applies, and that this is the question to take to them. Do not pick one.

**Thresholds shown:** Rs 1 crore generally; Rs 10 crore where cash receipts and cash payments are each within 5% of the total (true for nearly all exchange trading). Whether an audit is actually required also turns on the presumptive-scheme rules and the profit declared, which the script does not evaluate. Never tell a user they do or do not need an audit; give the figures and the thresholds.

## Limits

Summarises the rows supplied; it does not read broker files or compute trade P&L from fills. Intraday equity (speculative business income) is separate and not included. Slab tax is not computed. The rules here were checked against secondary sources only.
