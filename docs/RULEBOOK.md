# Rulebook

Generated from `marketcore/rulebook/*.json` by `scripts/build_rulebook_doc.py`. Do not edit by hand.

Source standing: **primary** = read from the exchange or regulator's own document; **secondary** = cross-checked against a broker or summary only; **unverified** = general knowledge, not checked against a document; **unconfirmed** = a filed change whose effect was not confirmed.

## India: trade charges

India: statutory and exchange levies on trades. Rates are fractions of the stated basis (0.001 = 0.1%). Coverage starts 2024-10-01; the calculator refuses earlier trade dates.

| Rule | Applies to | Side | Basis | From | To | Rate | Source |
|---|---|---|---|---|---|---|---|
| `stt.equity_delivery` | equity_delivery | both | turnover | 2024-10-01 | current | 0.1% | [primary](https://nsearchives.nseindia.com/content/circulars/FATAX73524.pdf) |
| `stt.equity_intraday` | equity_intraday | sell | turnover | 2024-10-01 | current | 0.025% | [primary](https://nsearchives.nseindia.com/content/circulars/FATAX73524.pdf) |
| `stt.etf_delivery` | etf_delivery | sell | turnover | 2024-10-01 | current | 0.001% | [primary](https://nsearchives.nseindia.com/content/circulars/FATAX73524.pdf) |
| `stt.futures` | futures | sell | turnover | 2024-10-01 | 2026-03-31 | 0.02% | [primary](https://nsearchives.nseindia.com/content/circulars/FATAX73524.pdf) |
| `stt.futures` | futures | sell | turnover | 2026-04-01 | current | 0.05% | [primary](https://nsearchives.nseindia.com/content/circulars/FATAX73524.pdf) |
| `stt.options` | options | sell | premium | 2024-10-01 | 2026-03-31 | 0.1% | [primary](https://nsearchives.nseindia.com/content/circulars/FATAX73524.pdf) |
| `stt.options` | options | sell | premium | 2026-04-01 | current | 0.15% | [primary](https://nsearchives.nseindia.com/content/circulars/FATAX73524.pdf) |
| `stt.options_exercise` | options_exercise | buy | intrinsic_value | 2024-10-01 | 2026-03-31 | 0.125% | [primary](https://nsearchives.nseindia.com/content/circulars/FATAX73524.pdf) |
| `stt.options_exercise` | options_exercise | buy | intrinsic_value | 2026-04-01 | current | 0.15% | [primary](https://nsearchives.nseindia.com/content/circulars/FATAX73524.pdf) |
| `txn.nse.cash` | equity_delivery, equity_intraday, etf_delivery (NSE) | both | turnover | 2024-10-01 | 2026-02-28 | 0.00297% | [primary](https://nsearchives.nseindia.com/content/circulars/FA73061.pdf) |
| `txn.nse.cash` | equity_delivery, equity_intraday, etf_delivery (NSE) | both | turnover | 2026-03-01 | current | 0.0030699% | [primary](https://nsearchives.nseindia.com/content/circulars/FA73061.pdf) |
| `txn.nse.futures` | futures (NSE) | both | turnover | 2024-10-01 | 2026-02-28 | 0.00173% | [primary](https://nsearchives.nseindia.com/content/circulars/FA73061.pdf) |
| `txn.nse.futures` | futures (NSE) | both | turnover | 2026-03-01 | current | 0.0018299% | [primary](https://nsearchives.nseindia.com/content/circulars/FA73061.pdf) |
| `txn.nse.options` | options (NSE) | both | premium | 2024-10-01 | 2026-02-28 | 0.03503% | [primary](https://nsearchives.nseindia.com/content/circulars/FA73061.pdf) |
| `txn.nse.options` | options (NSE) | both | premium | 2026-03-01 | current | 0.0355299% | [primary](https://nsearchives.nseindia.com/content/circulars/FA73061.pdf) |
| `ipft.nse.cash` | equity_delivery, equity_intraday, etf_delivery (NSE) | both | turnover | 2024-10-01 | 2026-02-28 | 0.0001% | [primary](https://nsearchives.nseindia.com/content/circulars/FA73061.pdf) |
| `ipft.nse.cash` | equity_delivery, equity_intraday, etf_delivery (NSE) | both | turnover | 2026-03-01 | current | 0.0000001% | [primary](https://nsearchives.nseindia.com/content/circulars/FA73061.pdf) |
| `ipft.nse.futures` | futures (NSE) | both | turnover | 2024-10-01 | 2026-02-28 | 0.0001% | [primary](https://nsearchives.nseindia.com/content/circulars/FA73061.pdf) |
| `ipft.nse.futures` | futures (NSE) | both | turnover | 2026-03-01 | current | 0.0000001% | [primary](https://nsearchives.nseindia.com/content/circulars/FA73061.pdf) |
| `ipft.nse.options` | options (NSE) | both | premium | 2024-10-01 | 2026-02-28 | 0.0005% | [primary](https://nsearchives.nseindia.com/content/circulars/FA73061.pdf) |
| `ipft.nse.options` | options (NSE) | both | premium | 2026-03-01 | current | 0.0000001% | [primary](https://nsearchives.nseindia.com/content/circulars/FA73061.pdf) |
| `txn.bse.cash` | equity_delivery, equity_intraday, etf_delivery (BSE) | both | turnover | 2026-11-12 | current | 0.00375% | [secondary](https://zerodha.com/charges/) |
| `txn.mcx.futures` | commodity_futures (MCX) | both | turnover | 2026-11-12 | current | 0.0021% | [secondary](https://zerodha.com/charges/) |
| `txn.mcx.options` | commodity_options (MCX) | both | premium | 2026-11-12 | current | 0.0418% | [secondary](https://zerodha.com/charges/) |
| `ctt.futures` | commodity_futures | sell | turnover | 2024-10-01 | current | 0.01% | [secondary](https://zerodha.com/charges/) |
| `ctt.options` | commodity_options | sell | premium | 2024-10-01 | current | 0.05% | [secondary](https://zerodha.com/charges/) |
| `sebi.turnover_fee` | equity_delivery, equity_intraday, etf_delivery, futures, options, commodity_futures, commodity_options | both | turnover_or_premium | 2024-10-01 | current | 0.0001% | [secondary](https://zerodha.com/charges/) |
| `stamp.equity_delivery` | equity_delivery, etf_delivery | buy | turnover | 2024-10-01 | current | 0.015% | [secondary](https://zerodha.com/charges/) |
| `stamp.equity_intraday` | equity_intraday | buy | turnover | 2024-10-01 | current | 0.003% | [secondary](https://zerodha.com/charges/) |
| `stamp.futures` | futures, commodity_futures | buy | turnover | 2024-10-01 | current | 0.002% | [secondary](https://zerodha.com/charges/) |
| `stamp.options` | options, commodity_options | buy | premium | 2024-10-01 | current | 0.003% | [secondary](https://zerodha.com/charges/) |
| `gst` | * | both | brokerage+exchange_txn+ipft+sebi_fee | 2024-10-01 | current | 18% | [secondary](https://zerodha.com/charges/) |

Sources:

- **primary** - [NSE circular NSE/FATAX/73524 (31 Mar 2026): Changes in relation to rates of Securities Transaction Tax (Finance Act, 2026)](https://nsearchives.nseindia.com/content/circulars/FATAX73524.pdf) (checked 2026-11-12)
- **primary** - [NSE circular NSE/FA/73061 (27 Feb 2026): Revision in Transaction Charges](https://nsearchives.nseindia.com/content/circulars/FA73061.pdf) (checked 2026-11-12)
- **secondary** - [Zerodha list of charges (broker page, used as a cross-check)](https://zerodha.com/charges/) (checked 2026-11-12)

## US: equity regulatory fees

US: regulatory fees on equity sales. Broker commissions are user-supplied. Options and futures regulatory fees are not covered.

| Rule | Applies to | Side | Basis | From | To | Rate | Source |
|---|---|---|---|---|---|---|---|
| `us.sec_section31` | all | sell | turnover | 2025-05-14 | 2026-04-03 | 0% | [primary](https://www.sec.gov/rules-regulations/fee-rate-advisories/2026-2) |
| `us.sec_section31` | all | sell | turnover | 2026-04-04 | current | 0.00206% | [primary](https://www.sec.gov/rules-regulations/fee-rate-advisories/2026-2) |
| `us.finra_taf` | all | sell | shares | 2025-05-14 | 2025-12-31 | 0.000166 (max 8.30) | [primary](https://www.finra.org/rules-guidance/rule-filings/sr-finra-2024-019/fee-adjustment-schedule) |
| `us.finra_taf` | all | sell | shares | 2026-01-01 | 2026-09-30 | 0.000195 (max 9.79) | [primary](https://www.finra.org/rules-guidance/rule-filings/sr-finra-2024-019/fee-adjustment-schedule) |
| `us.finra_taf` | all | sell | shares | 2026-10-01 | 2026-12-31 | 0 (max 0) | [unconfirmed](https://www.finra.org/rules-guidance/rule-filings/sr-finra-2026-021) |
| `us.finra_taf` | all | sell | shares | 2027-01-01 | current | 0.000195 (max 9.79) | [unconfirmed](https://www.finra.org/rules-guidance/rule-filings/sr-finra-2024-019/fee-adjustment-schedule) |

Sources:

- **primary** - [SEC Fee Rate Advisory #2 for Fiscal Year 2026 (Section 31 transaction fee)](https://www.sec.gov/rules-regulations/fee-rate-advisories/2026-2) (checked 2026-11-12)
- **primary** - [FINRA fee adjustment schedule, SR-FINRA-2024-019 (Trading Activity Fee rates 2024-2029)](https://www.finra.org/rules-guidance/rule-filings/sr-finra-2024-019/fee-adjustment-schedule) (checked 2026-11-12)
- **unconfirmed** - [SR-FINRA-2026-021: proposed three-month pause of the Trading Activity Fee (1 Oct - 31 Dec 2026)](https://www.finra.org/rules-guidance/rule-filings/sr-finra-2026-021) (checked 2026-11-12)

## India: capital gains (resident individual)

India: capital gains rules for a resident individual. Coverage: transfers on or after 2025-04-01 (FY 2025-26 onward). Earlier years had mid-year rate changes and are refused.

| Asset class | Long-term after | Short-term gains | Long-term gains | Exemption per FY |
|---|---|---|---|---|
| `listed_equity`: Listed equity shares, equity-oriented mutual fund units and business trust units, STT paid | 12 months | 20% | 12.5% | Rs 125,000 |
| `foreign_equity`: Shares listed only outside India (for example US stocks) and other unlisted shares | 24 months | slab rate | 12.5% | none |
| `debt_fund_post_2023`: Specified (debt-oriented) mutual fund units acquired on or after 1 Apr 2023 | never | slab rate | - | - |
| `listed_other`: Other listed securities, for example gold and silver ETFs | 12 months | slab rate | 12.5% | none |
| `unlisted_other`: Other unlisted capital assets, for example gold funds-of-funds and overseas funds-of-funds | 24 months | slab rate | 12.5% | none |

Not handled:

- Surcharge (income above Rs 50 lakh) and its 15% cap on equity gains
- Set-off of losses between buckets and carry-forward from earlier years (reported, not applied)
- Shortfall of the basic exemption limit adjusted against special-rate gains
- Derivatives (F&O) and intraday equity: these are business income, not capital gains
- Buybacks, bonus stripping, corporate actions that change cost (splits, bonuses, demergers)
- Non-residents, HUFs, companies, and the US-person tax view

Sources:

- **primary** - [Income-tax Act, 2025, section 196 (tax on short-term capital gains in certain cases; was section 111A)](https://www.incometaxindia.gov.in/w/section-196-76) (checked 2026-11-12)
- **secondary** - [Secondary summaries of the Income-tax Act, 2025 capital gains provisions (sections 197, 198; holding periods)](https://help.myitreturn.com/hc/en-us/articles/60943188924313-Capital-Gains-Holding-Periods-Tax-Rates-Income-Tax-Act-2025) (checked 2026-11-12)
- **secondary** - [Broker guides on taxation of US stocks for Indian residents](https://www.angelone.in/news/taxation/how-us-stocks-are-taxed-in-india-foreign-asset-reporting-capital-gains-and-ftc-explained) (checked 2026-11-12)

## Futures contract specifications

Futures contract specifications. 'multiplier' is the currency value of a 1.0 move in the quoted price for one contract (one lot). NSE index and stock derivative lot sizes are NOT here: they are read live from NSE's fo_mktlots.csv.

| Symbol | Exchange | Contract | Multiplier | Tick | Currency | Source |
|---|---|---|---|---|---|---|
| ES | CME | E-mini S&P 500 | 50 | 0.25 | USD | [unverified](https://www.cmegroup.com/markets.html) |
| NQ | CME | E-mini Nasdaq-100 | 20 | 0.25 | USD | [unverified](https://www.cmegroup.com/markets.html) |
| YM | CBOT | E-mini Dow ($5) | 5 | 1 | USD | [unverified](https://www.cmegroup.com/markets.html) |
| RTY | CME | E-mini Russell 2000 | 50 | 0.1 | USD | [unverified](https://www.cmegroup.com/markets.html) |
| GC | COMEX | Gold (100 troy oz) | 100 | 0.1 | USD | [unverified](https://www.cmegroup.com/markets.html) |
| SI | COMEX | Silver (5,000 troy oz) | 5000 | 0.005 | USD | [unverified](https://www.cmegroup.com/markets.html) |
| HG | COMEX | Copper (25,000 lb) | 25000 | 0.0005 | USD | [unverified](https://www.cmegroup.com/markets.html) |
| PL | NYMEX | Platinum (50 troy oz) | 50 | 0.1 | USD | [unverified](https://www.cmegroup.com/markets.html) |
| CL | NYMEX | WTI Crude Oil (1,000 bbl) | 1000 | 0.01 | USD | [unverified](https://www.cmegroup.com/markets.html) |
| NG | NYMEX | Henry Hub Natural Gas (10,000 mmBtu) | 10000 | 0.001 | USD | [unverified](https://www.cmegroup.com/markets.html) |
| ZN | CBOT | 10-Year US Treasury Note | 1000 | 0.015625 | USD | [unverified](https://www.cmegroup.com/markets.html) |
| ZB | CBOT | 30-Year US Treasury Bond | 1000 | 0.03125 | USD | [unverified](https://www.cmegroup.com/markets.html) |
| MES | CME | Micro E-mini S&P 500 | 5 | 0.25 | USD | [unverified](https://www.cmegroup.com/markets.html) |
| MNQ | CME | Micro E-mini Nasdaq-100 | 2 | 0.25 | USD | [unverified](https://www.cmegroup.com/markets.html) |
| MGC | COMEX | Micro Gold (10 troy oz) | 10 | 0.1 | USD | [unverified](https://www.cmegroup.com/markets.html) |
| SIL | COMEX | Micro Silver (1,000 troy oz) | 1000 | 0.005 | USD | [unverified](https://www.cmegroup.com/markets.html) |
| MCL | NYMEX | Micro WTI Crude Oil (100 bbl) | 100 | 0.01 | USD | [unverified](https://www.cmegroup.com/markets.html) |
| GOLD | MCX | Gold (1 kg, quoted per 10 g) | 100 | 1 | INR | [secondary](https://www.mcxindia.com/products) |
| GOLDM | MCX | Gold Mini (100 g, quoted per 10 g) | 10 | 1 | INR | [secondary](https://www.mcxindia.com/products) |
| SILVER | MCX | Silver (30 kg, quoted per kg) | 30 | 1 | INR | [secondary](https://www.mcxindia.com/products) |
| SILVERM | MCX | Silver Mini (5 kg, quoted per kg) | 5 | 1 | INR | [secondary](https://www.mcxindia.com/products) |
| SILVERMIC | MCX | Silver Micro (1 kg, quoted per kg) | 1 | 1 | INR | [secondary](https://www.mcxindia.com/products) |
| CRUDEOIL | MCX | Crude Oil (100 bbl) | 100 | 1 | INR | [secondary](https://www.mcxindia.com/products) |
| CRUDEOILM | MCX | Crude Oil Mini (10 bbl) | 10 | 1 | INR | [secondary](https://www.mcxindia.com/products) |
| NATURALGAS | MCX | Natural Gas (1,250 mmBtu) | 1250 | 0.1 | INR | [secondary](https://www.mcxindia.com/products) |
| NATGASMINI | MCX | Natural Gas Mini (250 mmBtu) | 250 | 0.1 | INR | [secondary](https://www.mcxindia.com/products) |
| COPPER | MCX | Copper (2,500 kg, quoted per kg) | 2500 | 0.05 | INR | [secondary](https://www.mcxindia.com/products) |
