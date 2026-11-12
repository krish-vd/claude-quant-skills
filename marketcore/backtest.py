"""Daily-bar, long-only portfolio backtester.

Rules that keep it honest:

* A signal is computed from the close of day ``t`` and filled at the OPEN of the
  symbol's next bar. Nothing is ever filled at a price the signal already saw.
* A stop is checked against each day's range. If the day opens below the stop,
  the fill is the open (a gap loses more than planned), not the stop price.
* Every fill pays costs and slippage.
* Positions still open at the end are valued at the last close and reported
  separately; trade statistics cover closed trades only.

Not modelled: dividends (returns of long holds are understated), shorting,
intraday entries, liquidity and impact, circuit limits, and survivorship (the
universe you pass in is the universe that survived to today).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from typing import Callable, Optional

from . import indicators as ind


@dataclass
class Bars:
    symbol: str
    dates: list[date]
    open: list[float]
    high: list[float]
    low: list[float]
    close: list[float]
    volume: list[float]

    def __len__(self) -> int:
        return len(self.dates)

    def slice(self, end: int) -> "Bars":
        return Bars(self.symbol, self.dates[:end], self.open[:end], self.high[:end],
                    self.low[:end], self.close[:end], self.volume[:end])


@dataclass
class Signals:
    """Per-bar decisions, all computed from data up to that bar's close."""

    entry: list[bool]
    exit: list[bool]
    stop_distance: list[Optional[float]]  # distance below the fill price for the initial stop
    score: list[float]  # higher is preferred when signals compete for slots


Strategy = Callable[[Bars, dict], Signals]


def _ok(*values) -> bool:
    return all(v is not None for v in values)


def donchian_breakout(bars: Bars, p: dict) -> Signals:
    """Enter when the close exceeds the highest high of the previous ``entry_n`` days;
    exit when it falls below the lowest low of the previous ``exit_n`` days.
    Initial stop: ``atr_mult`` x ATR(``atr_n``) below the fill."""
    entry_n, exit_n = int(p.get("entry_n", 55)), int(p.get("exit_n", 20))
    atr_n, atr_mult = int(p.get("atr_n", 20)), float(p.get("atr_mult", 2.0))
    hi, lo = ind.highest(bars.high, entry_n), ind.lowest(bars.low, exit_n)
    a = ind.atr(bars.high, bars.low, bars.close, atr_n)
    r = ind.roc(bars.close, entry_n)
    n = len(bars)
    entry, exit_, stop, score = [False] * n, [False] * n, [None] * n, [0.0] * n
    for i in range(1, n):
        if _ok(hi[i - 1], a[i]) and bars.close[i] > hi[i - 1]:
            entry[i], stop[i] = True, atr_mult * a[i]
            score[i] = r[i] or 0.0
        if _ok(lo[i - 1]) and bars.close[i] < lo[i - 1]:
            exit_[i] = True
    return Signals(entry, exit_, stop, score)


def sma_cross(bars: Bars, p: dict) -> Signals:
    """Enter when the fast SMA crosses above the slow SMA; exit on the cross back.
    Optional initial stop of ``atr_mult`` x ATR (0 disables it)."""
    fast_n, slow_n = int(p.get("fast_n", 50)), int(p.get("slow_n", 200))
    atr_n, atr_mult = int(p.get("atr_n", 20)), float(p.get("atr_mult", 0))
    fast, slow = ind.sma(bars.close, fast_n), ind.sma(bars.close, slow_n)
    a = ind.atr(bars.high, bars.low, bars.close, atr_n)
    n = len(bars)
    entry, exit_, stop, score = [False] * n, [False] * n, [None] * n, [0.0] * n
    for i in range(1, n):
        if not _ok(fast[i], slow[i], fast[i - 1], slow[i - 1]):
            continue
        if fast[i] > slow[i] and fast[i - 1] <= slow[i - 1]:
            entry[i] = True
            if atr_mult > 0 and a[i] is not None:
                stop[i] = atr_mult * a[i]
            score[i] = fast[i] / slow[i] - 1.0
        if fast[i] < slow[i] and fast[i - 1] >= slow[i - 1]:
            exit_[i] = True
    return Signals(entry, exit_, stop, score)


def rsi_pullback(bars: Bars, p: dict) -> Signals:
    """Buy a short-term dip inside an uptrend: close above SMA(``trend_n``) and
    RSI(``rsi_n``) below ``rsi_below``. Exit when the close is above SMA(``exit_n``)."""
    trend_n, rsi_n = int(p.get("trend_n", 200)), int(p.get("rsi_n", 2))
    rsi_below, exit_n = float(p.get("rsi_below", 10)), int(p.get("exit_n", 5))
    atr_n, atr_mult = int(p.get("atr_n", 20)), float(p.get("atr_mult", 0))
    trend, r = ind.sma(bars.close, trend_n), ind.rsi(bars.close, rsi_n)
    out_ma = ind.sma(bars.close, exit_n)
    a = ind.atr(bars.high, bars.low, bars.close, atr_n)
    n = len(bars)
    entry, exit_, stop, score = [False] * n, [False] * n, [None] * n, [0.0] * n
    for i in range(n):
        if _ok(trend[i], r[i]) and bars.close[i] > trend[i] and r[i] < rsi_below:
            entry[i] = True
            if atr_mult > 0 and a[i] is not None:
                stop[i] = atr_mult * a[i]
            score[i] = -r[i]  # the deeper the dip, the higher the priority
        if _ok(out_ma[i]) and bars.close[i] > out_ma[i]:
            exit_[i] = True
    return Signals(entry, exit_, stop, score)


def trend_momentum(bars: Bars, p: dict) -> Signals:
    """Hold strong uptrends: enter when close > SMA50 > SMA200 and the close is
    within ``near_high_pct`` percent of its ``high_n``-day high; exit on a close below SMA50."""
    high_n, near = int(p.get("high_n", 252)), float(p.get("near_high_pct", 10))
    atr_n, atr_mult = int(p.get("atr_n", 20)), float(p.get("atr_mult", 3.0))
    s50, s200 = ind.sma(bars.close, 50), ind.sma(bars.close, 200)
    hi = ind.highest(bars.high, high_n)
    a = ind.atr(bars.high, bars.low, bars.close, atr_n)
    r = ind.roc(bars.close, 126)
    n = len(bars)
    entry, exit_, stop, score = [False] * n, [False] * n, [None] * n, [0.0] * n
    for i in range(n):
        if _ok(s50[i], s200[i], hi[i], a[i]):
            c = bars.close[i]
            if c > s50[i] > s200[i] and c >= hi[i] * (1 - near / 100):
                entry[i], stop[i] = True, (atr_mult * a[i] if atr_mult > 0 else None)
                score[i] = r[i] or 0.0
        if _ok(s50[i]) and bars.close[i] < s50[i]:
            exit_[i] = True
    return Signals(entry, exit_, stop, score)


def momentum_rotation(data: dict[str, Bars], p: dict) -> dict[str, Signals]:
    """Hold the strongest stocks and rotate on a schedule.

    Every ``rebalance_days`` sessions, rank all symbols by their return from
    ``lookback`` sessions ago to ``skip`` sessions ago (skipping the most recent
    weeks avoids short-term reversal). Enter symbols ranked in the top ``top_n``;
    exit holdings that have dropped below rank ``hold_n``. With ``trend_n`` > 0 a
    symbol must also close above its own SMA(``trend_n``) to be bought, and is
    sold if it closes below it on a rebalance day.

    Ranks use only closes up to the rebalance day; orders fill at the next open.
    Set --alloc-pct to about 100 / top_n and --max-positions to top_n.
    """
    lookback, skip = int(p.get("lookback", 126)), int(p.get("skip", 21))
    top_n, rebalance = int(p.get("top_n", 10)), int(p.get("rebalance_days", 21))
    hold_n, trend_n = int(p.get("hold_n", 2 * top_n)), int(p.get("trend_n", 200))
    if skip >= lookback:
        raise ValueError("skip must be smaller than lookback")
    calendar = sorted({d for b in data.values() for d in b.dates})
    position = {s: {d: i for i, d in enumerate(b.dates)} for s, b in data.items()}
    trend = {s: (ind.sma(b.close, trend_n) if trend_n > 0 else None) for s, b in data.items()}
    out = {s: Signals([False] * len(b), [False] * len(b), [None] * len(b), [0.0] * len(b)) for s, b in data.items()}

    eligible_fn = p.get("_eligible")  # optional point-in-time universe: callable(day) -> set of symbols
    for day in calendar[lookback::rebalance]:
        scores: dict[str, float] = {}
        below_trend: set[str] = set()
        allowed = eligible_fn(day) if eligible_fn else None
        for s, b in data.items():
            i = position[s].get(day)
            if i is None:
                continue
            if eligible_fn and (allowed is None or s not in allowed):
                out[s].exit[i] = True  # no longer in the universe: sell if held, never buy
                continue
            if i < lookback:
                continue
            base = b.close[i - lookback]
            if base <= 0:
                continue
            if trend[s] is not None and (trend[s][i] is None or b.close[i] <= trend[s][i]):
                below_trend.add(s)
            scores[s] = b.close[i - skip] / base - 1.0
        ranked = sorted(scores, key=lambda s: -scores[s])
        rank = {s: n + 1 for n, s in enumerate(ranked)}
        for s in ranked:
            i = position[s][day]
            if s in below_trend or rank[s] > hold_n:
                out[s].exit[i] = True
            elif rank[s] <= top_n:
                out[s].entry[i] = True
                out[s].score[i] = scores[s]
    return out


momentum_rotation.cross_sectional = True

STRATEGIES: dict[str, Strategy] = {
    "donchian_breakout": donchian_breakout,
    "sma_cross": sma_cross,
    "rsi_pullback": rsi_pullback,
    "trend_momentum": trend_momentum,
    "momentum_rotation": momentum_rotation,
}


@dataclass
class Config:
    initial_capital: float = 1_000_000.0
    risk_pct: float = 1.0  # percent of equity risked per trade when the strategy sets a stop
    alloc_pct: float = 10.0  # percent of equity per position when there is no stop
    max_positions: int = 10
    max_position_pct: float = 20.0  # cap on any one position's value
    buy_cost_frac: float = 0.0  # proportional cost on the buy turnover
    sell_cost_frac: float = 0.0
    fixed_cost_per_order: float = 0.0
    slippage_bps: float = 5.0  # paid on every fill, against you
    entries_from: Optional[date] = None  # ignore entry signals before this date (out-of-sample runs)
    regime: Optional[dict] = None  # {date: bool}; entry signals count only on days marked True
    eligible: Optional[Callable] = None  # callable(day) -> set of symbols that may be bought that day


@dataclass
class Trade:
    symbol: str
    entry_date: date
    entry_price: float
    shares: int
    stop: Optional[float]
    risk_amount: Optional[float]
    equity_at_entry: float = 0.0
    exit_date: Optional[date] = None
    exit_price: Optional[float] = None
    exit_reason: str = ""
    costs: float = 0.0
    pnl: float = 0.0
    r_multiple: Optional[float] = None

    @property
    def holding_days(self) -> int:
        return (self.exit_date - self.entry_date).days if self.exit_date else 0


@dataclass
class Result:
    config: Config
    equity_curve: list[tuple[date, float]]
    trades: list[Trade]
    open_positions: list[Trade]
    skipped_entries: int
    metrics: dict = field(default_factory=dict)


def run(data: dict[str, Bars], strategy: Strategy, params: Optional[dict] = None, config: Optional[Config] = None) -> Result:
    """Run ``strategy`` over every symbol in ``data`` with one shared pool of cash."""
    cfg = config or Config()
    params = params or {}
    if getattr(strategy, "cross_sectional", False):
        signals = strategy(data, params)  # ranks symbols against each other
    else:
        signals = {s: strategy(b, params) for s, b in data.items()}
    index = {s: {d: i for i, d in enumerate(b.dates)} for s, b in data.items()}
    calendar = sorted({d for b in data.values() for d in b.dates})
    slip = cfg.slippage_bps / 10_000.0

    cash = cfg.initial_capital
    positions: dict[str, Trade] = {}
    last_close: dict[str, float] = {}
    pending_entry: dict[str, tuple[Optional[float], float]] = {}  # symbol -> (stop_distance, score)
    pending_exit: set[str] = set()
    closed: list[Trade] = []
    curve: list[tuple[date, float]] = []
    skipped = 0
    days_in_market = 0

    def equity() -> float:
        return cash + sum(t.shares * last_close.get(s, t.entry_price) for s, t in positions.items())

    def close_position(symbol: str, day: date, raw_price: float, reason: str) -> None:
        nonlocal cash
        trade = positions.pop(symbol)
        price = raw_price * (1 - slip)
        proceeds = trade.shares * price
        cost = proceeds * cfg.sell_cost_frac + cfg.fixed_cost_per_order
        cash += proceeds - cost
        trade.exit_date, trade.exit_price, trade.exit_reason = day, price, reason
        trade.costs += cost
        trade.pnl = (price - trade.entry_price) * trade.shares - trade.costs
        if trade.risk_amount:
            trade.r_multiple = trade.pnl / trade.risk_amount
        closed.append(trade)

    for day in calendar:
        today = [s for s in data if day in index[s]]

        # 1. Fill exits decided at the previous close, at today's open.
        for s in today:
            if s in pending_exit and s in positions:
                close_position(s, day, data[s].open[index[s][day]], "signal")
            pending_exit.discard(s)

        # 2. Stops on positions carried into today.
        for s in today:
            if s in positions and positions[s].stop is not None:
                i = index[s][day]
                stop = positions[s].stop
                if data[s].open[i] <= stop:
                    close_position(s, day, data[s].open[i], "stop_gap")
                elif data[s].low[i] <= stop:
                    close_position(s, day, stop, "stop")

        # 3. Fill entries decided at the previous close, best score first.
        for s in sorted((s for s in today if s in pending_entry), key=lambda x: -pending_entry[x][1]):
            stop_distance, _ = pending_entry.pop(s)
            if s in positions:
                continue
            if len(positions) >= cfg.max_positions:
                skipped += 1
                continue
            i = index[s][day]
            price = data[s].open[i] * (1 + slip)
            eq = equity()
            if stop_distance and stop_distance > 0:
                shares = math.floor(eq * cfg.risk_pct / 100 / stop_distance)
            else:
                shares = math.floor(eq * cfg.alloc_pct / 100 / price)
            shares = min(shares, math.floor(eq * cfg.max_position_pct / 100 / price))
            affordable = math.floor((cash - cfg.fixed_cost_per_order) / (price * (1 + cfg.buy_cost_frac)))
            shares = min(shares, affordable)
            if shares < 1:
                skipped += 1
                continue
            cost = shares * price * cfg.buy_cost_frac + cfg.fixed_cost_per_order
            cash -= shares * price + cost
            stop_price = price - stop_distance if stop_distance and stop_distance > 0 else None
            positions[s] = Trade(s, day, price, shares, stop_price,
                                 stop_distance * shares if stop_price is not None else None,
                                 equity_at_entry=eq, costs=cost)
            # The stop is live for the rest of the entry day.
            if stop_price is not None and data[s].low[i] <= stop_price:
                close_position(s, day, stop_price, "stop")

        # 4. Mark to the close and record equity.
        for s in today:
            last_close[s] = data[s].close[index[s][day]]
        if positions:
            days_in_market += 1
        curve.append((day, equity()))

        # 5. Decide at the close; these fill at each symbol's next bar.
        allowed = (cfg.eligible(day) or frozenset()) if cfg.eligible else None
        for s in today:
            i = index[s][day]
            sig = signals[s]
            if s in positions:
                if sig.exit[i]:
                    pending_exit.add(s)
            elif (
                sig.entry[i]
                and not sig.exit[i]
                and (cfg.entries_from is None or day >= cfg.entries_from)
                and (cfg.regime is None or cfg.regime.get(day, False))
                and (allowed is None or s in allowed)
            ):
                pending_entry[s] = (sig.stop_distance[i], sig.score[i])
            else:
                pending_entry.pop(s, None)

    result = Result(cfg, curve, closed, list(positions.values()), skipped)
    result.metrics = _metrics(result, days_in_market)
    return result


def _metrics(result: Result, days_in_market: int) -> dict:
    out = window_metrics(result.equity_curve, result.trades)
    if out:
        out["exposure_pct"] = round(days_in_market / len(result.equity_curve) * 100, 1)
        out["total_costs"] = round(sum(t.costs for t in result.trades) + sum(t.costs for t in result.open_positions), 2)
        out["open_positions_at_end"] = len(result.open_positions)
        out["skipped_entries"] = result.skipped_entries
    return out


def window_metrics(curve: list[tuple[date, float]], trades: list[Trade]) -> dict:
    """Performance of an equity curve (or a slice of one) and the trades closed in it."""
    if len(curve) < 2:
        return {}
    start, end = curve[0][0], curve[-1][0]
    base, final = curve[0][1], curve[-1][1]
    years = max((end - start).days, 1) / 365.25
    cagr = (final / base) ** (1 / years) - 1 if final > 0 else -1.0

    peak, max_dd = base, 0.0
    for _, value in curve:
        peak = max(peak, value)
        max_dd = max(max_dd, 1 - value / peak)

    returns = [curve[i][1] / curve[i - 1][1] - 1 for i in range(1, len(curve))]
    sharpe = None
    if len(returns) > 1:
        mean = sum(returns) / len(returns)
        var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
        if var > 0:
            sharpe = mean / math.sqrt(var) * math.sqrt(252)

    wins = [t.pnl for t in trades if t.pnl > 0]
    losses = [t.pnl for t in trades if t.pnl <= 0]
    r_values = [t.r_multiple for t in trades if t.r_multiple is not None]
    gross_loss = -sum(losses)
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "years": round(years, 2),
        "final_equity": round(final, 2),
        "total_return_pct": round((final / base - 1) * 100, 2),
        "cagr_pct": round(cagr * 100, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "sharpe": None if sharpe is None else round(sharpe, 2),
        "closed_trades": len(trades),
        "win_rate_pct": round(len(wins) / len(trades) * 100, 1) if trades else None,
        "avg_win": round(sum(wins) / len(wins), 2) if wins else None,
        "avg_loss": round(sum(losses) / len(losses), 2) if losses else None,
        "profit_factor": round(sum(wins) / gross_loss, 2) if gross_loss > 0 else None,
        "expectancy_per_trade": round(sum(t.pnl for t in trades) / len(trades), 2) if trades else None,
        "avg_r_multiple": round(sum(r_values) / len(r_values), 3) if r_values else None,
        "avg_holding_days": round(sum(t.holding_days for t in trades) / len(trades), 1) if trades else None,
    }


def bars_before(bars: Bars, cutoff: date) -> Bars:
    """The part of ``bars`` dated strictly before ``cutoff``."""
    end = next((i for i, d in enumerate(bars.dates) if d >= cutoff), len(bars))
    return bars.slice(end)
