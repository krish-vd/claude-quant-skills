---
name: market-data
description: Fetch market data with no API key - official NSE end-of-day prices (bhavcopy), live NSE F&O lot sizes, official AMFI mutual fund NAVs and scheme search, futures contract specifications (MCX and US), and daily prices for US stocks, ETFs and futures. Use when the user asks for the closing price of an Indian or US stock, a mutual fund NAV or scheme code, the lot size of Nifty or any F&O stock, the size of a gold or crude contract, or when another skill needs a price, lot size or NAV.
---

# Market Data

One script, six commands. Prefer the official sources; they are the record a broker or tax officer would use.

```bash
python scripts/market_data.py nse-quote RELIANCE [--date 2026-11-11] [--series EQ]
python scripts/market_data.py nse-lot BANKNIFTY [--expiry-month DEC-26]
python scripts/market_data.py mf-search "parag parikh flexi cap direct growth"
python scripts/market_data.py mf-nav --scheme-code 122639        # or --isin INF879O01027
python scripts/market_data.py contract GOLDM                      # MCX and US futures specs
python scripts/market_data.py yahoo AAPL --range 1mo              # also SPY, GC=F, CL=F, ^NSEI
```

## Which source for what

| Need | Command | Source | Standing |
|---|---|---|---|
| Indian stock close, OHLC, volume | `nse-quote` | NSE bhavcopy | Official end-of-day record |
| F&O lot size | `nse-lot` | NSE `fo_mktlots.csv` | Official, current |
| Mutual fund NAV, scheme code | `mf-nav`, `mf-search` | AMFI `NAVAll.txt` | Official daily NAV |
| MCX / US futures contract size | `contract` | Repo rulebook | Secondary or unverified - see `source_kind` |
| US stocks, ETFs, futures, indices | `yahoo` | Yahoo chart endpoint | **Unofficial**, indicative only |

## Rules for using the data

- **Always state the date of a price.** NSE data is end-of-day; today's bhavcopy appears in the evening (India time). Without `--date`, `nse-quote` returns the latest published day: say which day that is. These are not live quotes.
- **Never present a Yahoo price as official.** It is fine for sizing a position or a rough valuation; it is not a settlement price. For Indian stocks use `nse-quote`, not `yahoo SYMBOL.NS`.
- Mutual fund search returns Direct and Regular plans, Growth and IDCW options separately. Confirm with the user which one they hold before using a NAV.
- NSE series: `EQ` is normal equity. `BE` is trade-for-trade. ETFs trade in `EQ`. If a symbol is not found, try `--series BE` before saying it does not exist.
- Every result includes a `source` URL. Quote it when the number matters (tax, a dispute over a contract note).

## Limits

- No intraday or live prices, no options chains, no MCX prices, no fundamentals.
- Files are cached under `~/.cache/market-skills` (bhavcopy forever, lot sizes 12 hours, NAVs 3 hours).
- If NSE or AMFI is unreachable, the script returns an error. Report it; do not substitute a remembered or estimated price.
