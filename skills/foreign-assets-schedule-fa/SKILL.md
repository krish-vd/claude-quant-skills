---
name: foreign-assets-schedule-fa
description: Prepare the Schedule FA (foreign assets) figures an Indian resident needs for US or other foreign shares and ETFs - cost, peak value during the calendar year and the date it occurred, closing value on 31 December, and sale proceeds - in the foreign currency and converted to rupees with exchange rates the user supplies. Use when the user holds US stocks, RSUs, ESPP shares or foreign ETFs and asks how to report them in their Indian tax return, what to put in Schedule FA or Table A3, or what the peak or closing value of their foreign holdings was.
---

# Foreign Assets: Schedule FA

```bash
python scripts/schedule_fa.py --trades us_trades.csv --year 2025 --rates sbi_rates.csv
```

`us_trades.csv` (prices in the foreign currency):

```csv
date,symbol,side,quantity,price
2024-03-15,AAPL,buy,10,172
2025-02-10,AAPL,buy,5,228
2025-09-02,AAPL,sell,4,230
```

`sbi_rates.csv` (the number below only shows the format; it is not a real rate):

```csv
date,rate
2025-12-31,00.00
```

For RSUs and ESPP, the buy row is the vest or purchase date with the fair market value per share on that date.

## Three things users get wrong

1. **Calendar year, not financial year.** Schedule FA for the return of financial year 2025-26 covers 1 January to 31 December 2025. `--year` is that calendar year.
2. **It applies even with no sale and no gain.** A resident and ordinarily resident person who held a foreign asset at any time in the year must report it, however small.
3. **Rupee values need the rate on specific dates.** The telegraphic transfer buying rate applies on the acquisition date for cost, the peak date for peak value, and 31 December for closing value.

## How to run it with the user

Run it once without `--rates`. The output gives the foreign-currency figures and, under `rates_needed`, the exact dates for which a rate is required. The user looks those up (SBI publishes its TT buying rates; many brokers serving Indian investors also list them), puts them in the rates file, and the second run fills in the rupee values.

**Never fill a missing rate with an estimate or a market rate.** The script leaves the rupee value empty instead; do the same. A plausible-looking wrong rate in a disclosure schedule is worse than a blank the user knows they must fill.

## Reading a row

`initial_value` (cost), `peak_value` with `peak_date`, `closing_value` with `closing_date`, `sale_proceeds`, each in foreign currency and in rupees where a rate was supplied; `shares_at_year_end`; and `purchase_lots` listing each acquisition. A holding sold out during the year shows a closing value of zero and is still reported.

Check with the user:

- **Peak date.** It is found from daily closes and the shares held each day. Because the exchange rate also moves, the rupee peak can fall on a nearby day. If the top two days are close in value, get rates for both and use the higher rupee figure.
- **Earlier sales.** `initial_value` sums every purchase to the year end. If shares were sold in a previous year, reduce it to the cost of what was held.
- **Splits.** Prices are split-adjusted, so quantities in the trade file must be on the post-split basis.

## What this does not cover

- **Dividends** go in Schedule FSI; US tax withheld is claimed through Schedule TR, with Form 67 filed before the return.
- **Capital gains** on sales go in the capital-gains schedule: use `india-capital-gains` with `foreign_equity` and rupee amounts.
- Foreign bank and brokerage **cash balances** (other tables of Schedule FA).
- Sources differ on whether several lots of one share go in one row or separate rows; `purchase_lots` supports either.

The penalties for missing or wrong foreign-asset disclosure are severe and apply even when no tax is due. Say so, and recommend a chartered accountant reviews the schedule before filing. This skill prepares the numbers; it does not replace that review.
