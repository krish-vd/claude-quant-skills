#!/usr/bin/env python3
"""Backtest a rule-based, long-only strategy on Indian or US stocks with real costs.

Signals use each day's close; orders fill at the next day's open. Strategies:
donchian_breakout, sma_cross, rsi_pullback, trend_momentum.
"""
import argparse
import json
import pathlib
import sys
from datetime import date, timedelta

_here = pathlib.Path(__file__).resolve()
for _candidate in (_here.parent / "_vendor", *_here.parents):
    if (_candidate / "marketcore" / "__init__.py").exists():
        sys.path.insert(0, str(_candidate))
        break
else:
    sys.exit("marketcore not found: run from the repo, or use a packaged skill")

from marketcore import costmodel, indicators, robustness, rules, rulestrategy  # noqa: E402
from marketcore.backtest import STRATEGIES, Config, run  # noqa: E402
from marketcore.data import DataUnavailable, bhavprices, pit  # noqa: E402
from marketcore.data.history import RANGES, daily_bars, load_universe  # noqa: E402


def yearly_returns(curve):
    out, start_value, year = [], curve[0][1], curve[0][0].year
    previous = curve[0][1]
    for day, value in curve[1:]:
        if day.year != year:
            out.append({"year": year, "return_pct": round((previous / start_value - 1) * 100, 2)})
            start_value, year = previous, day.year
        previous = value
    out.append({"year": year, "return_pct": round((previous / start_value - 1) * 100, 2)})
    return out


def buy_and_hold(symbol, market, range_, start, end):
    bars = daily_bars(symbol, range_, market)
    points = [(d, c) for d, c in zip(bars.dates, bars.close) if start <= d <= end]
    if len(points) < 2:
        raise DataUnavailable(f"benchmark {symbol} has no data in the test window")
    first, last = points[0][1], points[-1][1]
    years = max((points[-1][0] - points[0][0]).days, 1) / 365.25
    peak, max_dd = first, 0.0
    for _, c in points:
        peak = max(peak, c)
        max_dd = max(max_dd, 1 - c / peak)
    return {
        "symbol": symbol.upper(),
        "total_return_pct": round((last / first - 1) * 100, 2),
        "cagr_pct": round(((last / first) ** (1 / years) - 1) * 100, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "note": "price only, no dividends, no costs",
    }


def build_regime(symbol, sma_n, range_, data):
    """{date: True/False} for every trading day in ``data``: is the index above its moving average?

    Each day uses the index's latest close on or before that day, so the filter never looks ahead.
    """
    index_bars = daily_bars(symbol, range_, "US")
    average = indicators.sma(index_bars.close, sma_n)
    state, on_days = {}, 0
    calendar = sorted({d for b in data.values() for d in b.dates})
    j, current = 0, False
    for day in calendar:
        while j < len(index_bars) and index_bars.dates[j] <= day:
            current = average[j] is not None and index_bars.close[j] > average[j]
            j += 1
        state[day] = current
        on_days += current
    share = round(on_days / len(calendar) * 100, 1) if calendar else 0.0
    return state, f"Entries allowed only while {symbol.upper()} closes above its {sma_n}-day average ({share}% of days)"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--market", choices=["IN", "US"], required=True)
    p.add_argument("--symbols", help="comma-separated, e.g. RELIANCE,TCS or AAPL,MSFT")
    p.add_argument("--symbols-file", help="text file, one symbol per line")
    p.add_argument("--index", help="India: nifty50, niftynext50, nifty100, nifty200, nifty500, niftymidcap150, niftysmallcap250")
    p.add_argument("--pit-universe", type=int, metavar="N",
                   help="India: instead of today's index members, use the N most traded stocks as of each past quarter "
                        "(built from NSE bhavcopies). Reduces survivorship bias. Slow on the first run")
    p.add_argument("--no-delisted", action="store_true",
                   help="with --pit-universe: do not rebuild delisted or merged stocks from NSE bhavcopies (skips the slow first-run download, keeps the survivorship bias)")
    p.add_argument("--delisting-haircut-pct", type=float, default=0.0, metavar="PCT",
                   help="loss applied to the last traded price when a held stock is delisted or merged away (default 0; "
                        "100 = every delisting is a total loss, a bound for insolvencies)")
    p.add_argument("--strategy", choices=sorted(STRATEGIES), help="a built-in strategy (or use --rules)")
    p.add_argument("--rules", help="JSON rule file describing a custom strategy (see the strategy-idea-pipeline skill)")
    p.add_argument("--param", action="append", default=[], metavar="NAME=VALUE", help="strategy parameter; repeatable")
    p.add_argument("--range", default="5y", choices=RANGES, help="history to test (default 5y)")
    p.add_argument("--capital", type=float, default=1_000_000)
    p.add_argument("--risk-pct", type=float, default=1.0, help="percent of equity risked per trade when the strategy has a stop")
    p.add_argument("--alloc-pct", type=float, default=10.0, help="percent of equity per position when there is no stop")
    p.add_argument("--max-positions", type=int, default=10)
    p.add_argument("--max-position-pct", type=float, default=20.0)
    p.add_argument("--slippage-bps", type=float, default=5.0, help="slippage per fill in basis points (default 5)")
    p.add_argument("--brokerage", type=float, default=0.0, help="brokerage or commission per order")
    p.add_argument("--dp-charge", type=float, default=0.0, help="India: depository charge per delivery sell")
    p.add_argument("--benchmark", help="buy-and-hold comparison, e.g. ^NSEI, ^CRSLDX (Nifty 500), SPY")
    p.add_argument("--trades", action="store_true", help="include the full trade list")
    p.add_argument("--split-date", help="YYYY-MM-DD: report results before (in-sample) and from (out-of-sample) this date")
    p.add_argument("--sweep", action="append", default=[], metavar="NAME=V1,V2,...",
                   help="test every combination of these parameter values; repeatable. With --split-date the best in-sample setting is re-tested out of sample")
    p.add_argument("--regime-filter", metavar="SYMBOL",
                   help="take entries only while this index closes above its moving average, e.g. ^NSEI or SPY")
    p.add_argument("--regime-sma", type=int, default=200, help="moving-average length for --regime-filter (default 200)")
    p.add_argument("--monte-carlo", type=int, default=0, metavar="RUNS", help="resample the trade sequence this many times (e.g. 2000)")
    a = p.parse_args()
    if bool(a.strategy) == bool(a.rules):
        p.error("give exactly one of --strategy or --rules")

    try:
        params = {}
        for item in a.param:
            name, _, value = item.partition("=")
            if not _:
                p.error(f"--param must be NAME=VALUE, got {item!r}")
            params[name.strip()] = float(value)
        symbols = a.symbols.split(",") if a.symbols else None
        if a.symbols_file:
            symbols = pathlib.Path(a.symbols_file).read_text(encoding="utf-8").split()
        membership, pit_note = None, None
        if a.pit_universe:
            if a.market != "IN":
                p.error("--pit-universe is available for India only")
            years = {"1mo": 1, "3mo": 1, "6mo": 1, "1y": 1, "2y": 2, "5y": 5, "10y": 10, "max": 10}[a.range]
            start = date.today() - timedelta(days=int(years * 365.25))
            built = pit.liquidity_membership(start, date.today(), a.pit_universe)
            _, current = pit.nse_latest_turnover()
            raw_symbols = {s for members in built["membership"].values() for s in members}
            rename = pit.rename_to_current(raw_symbols, built["isin"], current)
            membership = pit.Membership(built["membership"], rename)
            symbols, a.index = sorted(membership.all_symbols()), None
        data, failed, details = load_universe(a.market, symbols, a.index, a.range)
        recovery = None
        if membership and failed and not a.no_delisted:
            print(f"Rebuilding {len(failed)} delisted or merged stocks from NSE bhavcopies "
                  "(the first run downloads about 2,600 daily files; later runs reuse them)...", file=sys.stderr, flush=True)
            recovered, recovery = bhavprices.adjusted_bars(set(failed), start, date.today(), progress=True)
            data.update(recovered)
            failed = [s for s in failed if s not in recovered]
        if not data:
            raise DataUnavailable("no price history could be loaded for any symbol")
        if membership:
            pit_note = {
                "method": f"Each quarter, the {a.pit_universe} most traded NSE company shares, ranked on bhavcopies dated before that quarter.",
                "quarters": len(membership.keys),
                "distinct_stocks_over_the_period": len(symbols),
                "with_price_history": len(data),
                "rebuilt_from_nse_bhavcopies": recovery and {
                    "stocks": len(recovered),
                    "sessions_read": recovery["sessions_read"],
                    "days_without_file": recovery["days_without_file"],
                    "per_stock": recovery["symbols"],
                },
                "missing_price_history": failed,
                "renamed_to_current_symbol": rename,
                "quarters_without_data": built["skipped_quarters"],
            }
        model = (costmodel.india_delivery(date.today(), a.brokerage, a.dp_charge) if a.market == "IN"
                 else costmodel.us_equity(date.today(), a.brokerage))
        cfg = Config(
            initial_capital=a.capital, risk_pct=a.risk_pct, alloc_pct=a.alloc_pct,
            max_positions=a.max_positions, max_position_pct=a.max_position_pct,
            buy_cost_frac=model.buy_frac, sell_cost_frac=model.sell_frac,
            fixed_cost_per_order=model.fixed_per_order, slippage_bps=a.slippage_bps,
            delisting_haircut_pct=a.delisting_haircut_pct,
        )
        regime_note = None
        if a.regime_filter:
            cfg.regime, regime_note = build_regime(a.regime_filter, a.regime_sma, a.range, data)
        split = date.fromisoformat(a.split_date) if a.split_date else None
        if a.rules:
            rule_spec = rulestrategy.load(a.rules)
            strategy = rulestrategy.build(rule_spec)
            a.strategy = f"rules:{pathlib.Path(a.rules).name}"
        else:
            strategy = STRATEGIES[a.strategy]
        shown_params = dict(params)
        if membership:
            cfg.eligible = membership
            params = {**params, "_eligible": membership}  # lets ranking strategies rank within the universe
        result = run(data, strategy, params, cfg)
        m = result.metrics
        robustness_out = {}
        if split:
            robustness_out["out_of_sample"] = robustness.out_of_sample(data, strategy, params, cfg, split)
        if a.sweep:
            grid = {}
            for item in a.sweep:
                name, sep, values = item.partition("=")
                if not sep:
                    p.error(f"--sweep must be NAME=V1,V2,..., got {item!r}")
                grid[name.strip()] = [float(v) for v in values.split(",")]
            robustness_out["parameter_sweep"] = robustness.parameter_sweep(data, strategy, grid, cfg, split, params)
        if a.monte_carlo:
            trade_returns = [t.pnl / t.equity_at_entry for t in result.trades if t.equity_at_entry > 0]
            robustness_out["monte_carlo"] = robustness.monte_carlo(trade_returns, a.monte_carlo)
        benchmark = None
        if a.benchmark:
            benchmark = buy_and_hold(a.benchmark, "US", a.range, result.equity_curve[0][0], result.equity_curve[-1][0])
    except (ValueError, OSError, DataUnavailable, rules.RuleNotCovered) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2

    cautions = [
        "Past results do not predict future results.",
        "Dividends are not included, so long holding periods are understated.",
        "Prices are from an unofficial source (Yahoo), adjusted for splits and bonuses.",
        f"Costs: {model.description}; slippage {a.slippage_bps} bps per fill.",
    ]
    if a.index:
        cautions.append(
            f"Survivorship bias: {a.index} is today's member list. Stocks that fell out of the index "
            "(often the losers) are missing, which flatters the result."
        )
        if a.strategy in ("momentum_rotation", "trend_momentum"):
            cautions.append(
                "This bias is at its worst for momentum strategies: today's index holds the past decade's biggest "
                "winners, and the strategy then 'selects' them with hindsight. Treat the full-period and in-sample "
                "figures as an upper bound and rely on a recent out-of-sample period (--split-date) instead."
            )
    if membership:
        missing = len(pit_note["missing_price_history"])
        rebuilt = pit_note["rebuilt_from_nse_bhavcopies"]
        cautions.append(
            "Point-in-time universe: stocks were chosen each quarter from what was most traded then, without hindsight."
        )
        if rebuilt:
            suspect = {s: e["suspect_jumps"] for s, e in rebuilt["per_stock"].items() if e["suspect_jumps"]}
            unadjusted = {s: e["not_adjusted"] for s, e in rebuilt["per_stock"].items() if e["not_adjusted"]}
            cautions.append(
                f"{rebuilt['stocks']} delisted or merged stocks were rebuilt from official NSE bhavcopies and adjusted for splits "
                "and bonuses. Dividends, rights issues and demergers are not adjusted. "
                f"{len(unadjusted)} of them had a demerger, rights issue or unparsed action (see rebuilt_from_nse_bhavcopies.per_stock) "
                f"and {len(suspect)} still show a one-day move above 35% that may be an unadjusted event."
            )
            cautions.append(
                f"A held stock that stops trading is closed at its last traded price less a {a.delisting_haircut_pct:g}% haircut. "
                "For a merger that is about right; for an insolvency the true outcome can be a total loss, so check the result "
                "with --delisting-haircut-pct 100 as a bound."
            )
        if missing:
            cautions.append(
                f"{missing} of {pit_note['distinct_stocks_over_the_period']} historical members still have no price history "
                f"({', '.join(pit_note['missing_price_history'][:8])}{'...' if missing > 8 else ''}), so some survivorship bias remains."
            )
        elif rebuilt:
            cautions.append("Every historical member has a price history; survivorship bias from missing delisted stocks is removed.")
        failed = []
    params = shown_params
    if (m.get("closed_trades") or 0) < 30:
        cautions.append(f"Only {m.get('closed_trades', 0)} closed trades: too few to trust the statistics.")
    if params:
        cautions.append("Parameters were chosen by hand. If you tried several and kept the best, the result is optimistic; confirm on a period you did not tune on.")
    repair = details.get("__repair__", {})
    if repair.get("repaired"):
        cautions.append(f"{len(repair['repaired'])} recent gap(s) in the price source were filled from the official NSE bhavcopy.")
    if repair.get("unrepaired"):
        cautions.append(f"Recent gaps that could not be filled: {', '.join(repair['unrepaired'])}")
    if failed:
        cautions.append(f"No data for: {', '.join(failed)}")

    out = {
        "strategy": a.strategy,
        "parameters": params or "defaults",
        "market": a.market,
        "symbols_tested": len(data),
        "metrics": m,
        "yearly_returns": yearly_returns(result.equity_curve),
        "benchmark_buy_and_hold": benchmark,
        "regime_filter": regime_note,
        "point_in_time_universe": pit_note,
        **robustness_out,
        "exit_reasons": {r: sum(1 for t in result.trades if t.exit_reason == r) for r in sorted({t.exit_reason for t in result.trades})},
        "open_positions": [
            {"symbol": t.symbol, "entry_date": t.entry_date.isoformat(), "entry_price": round(t.entry_price, 2), "shares": t.shares}
            for t in result.open_positions
        ],
        "cautions": cautions,
    }
    if a.trades:
        out["trades"] = [
            {"symbol": t.symbol, "entry_date": t.entry_date.isoformat(), "entry_price": round(t.entry_price, 2),
             "exit_date": t.exit_date.isoformat(), "exit_price": round(t.exit_price, 2), "shares": t.shares,
             "pnl": round(t.pnl, 2), "r_multiple": None if t.r_multiple is None else round(t.r_multiple, 2),
             "exit_reason": t.exit_reason, "holding_days": t.holding_days}
            for t in result.trades
        ]
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
