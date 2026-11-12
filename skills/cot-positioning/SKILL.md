---
name: cot-positioning
description: Show who holds US futures from the CFTC's weekly Commitments of Traders report - net positions of large speculators, commercial hedgers and small traders in gold, silver, copper, crude oil, natural gas, S&P 500 and Nasdaq futures, Treasury notes, the dollar, euro, yen and Bitcoin (or any contract by search) - with the three-year COT index and weekly changes. Use when the user asks about COT data, speculator or hedge fund positioning in a commodity or currency, whether a futures market is crowded, or commercial hedger activity.
---

# COT Positioning

```bash
python scripts/cot_report.py --market gold
python scripts/cot_report.py --market crude_wti --market natural_gas
python scripts/cot_report.py --all
python scripts/cot_report.py --search "SOYBEAN"        # find a contract code
python scripts/cot_report.py --code 005602
```

Built-in markets: gold, silver, copper, crude_wti, natural_gas, sp500_emini, nasdaq100_emini, us_10y_note, us_dollar_index, euro_fx, japanese_yen, bitcoin.

## Output

Per market: report date, open interest, speculator net (contracts and percent of open interest), speculator and commercial COT index (0 = lowest net in three years, 100 = highest), small-trader net, one- and four-week change in speculator net, and (single market) a 12-week history.

## Interpreting it

- **Speculators** (funds) tend to follow trends; **commercials** (producers and users hedging) tend to be on the other side.
- A speculator COT index near 100 means funds are as long as they have been in three years. Many traders read extremes as crowded and prone to sharp reversal; that is an interpretation, and extremes can last months while the trend continues. Present it as context and attribute the contrarian reading.
- The weekly change shows whether positioning is building or unwinding.
- For Indian commodity traders, US positioning in gold, silver, crude and copper matters because MCX follows international prices (`commodity-regime` shows the USD/INR link).

Positions are as of Tuesday, published Friday: always state the report date.

## Limits

Legacy futures-only report (no options or disaggregated categories). US exchanges only; there is no public equivalent for MCX.
