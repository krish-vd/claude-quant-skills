# Status and roadmap

A skill counts as built only when its calculator has hand-checked tests and any rates it uses are in the rulebook with a source.

## Built: 50 skills

| Area | Skills |
|---|---|
| Costs and sizing | `trade-cost-calculator`, `position-sizer` |
| Data | `market-data` |
| Market regime | `market-breadth`, `sector-rotation`, `institutional-positioning`, `commodity-regime`, `market-posture-daily` |
| Screens | `stock-screener` (relative strength, trend template, breakout, new high, volatility contraction), `delivery-volume-screener`, `dividend-screener` |
| Fundamentals and events | `company-fundamentals`, `results-calendar`, `market-news-brief` |
| Market timing, macro, crypto | `market-timing`, `macro-regime`, `crypto-regime`, `cot-positioning` |
| More research | `growth-leader-screener`, `earnings-reaction`, `pair-trading-screener`, `chart-reader`, `institutional-holdings-13f`, `options-strategy-advisor`, `strategy-idea-pipeline` |
| Routines | `daily-trading-routine`, `weekly-review-routine`, `tax-year-routine` |
| Research | `backtest-runner` (five strategies, out-of-sample, sweep, regime filter, Monte Carlo, point-in-time universe), `backtest-reviewer` |
| Futures and options | `option-pricer`, `option-payoff-builder`, `option-chain-analyzer`, `fno-expiry-calendar`, `futures-basis-rollover` |
| Discipline | `trade-journal`, `trade-review`, `risk-circuit-breaker`, `pre-trade-checklist` |
| Long-term investing | `portfolio-xirr`, `sip-planner`, `mf-returns`, `portfolio-rebalancer` |
| Tax (India) | `india-capital-gains`, `tradebook-importer`, `corporate-action-adjuster`, `tax-harvest-planner`, `advance-tax-on-gains`, `fno-business-income`, `foreign-assets-schedule-fa` |

Shared library `marketcore`: dated rulebook, charges, cost model, sizing, capital gains, harvest planning, trade-book parsing, corporate actions, rebalancing, XIRR, SIP and return statistics, indicators, backtest engine, robustness and review checks, screens, breadth, sectors, positioning, delivery, dividends, option models, option chain, futures tools, journal, and data adapters for NSE (bhavcopy old and new formats, lot sizes, index members, participant open interest, FII/DII cash, delivery, F&O ban list), AMFI, mfapi.in and Yahoo.

## Deliberately not built

| Idea | Why not |
|---|---|
| Mutual fund portfolio overlap | Needs each fund's holdings. There is no free, reliable, machine-readable source, and a wrong overlap figure is worse than none |
| Automatic SBI TT buying rates | No free feed. Schedule FA lists the dates needed and takes the rates from the user |
| Buy or sell signals | Out of scope by design: the skills rank, measure and test; the decision stays with the user |

## Known gaps, in order of importance

1. **Survivorship bias in rebuilt stocks.** `--pit-universe` picks stocks without hindsight, and stocks missing from the price source are rebuilt from NSE bhavcopies (`marketcore/data/bhavprices.py`): splits and bonuses from NSE's corporate-actions feed, renames followed by ISIN, demerger drops neutralised. Still open: dividends and rights issues in rebuilt stocks, renames where the ISIN also changed, and a US equivalent.
2. **Backtest prices are unofficial** (Yahoo). Recent Indian sessions are cross-checked or repaired from the NSE bhavcopy; older history is not.
3. **Secondary-sourced rates:** MCX charges and lot sizes, stamp duty, SEBI fee, BSE charges, advance-tax schedule, audit thresholds. Each needs its primary document.
4. **Disputed rules:** whether option premium is added to F&O turnover; whether Schedule FA lots are aggregated. Both readings are shown.
5. **Unconfirmed:** the FINRA trading activity fee pause for October to December 2026.
6. **Tax scope:** resident individuals, transfers from 1 April 2025; no surcharge, loss set-off, or slab tax; no US-resident tax view.
7. **Backtester scope:** long only, daily bars, no dividends, no F&O or intraday strategies.
8. **Markets:** no BSE derivatives, no MCX prices or option chains, no currency derivatives.
9. **US breadth and screens** need the user to supply a symbol list: there is no built-in index membership for US indices.

## Still to build

The areas listed here earlier (growth screening, market timing, macro, pairs, options strategy selection, results reactions, chart reading, an idea pipeline, 13F, COT, crypto) are now built. What remains is in "Known gaps" above and "Ideas for later" below.

## Ideas for later

- An adjusted Indian price database from bhavcopies, to finish the survivorship fix and remove the dependence on Yahoo.
- Historical rollover and implied-volatility percentiles (needs a stored history of daily F&O files).
- Earnings and results calendars; bulk and block deal data.
- Short-side and F&O strategy backtests; position sizing by volatility targeting.
- A US tax view for US residents.
