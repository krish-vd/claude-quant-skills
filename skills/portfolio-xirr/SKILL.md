---
name: portfolio-xirr
description: Calculate XIRR (annualised, money-weighted return) for a SIP, a mutual fund folio, a stock position or a whole portfolio from dated cash flows, optionally valuing mutual fund units at the official AMFI NAV. Use when the user asks for their SIP returns, XIRR, annualised return, what their mutual fund has actually earned, or wants to compare the real return of two investments made in instalments.
---

# Portfolio XIRR

XIRR is the right return measure when money went in or out on different dates (SIPs, top-ups, partial redemptions). It uses the same convention as spreadsheet `XIRR` (actual days / 365). Run the script; do not estimate.

## Run it

```bash
# Cash flows plus a current value you supply
python scripts/xirr_calc.py --cashflows flows.csv --current-value 170000 --as-of 2026-11-12

# Mutual fund: value the units at the latest official AMFI NAV
python scripts/xirr_calc.py --cashflows flows.csv --units 1800 --scheme-code 122639
```

`flows.csv`:

```csv
date,amount
2025-01-01,-100000
2025-07-01,-50000
2025-12-15,2000
```

**Sign convention: money you paid in is negative; money you received (redemptions, dividends) is positive.** The current value is added as a final positive flow. This is the most common mistake: check the signs before running.

To find a scheme code, use the `market-data` skill: `mf-search "parag parikh flexi cap direct growth"`. Match the exact plan (Direct or Regular) and option (Growth or IDCW): they have different NAVs.

## Reading the output

- `xirr_pct`: annualised return. Quote it with the date range (`first_flow` to `last_flow`).
- `valuation`: the NAV, NAV date and source used, when units were valued from AMFI.
- For holdings under one year, XIRR annualises a short period and can look extreme. Say so, and give `absolute_gain` alongside it.

## Limits

- XIRR says nothing about risk, and is not comparable with a fund's published point-to-point (time-weighted) return.
- A whole-portfolio XIRR needs every cash flow across all holdings in one file, plus one total current value.
- Unusual flow patterns (large withdrawals mid-way) can have more than one mathematical solution; the script returns one. If the result looks wrong, check the signs first.
- Past returns do not predict future returns.
