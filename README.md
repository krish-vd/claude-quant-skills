# claude-quant-skills

[![tests](https://github.com/krish-vd/claude-quant-skills/actions/workflows/tests.yml/badge.svg)](https://github.com/krish-vd/claude-quant-skills/actions/workflows/tests.yml) [![licence: MIT](https://img.shields.io/badge/licence-MIT-blue.svg)](LICENSE)

**50 Claude skills for investors and traders in Indian and US markets, including commodities and crypto.**

Ask Claude in plain words, for example "how many lots of NIFTY can I trade?", "screen the Nifty 200 for growth leaders", "backtest this idea and tell me if I can trust it" or "what do I owe in capital gains this year?". Claude picks the right skill, runs a tested calculator on official data, and explains the result. It does not guess numbers.

An independent open-source project built for Claude, not affiliated with or endorsed by Anthropic.

Use it as a **strategy enhancer**: a toolkit that sharpens your own process (costs, sizing, research, testing, discipline, tax), not a system that tells you what to buy.

> **Not advice.** Educational and research use only. Not investment, tax or legal advice, and not a registered research or advisory service in India (SEBI), the United States (SEC, FINRA, CFTC) or anywhere else. Markets carry risk of loss. Check every number against your contract note, your broker and a qualified professional before acting on it. See [DISCLAIMER.md](DISCLAIMER.md).

---

## Contents

- [Quick start](#quick-start)
- [What you can ask](#what-you-can-ask)
- [All 50 skills](#all-50-skills)
- [Routines: the skills working together](#routines-the-skills-working-together)
- [Why the numbers can be trusted](#why-the-numbers-can-be-trusted)
- [The backtester](#the-backtester)
- [What has been verified, and what has not](#what-has-been-verified-and-what-has-not)
- [Data sources](#data-sources)
- [Install in detail](#install-in-detail)
- [Configuration](#configuration)
- [Using the scripts without Claude](#using-the-scripts-without-claude)
- [Repository layout](#repository-layout)
- [Development](#development)
- [Known limitations](#known-limitations)
- [FAQ](#faq)
- [Disclaimer](#disclaimer)
- [Licence](#licence)

---

## Quick start

You need Python 3.10 or newer and [Claude Code](https://claude.com/claude-code). Nothing else: no API keys, no paid data, no third-party Python packages.

```bash
git clone https://github.com/krish-vd/claude-quant-skills.git
cd claude-quant-skills
python scripts/install_skills.py
```

Start a new Claude Code session and ask:

> I have a 10 lakh account. I want to go long NIFTY futures at 25000 with a stop at 24900, risking 1%. How many lots?

Claude reads the live lot size from NSE and answers: 1 lot, a planned loss of ₹6,500, and a warning that margin and overnight gaps are not covered by the stop.

---

## What you can ask

| You want to... | Ask something like | Skills used |
|---|---|---|
| Know your costs | "What do I pay to buy and sell 100 Reliance at 1,330 and 1,350?" | `trade-cost-calculator` |
| Size a trade | "How many shares of TCS at 3,500 with a stop at 3,400, risking 1%?" | `position-sizer` |
| Read the market | "Give me this morning's market posture for India" | `market-posture-daily`, `market-breadth`, `market-timing` |
| Find candidates | "Screen the Nifty 500 for stocks in a strong uptrend with accelerating earnings" | `stock-screener`, `growth-leader-screener` |
| Check a company | "How did Infosys's last quarter compare with a year ago?" | `company-fundamentals`, `earnings-reaction` |
| Plan around events | "Do any of my holdings report results this week?" | `results-calendar` |
| Understand a move | "Why did HDFC Bank fall today?" | `market-news-brief` |
| Trade options | "I'm neutral on NIFTY this week: compare the structures on today's chain" | `options-strategy-advisor`, `option-chain-analyzer`, `option-pricer`, `option-payoff-builder` |
| Test an idea | "Does buying a 2-day RSI dip in an uptrend work on the top 200 stocks?" | `strategy-idea-pipeline`, `backtest-runner`, `backtest-reviewer` |
| Stay disciplined | "Can I take another trade today? I've lost twice." | `risk-circuit-breaker`, `pre-trade-checklist`, `trade-journal` |
| Review performance | "How did my trading go this month?" | `trade-review`, `weekly-review-routine` |
| Do your taxes | "Work out my capital gains for FY 2025-26 from my Zerodha tradebook" | `tax-year-routine` and the tax skills |
| Plan long-term | "What SIP gets me to 1 crore in 15 years?" | `sip-planner`, `mf-returns`, `portfolio-rebalancer` |
| Follow commodities | "Are speculators crowded in gold? Is MCX gold at a premium?" | `cot-positioning`, `commodity-regime` |

---

## All 50 skills

### Market conditions

| Skill | What it does | Markets |
|---|---|---|
| [`market-posture-daily`](skills/market-posture-daily/) | One-page daily read: trend, breadth, volatility, FII positioning, sectors, with a rule checklist | India, US |
| [`market-breadth`](skills/market-breadth/) | Stocks above key averages, advances and declines, new highs and lows, index trend, VIX percentile | India, US |
| [`market-timing`](skills/market-timing/) | Distribution days, rally attempts and follow-through days, market-top checklist | Nifty 50, S&P 500 |
| [`sector-rotation`](skills/sector-rotation/) | Sectors ranked by relative strength, rank changes, breadth by industry | Nifty sector indices, US sector ETFs |
| [`institutional-positioning`](skills/institutional-positioning/) | FII, DII, proprietary and client derivatives positions; FII long/short ratio; FII/DII cash flows | India |
| [`macro-regime`](skills/macro-regime/) | Yield curve, credit appetite, copper/gold, stocks/bonds, dollar, rupee, oil, VIX; risk-on/off checklist | Global |
| [`commodity-regime`](skills/commodity-regime/) | Metals and energy trend, key ratios, international prices converted to MCX units | COMEX, NYMEX, MCX |
| [`cot-positioning`](skills/cot-positioning/) | Speculator and hedger positions in US futures (CFTC), three-year COT index | US futures |
| [`crypto-regime`](skills/crypto-regime/) | Bitcoin and altcoin trend, drawdown, volatility, Nasdaq correlation, CME positioning | Crypto |

### Finding and checking ideas

| Skill | What it does | Markets |
|---|---|---|
| [`stock-screener`](skills/stock-screener/) | Relative strength, trend template, breakouts, new highs, volatility contraction (VCP-style), with an official NSE price check | Nifty 50 to Nifty 500, US lists |
| [`growth-leader-screener`](skills/growth-leader-screener/) | Strong and accelerating earnings and sales growth from filings, plus price leadership | India, US |
| [`delivery-volume-screener`](skills/delivery-volume-screener/) | Jumps in delivered quantity from NSE's delivery file | India |
| [`dividend-screener`](skills/dividend-screener/) | Yield, years paid, years of increases, dividend growth | India, US |
| [`pair-trading-screener`](skills/pair-trading-screener/) | Cointegration, hedge ratio, half-life, spread z-score | India, US |
| [`company-fundamentals`](skills/company-fundamentals/) | Reported revenue, profit, EPS, margins, growth, trailing P/E from regulatory filings | NSE companies, US companies |
| [`earnings-reaction`](skills/earnings-reaction/) | How a stock reacts to results: gap, day move, 5- and 20-day drift; recent-results scan | India, US |
| [`results-calendar`](skills/results-calendar/) | Upcoming results dates and ex-dates for an index, watchlist or open trades | India |
| [`market-news-brief`](skills/market-news-brief/) | Sourced, dated account of the news behind a move, under strict web-search rules | India, US |
| [`chart-reader`](skills/chart-reader/) | Reads a chart image or symbol: trend, swing structure, support and resistance zones, ATR | Any |
| [`institutional-holdings-13f`](skills/institutional-holdings-13f/) | What a US fund owns and changed last quarter (SEC 13F) | US |

### Planning and placing a trade

| Skill | What it does | Markets |
|---|---|---|
| [`trade-cost-calculator`](skills/trade-cost-calculator/) | Every charge on a trade, net P&L and breakeven, at the rates in force on the trade date | NSE, BSE cash, MCX, US stocks |
| [`position-sizer`](skills/position-sizer/) | Shares or lots for a fixed percent risk, with live NSE lot sizes | Stocks, NSE F&O, MCX, US futures |
| [`pre-trade-checklist`](skills/pre-trade-checklist/) | Rule gate: stop, risk, size, reward to risk, loss limits, open-risk room | Any |
| [`risk-circuit-breaker`](skills/risk-circuit-breaker/) | Daily, weekly, monthly loss limits, losing-streak pause, open-risk cap | Any |
| [`market-data`](skills/market-data/) | Official NSE closes, F&O lots, mutual fund NAVs, contract specs, US prices | India, US |

### Futures and options

| Skill | What it does | Markets |
|---|---|---|
| [`option-chain-analyzer`](skills/option-chain-analyzer/) | PCR, max pain, parity forward, at-the-money IV, implied move, open-interest build-up | NSE |
| [`options-strategy-advisor`](skills/options-strategy-advisor/) | Compares structures for a view on the live chain: cost, max P&L, breakevens, probability, greeks | NSE, any |
| [`option-pricer`](skills/option-pricer/) | Black-76 and Black-Scholes price, greeks, implied volatility | Any |
| [`option-payoff-builder`](skills/option-payoff-builder/) | Exact breakevens and maximum profit and loss for any multi-leg position | Any |
| [`fno-expiry-calendar`](skills/fno-expiry-calendar/) | Listed expiries, days left, lot sizes, F&O ban list | NSE |
| [`futures-basis-rollover`](skills/futures-basis-rollover/) | Basis, annualised carry, rollover, calendar spread | NSE |

### Research and testing

| Skill | What it does | Markets |
|---|---|---|
| [`backtest-runner`](skills/backtest-runner/) | Backtests with real costs, point-in-time universe, out-of-sample split, sweep, regime filter, Monte Carlo | NSE, US stocks |
| [`backtest-reviewer`](skills/backtest-reviewer/) | Audits a backtest for overfitting, bias and weak evidence, gives a verdict | Any |
| [`strategy-idea-pipeline`](skills/strategy-idea-pipeline/) | From an idea to a JSON rule file, a backtest and a verdict, with an idea log | Any |

### Journal and review

| Skill | What it does | Markets |
|---|---|---|
| [`trade-journal`](skills/trade-journal/) | Records trades in a local file with planned risk and plan adherence | Any |
| [`trade-review`](skills/trade-review/) | Expectancy, R-multiples, streaks, drawdown, results by setup and by plan adherence | Any |

### Long-term investing

| Skill | What it does | Markets |
|---|---|---|
| [`sip-planner`](skills/sip-planner/) | SIP projection and goal back-solving with step-up, lumpsum, inflation, scenarios | Any |
| [`mf-returns`](skills/mf-returns/) | Trailing and rolling returns, drawdown, volatility, actual SIP XIRR, checked against AMFI | Indian mutual funds |
| [`portfolio-xirr`](skills/portfolio-xirr/) | XIRR from dated cash flows, valued at official NAV | Any |
| [`portfolio-rebalancer`](skills/portfolio-rebalancer/) | Trades back to target allocation, with no-sell and tolerance-band modes | Any |

### Tax (Indian residents)

| Skill | What it does |
|---|---|
| [`india-capital-gains`](skills/india-capital-gains/) | FIFO gains, short/long term, 2018 grandfathering, tax at 20% / 12.5%, FY 2025-26 onward |
| [`tradebook-importer`](skills/tradebook-importer/) | Broker tradebook to standard trades, intraday separated, F&O set aside |
| [`corporate-action-adjuster`](skills/corporate-action-adjuster/) | Looks up bonuses and splits on NSE and restates the trade history |
| [`tax-harvest-planner`](skills/tax-harvest-planner/) | Unused LTCG exemption, exact shares to sell, loss candidates, lots about to turn long-term |
| [`advance-tax-on-gains`](skills/advance-tax-on-gains/) | Instalments due on capital gains, by when each gain arose |
| [`fno-business-income`](skills/fno-business-income/) | F&O profit and turnover for the audit test, under both readings in use |
| [`foreign-assets-schedule-fa`](skills/foreign-assets-schedule-fa/) | Cost, peak, closing value and proceeds of foreign shares for Schedule FA |

### Routines

| Skill | What it does |
|---|---|
| [`daily-trading-routine`](skills/daily-trading-routine/) | Posture → risk check → events → screen → fundamentals → sizing → pre-trade gate → journal |
| [`weekly-review-routine`](skills/weekly-review-routine/) | Results, open risk, coming events, the market's week, three process points |
| [`tax-year-routine`](skills/tax-year-routine/) | Broker files → corporate actions → gains → harvesting → advance tax, plus F&O and foreign shares |

---

## Routines: the skills working together

Each routine is a skill that runs the others in a fixed order and stops at every gate that says no.

**Daily.** Ask "run my daily routine":

1. `market-posture-daily`: is the backdrop constructive, mixed or defensive?
2. `risk-circuit-breaker`: are you allowed to take new risk today?
3. `results-calendar`: do any holdings report soon?
4. `stock-screener`: candidates in the chosen universe.
5. `company-fundamentals`, `market-news-brief`: is the business behind the chart?
6. `position-sizer`, `trade-cost-calculator`: size and cost from **your** entry and stop.
7. `pre-trade-checklist`: does the plan pass your rules?
8. `trade-journal`: record it once filled.

**Weekly.** "Run my weekly review": results and rule adherence, open positions and their risk, coming events, how the market and sectors changed, and three specific process points from your own numbers.

**Tax year.** "Do my capital gains for FY 2025-26": imports every tradebook, applies corporate actions, checks share counts against the demat statement, computes the gains, plans year-end harvesting, works out advance tax, and handles F&O and foreign shares separately.

---

## Why the numbers can be trusted

1. **Calculations run in tested code, not in the model's head.** Every number comes from a Python script; Claude explains the output.
2. **Rates live in a dated rulebook.** Every charge and tax rate is a row in [`marketcore/rulebook/`](marketcore/rulebook/) with an effective date and a source. Change a rate by adding a dated version; past trades keep the rate they had. [docs/RULEBOOK.md](docs/RULEBOOK.md) lists them all.
3. **Every source carries its standing**: `primary` (read from the exchange's, regulator's or company's own document), `secondary` (cross-checked against brokers or summaries only), `unverified`, `unconfirmed`, or `disputed`. The scripts repeat it in their output.
4. **Out-of-range inputs are refused.** A trade date the rulebook does not cover gets an error, not an estimate.
5. **Where sources disagree, both readings are shown** (F&O turnover, Schedule FA lot reporting) instead of one being picked.
6. **Official data first**: the NSE bhavcopy, NSE's lot-size, delivery and participant files, AMFI NAVs, company filings with NSE and the SEC, CFTC reports.
7. **Unofficial data is cross-checked**: Indian closes from the free price source are compared with or repaired from the NSE bhavcopy, and mutual fund history is checked against AMFI.
8. **Expected values in tests are worked out by hand** from the cited circulars and textbook cases, independently of the code. 215 tests.

Measured on 1,000 stock-days (the Nifty 100 over ten sessions): 98.7% present in the free price source, and every one of those equal to NSE's official close. The missing 1.3% were empty rows that the tools now fill from NSE's own file.

---

## The backtester

### It does not cheat

- A signal uses the day's close and fills at the **next day's open**. A test proves that adding future bars never changes past trades.
- A stop that gaps fills at the worse open price, not the stop.
- Every fill pays the charges from the rulebook plus slippage.
- An unfinished trading session is never used.
- A second, separately written implementation of a moving-average strategy produced **1,255 of 1,255 identical trades** across the 50 Nifty stocks over ten years.

### Survivorship bias, measured

Backtesting on today's index members is the most common way backtests mislead: the list already contains the winners. The same `momentum_rotation` strategy over the same ten years, with real costs:

| Universe | Return a year | Worst drawdown |
|---|---|---|
| Today's Nifty 100 members | 29.1% | 39% |
| Point-in-time: the 100 most traded stocks as of each quarter, delisted stocks dropped | 12.1% | 49% |
| Point-in-time, with the 27 delisted, merged and renamed stocks rebuilt from NSE files (`--pit-universe 100`) | **8.8%** | 48% |
| Nifty 50, buy and hold | 12.05% | 38% |

The apparent edge was the stock list knowing the future. `--pit-universe` rebuilds the universe each quarter from NSE's own daily files back to 2016, so stocks are chosen without hindsight. Stocks the price source no longer carries (DHFL, Reliance Capital, HDFC, Sintex, the merged PSU banks and others) are rebuilt from the official NSE bhavcopies. Splits and bonuses are adjusted from NSE's corporate-actions feed. Renamed companies are followed by ISIN (Infibeam to CCAVENUE, NIIT Tech to Coforge). Demerger drops are treated as value passed to the new shares, not as losses. Leaving those 27 stocks out had added 3.4 percentage points a year.

A held stock that stops trading is closed at its last traded price. Use `--delisting-haircut-pct 100` to bound the result as if every delisting were a total loss.

### Strategies

Built in: `donchian_breakout`, `sma_cross`, `rsi_pullback`, `trend_momentum`, `momentum_rotation`. Or describe your own as a JSON rule file, no code needed:

```json
{
  "entry": [["close", ">", "sma:200"], ["rsi:2", "<", 10]],
  "exit":  [["close", ">", "sma:5"]],
  "stop_atr_mult": 3
}
```

```bash
python skills/backtest-runner/scripts/backtest.py --market IN --pit-universe 200 --rules idea.json \
  --range 10y --benchmark ^NSEI --split-date 2022-01-01 --monte-carlo 2000
```

Then `backtest-reviewer` gives a verdict: "do not rely on this result", "weak evidence", or "no red flags on these checks".

### What a backtest here can and cannot tell you

It can reliably **rule a strategy out**. It cannot promise one will keep working. Known effects on the numbers:

| Effect | Size | Direction |
|---|---|---|
| Delisted stocks (now rebuilt from NSE files under `--pit-universe`) | 3.4% a year on the rotation above, when they were missing | Flattered results; now removed |
| Dividends, rights issues in rebuilt delisted stocks | Small | Not adjusted |
| Dividends not included | About 1% a year on large caps (median of 88) | Understates; the benchmark too |
| Slippage | About 0.7% a year per extra 10 bps on a monthly rotation | Depends on real fills |
| Costs at today's rates for all years | Small | Slightly understates older years |

---

## What has been verified, and what has not

| Area | Standing |
|---|---|
| NSE transaction charges and IPFT (from 1 Mar 2026) | Primary: NSE circular NSE/FA/73061 |
| STT on equity, futures, options (from 1 Apr 2026) | Primary: NSE circular NSE/FATAX/73524 |
| NSE F&O lot sizes, expiries, ban list | Primary: read live from NSE |
| Participant-wise open interest, FII/DII cash flows, delivery data | Primary: NSE's own files |
| Company results (India) and financial statements (US) | Primary: company filings with NSE and the SEC |
| Results calendar, corporate actions | Primary: NSE |
| Results announcement times | Primary: NSE broadcast times, SEC 8-K acceptance times |
| COT positions | Primary: CFTC |
| US SEC Section 31 fee (from 4 Apr 2026) | Primary: SEC fee rate advisory |
| US FINRA TAF rates | Primary schedule; the Oct-Dec 2026 pause is **unconfirmed** |
| Indian capital gains rates and holding periods | Section 196 primary; sections 197 and 198 secondary |
| Stamp duty, SEBI fee, GST base, BSE cash charge | Secondary: broker cross-check |
| MCX transaction charges, CTT, MCX lot sizes | Secondary: MCX documents could not be fetched |
| Advance-tax schedule and capital-gains relief; F&O audit thresholds | Secondary |
| F&O turnover for tax audit | **Disputed** on option premium; both figures computed |
| Schedule FA fields | Primary (income-tax portal guide); lot aggregation disputed |
| US futures contract sizes | Unverified: the exchange blocks automated access |
| Prices for backtests, screens, sectors, commodities, macro, crypto | Unofficial (Yahoo); Indian closes cross-checked or repaired from NSE |
| Mutual fund NAV history | Secondary (mfapi.in), checked against AMFI's latest NAV |

If you can point to a primary document for anything marked secondary or unverified, please open an issue or a pull request.

---

## Data sources

| Source | Used for | Key needed |
|---|---|---|
| NSE archives and API (nseindia.com) | Bhavcopy (cash and F&O), lot sizes, index members, delivery, participant OI, FII/DII, ban list, results filings, corporate actions, event calendar | No |
| AMFI | Official daily mutual fund NAVs | No |
| mfapi.in | Mutual fund NAV history (community mirror of AMFI) | No |
| SEC (data.sec.gov) | US company financials, results filing times | No |
| SEC (www.sec.gov archives) | 13F holdings | Contact email required (see [Configuration](#configuration)) |
| CFTC | Commitments of Traders | No |
| Yahoo Finance chart endpoint | Daily prices for indices, US stocks, ETFs, futures, crypto, and history for Indian stocks | No (unofficial) |

Files are downloaded at run time and cached locally; nothing is redistributed. Each source has its own terms of use, including limits on automated access. See [NOTICE.md](NOTICE.md).

---

## Install in detail

### Claude Code (recommended)

```bash
python scripts/install_skills.py                                 # all 50 skills into ~/.claude/skills
python scripts/install_skills.py position-sizer stock-screener   # only some
python scripts/install_skills.py --target .claude/skills         # into one project folder only
python scripts/install_skills.py --list                          # what is available
python scripts/install_skills.py --uninstall                     # remove what the installer added
```

Each installed skill carries its own copy of the shared library, so the clone can be moved or deleted afterwards. To update: `git pull`, then run the installer again. The installer never overwrites a folder it did not create.

Tip: installing into a dedicated folder (for example `~/trading/.claude/skills`) keeps these skills out of your other projects; open Claude Code in that folder when you want them.

Do not copy a folder out of `skills/` by hand: on its own it cannot find the shared library.

### claude.ai (web and desktop app)

```bash
python scripts/package_skills.py        # writes dist/<skill>.zip and dist/SHA256SUMS
```

Upload a zip under Settings > Capabilities > Skills, with code execution switched on. The data-fetching skills need network access from the code-execution environment. Where that is blocked, the pure calculators (costs, sizing, options, SIP, tax from your own files) still work, and the others report that they could not reach the source.

---

## Configuration

| Setting | Purpose | Default |
|---|---|---|
| `MARKET_SKILLS_CACHE` | Where downloaded data is cached | `~/.cache/market-skills` |
| `MARKET_SKILLS_HOME` | Where the trade journal lives | `~/.market-skills` |
| `MARKET_SKILLS_SEC_USER_AGENT` | Your name and email, required by the SEC for 13F downloads | unset |
| `MARKET_SKILLS_LIVE=1` | Run the live-data tests | off |

Your brokerage plan, risk limits and loss limits are passed per request (Claude asks for them), never assumed.

---

## Using the scripts without Claude

Every skill is a command-line script that prints JSON:

```bash
python skills/position-sizer/scripts/position_sizer.py --instrument futures --account 1000000 --entry 25000 --stop 24900 --symbol NIFTY
python skills/trade-cost-calculator/scripts/trade_cost.py --market IN --segment equity_delivery --buy-price 1000 --sell-price 1010 --quantity 100
python skills/option-chain-analyzer/scripts/option_chain.py NIFTY --rate 0.065
python skills/company-fundamentals/scripts/fundamentals.py --market IN --symbol INFY
```

Run any script with `--help` for its options. The first run of a screener or backtest downloads price history and can take a few minutes.

---

## Repository layout

```
claude-quant-skills/
├── skills/                 50 skills, each with SKILL.md (instructions for Claude) and scripts/
├── marketcore/             shared, tested library (standard library only)
│   ├── rulebook/           dated, sourced charges, tax rules and contract specs (JSON)
│   ├── data/               adapters for NSE, AMFI, SEC, CFTC, Yahoo; point-in-time universes
│   ├── charges.py          trade costs          ├── backtest.py      engine and strategies
│   ├── tax_india.py        capital gains        ├── robustness.py    out-of-sample, sweep, Monte Carlo, review
│   ├── options.py          pricing and payoff   ├── fundamentals.py  filings parsing
│   └── ...                 sizing, screens, breadth, timing, pairs, journal, and more
├── tests/                  215 tests with hand-computed expected values
├── scripts/                installer, packager, rulebook document generator
└── docs/                   CODE_TOUR.md, RULEBOOK.md (generated), ROADMAP.md
```

---

## Development

```bash
python -m venv .venv
.venv/Scripts/python -m pip install "pytest>=8,<9"     # macOS/Linux: .venv/bin/python
.venv/Scripts/python -m pytest                          # offline tests
MARKET_SKILLS_LIVE=1 .venv/Scripts/python -m pytest     # also hit NSE and AMFI
python scripts/build_rulebook_doc.py                    # after editing the rulebook
```

**Changing a rate:** add a `versions` entry with its `from` date and source, close the previous entry's `to` date, add a hand-computed test, and regenerate the rulebook document. Never overwrite an old rate.

**Reading the code:** start with [docs/CODE_TOUR.md](docs/CODE_TOUR.md), a guide to the cost, backtest and tax code with worked examples to check by hand.

**Adding a skill:** put the logic in `marketcore/` with tests, add a thin script under `skills/<name>/scripts/`, and write `SKILL.md` with a description that says when to use it, how to read the output, and its limits.

---

## Known limitations

- **No live data.** Everything is end of day; unfinished sessions are excluded.
- **Some prices are unofficial.** Long price histories come from Yahoo; Indian closes are checked against NSE, older history is not.
- **Survivorship bias: delisted stocks are rebuilt from NSE files**, but only for Indian point-in-time runs. Their dividends and rights issues are not adjusted. A stock whose ISIN changed at a rename is not followed. Today's index lists and hand-picked lists remain biased.
- **Rates not from primary documents** are listed above and labelled in every output.
- **Tax scope:** resident individuals, transfers from 1 April 2025; no surcharge, loss set-off, slab tax or non-residents. Not a filing tool.
- **Indian fundamentals:** about two years (the current filing format), income statement and headline balance-sheet figures only.
- **No US results calendar** (no reliable free source), no Indian bond yields or macro releases, no MCX prices or option chains.
- **Backtests:** long only, daily bars, no dividends, no F&O strategies.

Full list and what is planned: [docs/ROADMAP.md](docs/ROADMAP.md).

---

## FAQ

**Will this make me money?**
No tool can promise that. None of the built-in strategies tested here beat simply holding the Nifty once hindsight was removed. What it does is help you avoid avoidable mistakes: wrong costs, oversized positions, untested ideas, broken rules, wrong tax.

**Does it give buy or sell recommendations?**
No. Screens produce candidates for your own research; every output says so.

**Do I need paid data or API keys?**
No. Everything uses free public sources. Only the 13F skill needs your name and email, because the SEC requires it.

**Is my data sent anywhere?**
Your trades, journal and tax files stay on your machine. The scripts only download public market data.

**Why are some numbers marked "secondary"?**
Because their official document could not be fetched and checked. They match published broker figures, but you should confirm them against your contract note.

**Does it work outside India?**
Costs, tax and much of the data are India-specific. US stocks, US futures, commodities and crypto are covered for prices, screening, options, fundamentals, positioning and backtesting.

---

## Disclaimer

**Please read before using these tools.**

- **Not a recommendation.** Nothing produced by this project is a recommendation, solicitation or offer to buy, sell or hold any security, derivative, commodity, cryptocurrency or other instrument. Screens, rankings, signals, backtests and comparisons are research aids. Any decision is yours alone.
- **Not advice.** This project does not provide investment, financial, tax, legal or accounting advice. The author is not registered or licensed as an investment adviser, research analyst, broker-dealer, commodity trading adviser or in any similar capacity with any regulator, including the Securities and Exchange Board of India (SEBI), the US Securities and Exchange Commission (SEC), the Financial Industry Regulatory Authority (FINRA), the Commodity Futures Trading Commission (CFTC), the National Futures Association (NFA), any US state securities regulator, or any regulator in any other country. Nothing here is offered as such a service, and nothing is tailored to any person's circumstances.
- **Independent project.** This is not an Anthropic product and is not affiliated with or endorsed by Anthropic. "Quant" in the name refers to the quantitative methods used (testing, pricing, statistics); it does not imply the research quality, infrastructure or track record of an institutional quantitative fund.
- **Regulators and exchanges.** References to NSE, BSE, MCX, SEBI, AMFI, the SEC, the CFTC, CME and others identify the public sources of data and rules. They do not imply any affiliation with, or endorsement by, those bodies.
- **Risk of loss.** Trading and investing involve substantial risk, including the loss of more than your initial investment when using derivatives, margin or leverage. Past performance, including backtested results, does not guarantee or predict future results. Backtests are hypothetical and have inherent limitations, set out in this document.
- **No guarantee of accuracy.** Rates, rules, contract specifications and market data change and may be wrong, incomplete, delayed or out of date. Some figures come from secondary or unofficial sources and are labelled as such. Always verify against your broker's contract notes, official exchange and regulator documents, and your own records.
- **Tax figures are estimates.** Tax outputs are computation aids, not tax returns or opinions. Have a qualified chartered accountant or tax professional review them before filing or acting on them.
- **Third-party data.** Market data is downloaded at run time from public sources that are not affiliated with this project and do not endorse it. You are responsible for complying with each source's terms of use.
- **Your responsibility.** You are solely responsible for your use of these tools, for your trading and investment decisions, and for complying with the laws and regulations that apply to you.
- **No warranty, no liability.** The software is provided "as is", without warranty of any kind, express or implied. To the fullest extent permitted by law, the author and contributors accept no liability for any loss or damage arising from its use. See [LICENSE](LICENSE) and [DISCLAIMER.md](DISCLAIMER.md).

---

## Licence

MIT. See [LICENSE](LICENSE).
