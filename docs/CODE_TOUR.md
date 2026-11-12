# Code tour

A guide to the three files that matter most for correctness. Read this, then the
files, and you will be able to explain how the numbers are produced and where
they could be wrong.

Everything runs on `Decimal` for money in the cost and tax code, and on floats
for the backtester (prices and statistics, not ledger amounts).

---

## 1. `marketcore/charges.py`: what a trade costs

**The idea.** A trade's costs are a list of levies, each a percentage of the
trade value. No rate lives in the code. `india_leg()` asks the rulebook
(`marketcore/rulebook/in_charges.json`) for every rate in force **on the trade
date** and multiplies.

**How `india_leg()` works, top to bottom**

1. Validates the segment (`equity_delivery`, `equity_intraday`, `futures`, ...) and side.
2. `turnover = price x quantity`. For options the price is the premium.
3. Adds brokerage if the caller supplied a plan (flat, percentage, capped).
4. `rules.rates_for(...)` returns every rate for that segment and exchange on that
   date. For each one it skips levies that apply to the other side (for example
   STT on futures is sell-side only), then `amount = turnover x rate`.
5. GST is **18% of brokerage + exchange transaction charge + IPFT + SEBI fee**. It
   is not charged on STT, stamp duty or CTT. This is the base the code builds in
   `gst_base`.
6. If no exchange transaction charge was found, it raises instead of guessing.
7. DP charge is added only for delivery sells, and only if the caller passes it.

**Why the date matters.** STT on futures was 0.02% until 31 Mar 2026 and 0.05%
after; NSE's transaction charge changed on 1 Mar 2026. The rulebook keeps both
versions with date ranges, and `tests/test_charges.py` checks each side of
those boundaries.

**Where it could be wrong**

- Rates marked `secondary` or `unverified` in the rulebook (MCX, stamp duty, SEBI
  fee, BSE). The output repeats this in `warnings`.
- Real contract notes round each levy (STT to the nearest rupee, others to paise).
  This code keeps exact amounts, so expect differences of about a rupee per levy.
- The DP charge and brokerage are whatever the user supplies.

**Try it:** `python skills/trade-cost-calculator/scripts/trade_cost.py --market IN
--segment options --side sell --price 100 --quantity 650`, then recompute the STT
by hand: 100 x 650 x 0.0015 = 97.50.

---

## 2. `marketcore/backtest.py`: how the backtester avoids cheating

**The loop.** `run()` walks every trading day in order. On each day it does five
things, **in this order**, and the order is the whole point:

1. **Fill yesterday's exit decisions at today's open.**
2. **Check stops** on positions carried into today. If the day opens below the
   stop, the fill is the *open* (a gap loses more than planned); otherwise if the
   low touched the stop, the fill is the stop.
3. **Fill yesterday's entry decisions at today's open**, best-scoring first, within
   position limits. Size is risk-based when the strategy gave a stop distance
   (`risk_pct x equity / stop distance`), otherwise a fixed share of equity. It is
   capped by `max_position_pct` and by available cash.
4. **Mark every position to today's close** and record equity.
5. **Decide tomorrow's orders from today's close.**

Because decisions are made in step 5 and filled in steps 1 and 3 of the next day,
a trade can never use a price the signal had already seen. `tests/test_indicators_backtest.py`
has a test that adds future bars and checks earlier trades do not change.

**Costs.** Every fill pays slippage (`price x (1 +/- bps)`), proportional costs and
a fixed per-order cost. Costs come from the same rulebook as the cost calculator,
through `costmodel.py`, using the rates in force **today** for all years.

**Strategies** return a `Signals` object per symbol: entry flags, exit flags, stop
distance and a score, each computed only from data up to that bar. Indicators in
`indicators.py` return `None` until they have enough history.

**Where it could be wrong, and what is deliberately simplified**

- Long only, daily bars, no dividends, no intraday fills, no liquidity limits.
- Costs use today's rates for old trades.
- Prices are unofficial and split-adjusted. Recent Indian bars are repaired from
  the NSE bhavcopy (`data/history.py`).
- Survivorship bias depends on the universe passed in. `data/pit.py` builds a
  point-in-time universe, but delisted stocks have no price history and drop out.

**Try it:** `python -m pytest tests/test_indicators_backtest.py -v`. Then read
`test_entry_fills_at_next_open_not_signal_close` and
`test_gap_through_stop_fills_at_the_open`: each is a hand-worked example.

---

## 3. `marketcore/tax_india.py`: capital gains

**Order of work in `realised_gains()`**

1. Sort trades by date, buys before sells on the same day.
2. Keep a queue of open lots per symbol (**FIFO**: shares leave a demat account
   oldest first).
3. Each sell consumes lots from the front of the queue. If it asks for more than
   was bought, it stops with an error rather than inventing cost.
4. For each matched piece: sale value, apportioned selling expenses, and cost.
5. **Grandfathering** (shares bought before 1 Feb 2018): cost is the higher of
   actual cost and the lower of (31 Jan 2018 fair market value, sale value). If
   no value was supplied it uses actual cost and warns that the gain may be overstated.
6. **Term:** long-term means held for *more than* the period (12 months for listed
   equity, 24 for foreign shares). `is_long_term()` implements "more than": a
   share bought 1 Jan 2025 and sold 1 Jan 2026 is short-term; 2 Jan 2026 is long-term.

`summarise()` then groups by financial year, asset class and term, applies the
rate (20% short-term and 12.5% long-term on listed equity), the Rs 1.25 lakh
exemption for long-term listed equity, and 4% cess.

**Where it could be wrong, and what is not handled**

- Rates and section numbers come from `rulebook/in_tax.json`: section 196 was read
  from the tax department's site; sections 197 and 198 from secondary summaries.
- **Not handled:** surcharge, set-off of losses between buckets, carried-forward
  losses, the basic-exemption shortfall adjustment, corporate actions inside this
  file (use `corporate-action-adjuster` first), intraday and F&O (business income).
- Foreign shares must be supplied in rupees. The conversion rate is not automated.
- Sales before 1 April 2025 are consumed (for FIFO) but not reported.

**Try it:** build a two-line trade file (buy 100 at 1,000 on 2024-01-10, sell 100
at 3,000 on 2025-06-10), run `skills/india-capital-gains/scripts/capital_gains.py`,
and check: gain 2,00,000; taxable 75,000 after the exemption; tax 9,375; with
cess 9,750.

---

## Reading order

1. `marketcore/rules.py`: how a dated rate is looked up (short).
2. `marketcore/charges.py`, then `tests/test_charges.py`.
3. `marketcore/tax_india.py`, then `tests/test_tax_india.py`.
4. `marketcore/backtest.py`, then `tests/test_indicators_backtest.py`.
5. `marketcore/robustness.py` and `marketcore/data/pit.py` for the testing and
   universe logic around the engine.

Every test states its expected value with the working in a comment. If one
looks wrong to you, that is exactly the kind of review this project needs: open
an issue.
