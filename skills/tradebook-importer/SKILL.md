---
name: tradebook-importer
description: Convert a broker tradebook or trade history export (Zerodha, Groww, Upstox, Angel, Dhan, ICICI Direct, or any CSV with date, symbol, buy/sell, quantity and price) into the standard trade CSV used for capital gains, separating intraday round trips and setting F&O rows aside. Use when the user has a tradebook, contract note export or trade history file and wants their capital gains, a tax harvest plan, or a clean list of delivery trades.
---

# Tradebook Importer

The first step before `india-capital-gains` or `tax-harvest-planner` when the user has a broker export.

```bash
python scripts/import_tradebook.py --input tradebook-2023.csv --input tradebook-2024.csv \
  --input tradebook-2025.csv --output trades.csv
```

Column names are detected automatically (`trade_date` / `Date` / `Execution date and time`, `symbol` / `Scrip` / `tradingsymbol`, `trade_type` / `Buy/Sell` / `Type`, `quantity` / `Qty`, `price` / `Rate` ...). If detection fails the error lists the file's columns; name them:

```bash
python scripts/import_tradebook.py --input trades_export.csv --output trades.csv \
  --map date=TradeDt --map side=Dir --map quantity=Units --map price=Px --date-format %m/%d/%Y
```

Dates like `02/06/2025` are read day-first (the Indian convention). For US-style files pass `--date-format %m/%d/%Y`. The input must be CSV: for an Excel export, save the trade sheet as CSV first, without the title rows above the header.

## What it does, and why it matters

1. **Keeps cash-equity rows only.** Rows whose segment looks like F&O, currency or commodity are counted in `derivative_rows_skipped`. Derivative profits are business income, not capital gains.
2. **Separates intraday trades.** If a symbol was both bought and sold on the same day, the overlapping quantity never reached the demat account. It is speculative business income, listed under `intraday` with its profit or loss, and removed from the delivery file. Left in, it would consume the wrong FIFO lots and misstate every later gain in that stock.
3. **Writes the standard CSV** (`date,symbol,side,quantity,price,asset_class,charges`).

## Before using the output - check these with the user

- **Is the history complete?** Capital gains need every purchase of every share sold, including years ago and at other brokers. Compare `first_trade_date` with when they started investing. Shares that arrived by transfer, IPO allotment, bonus, ESOP or gift are not in a tradebook: they must be added as buy rows by hand (cost and date from the relevant record).
- **Corporate actions.** Splits, bonuses and demergers are not applied. Ask whether any holding had one, and adjust the rows (a 1:1 bonus adds a buy at zero cost on the allotment date; a split multiplies quantity and divides price).
- **`unreadable_rows`.** Any row listed there was dropped. Resolve each one; a missing trade gives a wrong answer.
- **`symbols`.** Scan the list for renamed or merged companies: the same holding under two symbols will not match.
- **Charges** are written as 0. Brokerage and other costs excluding STT may be added per row to reduce the gain; leaving them at 0 slightly overstates it.

Report the counts plainly (rows read, delivery trades written, intraday round trips, derivative rows skipped) so the user can reconcile them with their broker's statement. If their broker provides its own tax P&L report, suggest comparing totals: a difference is a sign of missing history or a corporate action.

## Limits

CSV only. One file format per run is assumed across all `--input` files. Mutual fund statements (CAS) and foreign broker statements with multi-currency rows are not handled here; for US stocks convert amounts to rupees first and pass `--asset-class foreign_equity`.
