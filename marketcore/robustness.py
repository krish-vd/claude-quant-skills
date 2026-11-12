"""Checks that separate a robust strategy from a lucky one.

* ``out_of_sample``: tune on the first part of history, judge on the rest.
* ``parameter_sweep``: run a grid; a result that only works at one setting is a spike, not an edge.
* ``monte_carlo``: reshuffle the trade outcomes to see the range of drawdowns the same trades could give.
"""
from __future__ import annotations

import itertools
import random
from dataclasses import replace
from datetime import date
from typing import Optional

from .backtest import Bars, Config, Strategy, bars_before, run, window_metrics


def out_of_sample(data: dict[str, Bars], strategy: Strategy, params: dict, config: Config, split: date) -> dict:
    """Run once on history before ``split`` and once taking entries only from ``split`` on.

    The second run still sees earlier bars, because indicators need warm-up, but
    opens no position before the split.
    """
    in_data = {s: bars_before(b, split) for s, b in data.items()}
    in_data = {s: b for s, b in in_data.items() if len(b) > 1}
    in_result = run(in_data, strategy, params, config)
    out_result = run(data, strategy, params, replace(config, entries_from=split))
    out_curve = [(d, v) for d, v in out_result.equity_curve if d >= split]
    return {
        "split_date": split.isoformat(),
        "in_sample": in_result.metrics,
        "out_of_sample": window_metrics(out_curve, out_result.trades),
    }


def parameter_sweep(
    data: dict[str, Bars],
    strategy: Strategy,
    grid: dict[str, list[float]],
    config: Config,
    split: Optional[date] = None,
    base_params: Optional[dict] = None,
    rank_by: str = "cagr_pct",
    max_combinations: int = 200,
) -> dict:
    """Run every combination in ``grid``. With ``split``, rank on in-sample data and
    report the best combination's out-of-sample result beside it."""
    names = sorted(grid)
    combos = list(itertools.product(*(grid[n] for n in names)))
    if len(combos) > max_combinations:
        raise ValueError(f"{len(combos)} combinations exceeds the limit of {max_combinations}; narrow the grid")
    train = data
    if split:
        train = {s: bars_before(b, split) for s, b in data.items()}
        train = {s: b for s, b in train.items() if len(b) > 1}
    rows = []
    for combo in combos:
        params = {**(base_params or {}), **dict(zip(names, combo))}
        m = run(train, strategy, params, config).metrics
        rows.append(
            {
                "params": dict(zip(names, combo)),
                "cagr_pct": m.get("cagr_pct"),
                "max_drawdown_pct": m.get("max_drawdown_pct"),
                "sharpe": m.get("sharpe"),
                "profit_factor": m.get("profit_factor"),
                "closed_trades": m.get("closed_trades"),
            }
        )
    rows.sort(key=lambda r: (r[rank_by] is None, -(r[rank_by] or 0)))
    values = [r["cagr_pct"] for r in rows if r["cagr_pct"] is not None]
    profitable = sum(1 for v in values if v > 0)
    out = {
        "ranked_by": rank_by,
        "combinations": len(rows),
        "profitable_combinations": profitable,
        "profitable_share_pct": round(profitable / len(values) * 100, 1) if values else None,
        "cagr_best_pct": max(values) if values else None,
        "cagr_median_pct": sorted(values)[len(values) // 2] if values else None,
        "cagr_worst_pct": min(values) if values else None,
        "results": rows,
    }
    if split and rows:
        best = {**(base_params or {}), **rows[0]["params"]}
        oos = out_of_sample(data, strategy, best, config, split)
        out["best_in_sample_params"] = rows[0]["params"]
        out["best_out_of_sample"] = oos["out_of_sample"]
        out["split_date"] = split.isoformat()
    return out


def monte_carlo(trade_returns: list[float], runs: int = 2000, seed: int = 12345) -> dict:
    """Resample per-trade returns (trade P&L as a fraction of equity at entry) with replacement.

    Each run draws as many trades as the backtest had and compounds them. The
    spread of outcomes shows how much of the result was the order the trades
    happened to come in. Deterministic for a given seed.
    """
    n = len(trade_returns)
    if n < 2:
        return {}
    rng = random.Random(seed)
    finals, drawdowns = [], []
    for _ in range(runs):
        equity, peak, max_dd = 1.0, 1.0, 0.0
        for _ in range(n):
            equity *= 1.0 + trade_returns[rng.randrange(n)]
            if equity <= 0:
                equity, max_dd = 0.0, 1.0
                break
            peak = max(peak, equity)
            max_dd = max(max_dd, 1 - equity / peak)
        finals.append(equity - 1.0)
        drawdowns.append(max_dd)
    finals.sort()
    drawdowns.sort()

    def pct(values: list[float], q: float) -> float:
        return round(values[min(len(values) - 1, int(q * len(values)))] * 100, 2)

    return {
        "runs": runs,
        "trades_per_run": n,
        "total_return_pct": {"p5": pct(finals, 0.05), "p50": pct(finals, 0.50), "p95": pct(finals, 0.95)},
        "max_drawdown_pct": {"p50": pct(drawdowns, 0.50), "p95": pct(drawdowns, 0.95), "p99": pct(drawdowns, 0.99)},
        "probability_of_loss_pct": round(sum(1 for f in finals if f < 0) / runs * 100, 1),
        "note": "Trades are resampled independently; real trades cluster, so real drawdowns can be worse.",
    }


MOMENTUM_STRATEGIES = ("momentum_rotation", "trend_momentum")


def review_report(report: dict) -> dict:
    """Audit a backtest report (the JSON printed by the backtest runner) for the usual
    ways a backtest misleads. Findings are ``high``, ``medium`` or ``info``.

    Verdict: any high finding -> "do not rely on this result"; two or more medium
    findings -> "weak evidence"; otherwise "no red flags on these checks" (which is
    not the same as proof that the strategy works).
    """
    findings: list[dict] = []

    def add(severity: str, check: str, detail: str) -> None:
        findings.append({"severity": severity, "check": check, "detail": detail})

    m = report.get("metrics") or {}
    trades, cagr, dd = m.get("closed_trades") or 0, m.get("cagr_pct"), m.get("max_drawdown_pct")
    if trades < 30:
        add("high", "sample_size", f"Only {trades} closed trades. Below about 30 the statistics are noise.")
    elif trades < 100:
        add("medium", "sample_size", f"{trades} closed trades: enough to look at, thin for conclusions.")
    if (m.get("years") or 0) < 5:
        add("medium", "history_length", f"{m.get('years')} years of history may cover only one kind of market.")

    oos = report.get("out_of_sample")
    if not oos:
        add("medium", "out_of_sample", "No out-of-sample test. Re-run with a split date and judge the later period.")
    else:
        inside, outside = (oos.get("in_sample") or {}).get("cagr_pct"), (oos.get("out_of_sample") or {}).get("cagr_pct")
        if inside is not None and outside is not None and inside > 0:
            if outside <= 0:
                add("high", "out_of_sample", f"Made {inside}% a year in sample and {outside}% out of sample: the edge did not survive.")
            elif outside < 0.5 * inside:
                add("high", "out_of_sample", f"Return fell from {inside}% a year in sample to {outside}% out of sample, less than half.")
            else:
                add("info", "out_of_sample", f"Out-of-sample return {outside}% a year against {inside}% in sample.")

    bench = report.get("benchmark_buy_and_hold")
    if not bench:
        add("medium", "benchmark", "No buy-and-hold benchmark to compare with.")
    elif cagr is not None and bench.get("cagr_pct") is not None:
        worse_return = cagr <= bench["cagr_pct"]
        worse_drawdown = dd is not None and bench.get("max_drawdown_pct") is not None and dd >= bench["max_drawdown_pct"]
        if worse_return and worse_drawdown:
            add("high", "benchmark", f"Returned {cagr}% a year with a {dd}% drawdown; buy and hold returned "
                                     f"{bench['cagr_pct']}% with {bench['max_drawdown_pct']}%. Worse on both.")
        elif worse_return:
            add("medium", "benchmark", f"Returned {cagr}% a year against {bench['cagr_pct']}% for buy and hold "
                                       f"(drawdown {dd}% against {bench['max_drawdown_pct']}%).")
        if oos and bench.get("cagr_pct") is not None:
            outside = (oos.get("out_of_sample") or {}).get("cagr_pct")
            if outside is not None and not worse_return and outside <= bench["cagr_pct"]:
                add("medium", "benchmark", f"The out-of-sample return ({outside}% a year) does not beat the full-period "
                                           f"benchmark ({bench['cagr_pct']}%).")

    cautions = " ".join(report.get("cautions") or [])
    pit = report.get("point_in_time_universe")
    if pit:
        missing = len(pit.get("missing_price_history") or [])
        add("info", "survivorship_bias", f"Point-in-time universe used; {missing} historical member(s) have no price history, "
                                         "so a little bias remains.")
    elif "Survivorship bias" in cautions:
        severity = "high" if report.get("strategy") in MOMENTUM_STRATEGIES else "medium"
        add(severity, "survivorship_bias", "Tested on today's index members, which already excludes the stocks that fell out. "
                                           "Re-run with a point-in-time universe.")
    else:
        add("medium", "survivorship_bias", "A hand-picked symbol list: it was chosen knowing which companies survived and grew.")

    pf, win = m.get("profit_factor"), m.get("win_rate_pct")
    if trades >= 30 and ((pf is not None and pf > 4) or (win is not None and win > 80)):
        add("medium", "too_good", f"Profit factor {pf} and win rate {win}% are unusually high. Check the data and rules for errors.")
    if dd is not None:
        if dd > 60:
            add("high", "drawdown", f"Maximum drawdown of {dd}%: few people keep trading a strategy through that.")
        elif dd > 40:
            add("medium", "drawdown", f"Maximum drawdown of {dd}% is hard to sit through.")
    mc = (report.get("monte_carlo") or {}).get("max_drawdown_pct") or {}
    if mc.get("p95") is not None and dd is not None and mc["p95"] > dd:
        add("info", "drawdown", f"Reshuffling the trades gives a {mc['p95']}% drawdown in 1 run out of 20, worse than the {dd}% seen.")

    sweep = report.get("parameter_sweep")
    if sweep:
        share, best, median = sweep.get("profitable_share_pct"), sweep.get("cagr_best_pct"), sweep.get("cagr_median_pct")
        if share is not None and share < 60:
            add("medium", "parameter_sensitivity", f"Only {share}% of the parameter combinations made money.")
        if best is not None and median is not None and median > 0 and best > 2 * median:
            add("medium", "parameter_sensitivity", f"The best setting made {best}% a year but the median made {median}%: "
                                                   "the result depends on picking the right parameters.")
    elif report.get("parameters") not in (None, "defaults", {}):
        add("medium", "parameter_sensitivity", "Parameters were set by hand and no sweep was run, so it is unknown whether nearby settings work.")

    high = sum(1 for f in findings if f["severity"] == "high")
    medium = sum(1 for f in findings if f["severity"] == "medium")
    verdict = "do not rely on this result" if high else "weak evidence" if medium >= 2 else "no red flags on these checks"
    order = {"high": 0, "medium": 1, "info": 2}
    findings.sort(key=lambda f: order[f["severity"]])
    return {"verdict": verdict, "high": high, "medium": medium, "findings": findings}
