"""Trade journal, performance review and a loss circuit breaker.

The journal is one JSON file on the user's machine (default
``~/.market-skills/journal.json``; override with ``MARKET_SKILLS_HOME`` or an
explicit path). Nothing is uploaded anywhere.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Optional


def default_path() -> Path:
    home = os.environ.get("MARKET_SKILLS_HOME") or str(Path.home() / ".market-skills")
    return Path(home) / "journal.json"


def load(path: Optional[Path] = None) -> list[dict]:
    path = path or default_path()
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))["trades"]


def save(trades: list[dict], path: Optional[Path] = None) -> Path:
    path = path or default_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"version": 1, "trades": trades}, indent=2), encoding="utf-8")
    tmp.replace(path)
    return path


def add_trade(
    trades: list[dict], symbol: str, direction: str, entry_date: date, entry_price: float, quantity: float,
    stop: Optional[float] = None, target: Optional[float] = None, setup: str = "", thesis: str = "",
    market: str = "IN", multiplier: float = 1.0,
) -> dict:
    """Record an opened trade. ``quantity`` is shares or contracts; ``multiplier`` is the
    value of a 1.0 price move per unit of quantity (1 for shares, the lot size or contract
    multiplier for futures entered as a number of lots)."""
    if direction not in ("long", "short"):
        raise ValueError("direction must be 'long' or 'short'")
    if entry_price <= 0 or quantity <= 0 or multiplier <= 0:
        raise ValueError("entry price, quantity and multiplier must be positive")
    if stop is not None:
        if stop <= 0 or (direction == "long" and stop >= entry_price) or (direction == "short" and stop <= entry_price):
            raise ValueError("stop must be below entry for a long and above entry for a short")
    trade = {
        "id": max((t["id"] for t in trades), default=0) + 1,
        "status": "open",
        "symbol": symbol.upper(),
        "market": market.upper(),
        "direction": direction,
        "entry_date": entry_date.isoformat(),
        "entry_price": entry_price,
        "quantity": quantity,
        "multiplier": multiplier,
        "stop": stop,
        "target": target,
        "planned_risk": None if stop is None else abs(entry_price - stop) * quantity * multiplier,
        "setup": setup,
        "thesis": thesis,
    }
    trades.append(trade)
    return trade


def close_trade(
    trades: list[dict], trade_id: int, exit_date: date, exit_price: float, fees: float = 0.0,
    followed_plan: Optional[bool] = None, notes: str = "",
) -> dict:
    """Close an open trade and compute its P&L and R-multiple (P&L / planned risk)."""
    trade = next((t for t in trades if t["id"] == trade_id), None)
    if trade is None:
        raise ValueError(f"no trade with id {trade_id}")
    if trade["status"] != "open":
        raise ValueError(f"trade {trade_id} is already closed")
    if exit_price <= 0 or fees < 0:
        raise ValueError("exit price must be positive and fees not negative")
    if exit_date < date.fromisoformat(trade["entry_date"]):
        raise ValueError("exit date is before the entry date")
    sign = 1.0 if trade["direction"] == "long" else -1.0
    pnl = sign * (exit_price - trade["entry_price"]) * trade["quantity"] * trade["multiplier"] - fees
    trade.update(
        status="closed", exit_date=exit_date.isoformat(), exit_price=exit_price, fees=fees,
        followed_plan=followed_plan, notes=notes, pnl=pnl,
        r_multiple=None if not trade["planned_risk"] else pnl / trade["planned_risk"],
    )
    return trade


def _block(rows: list[dict]) -> dict:
    wins = [t["pnl"] for t in rows if t["pnl"] > 0]
    losses = [t["pnl"] for t in rows if t["pnl"] <= 0]
    r_values = [t["r_multiple"] for t in rows if t.get("r_multiple") is not None]
    gross_loss = -sum(losses)
    return {
        "trades": len(rows),
        "net_pnl": round(sum(t["pnl"] for t in rows), 2),
        "win_rate_pct": round(len(wins) / len(rows) * 100, 1) if rows else None,
        "avg_win": round(sum(wins) / len(wins), 2) if wins else None,
        "avg_loss": round(sum(losses) / len(losses), 2) if losses else None,
        "payoff_ratio": round((sum(wins) / len(wins)) / (gross_loss / len(losses)), 2) if wins and gross_loss > 0 else None,
        "profit_factor": round(sum(wins) / gross_loss, 2) if gross_loss > 0 else None,
        "expectancy_per_trade": round(sum(t["pnl"] for t in rows) / len(rows), 2) if rows else None,
        "avg_r": round(sum(r_values) / len(r_values), 3) if r_values else None,
        "total_r": round(sum(r_values), 2) if r_values else None,
    }


def review(trades: list[dict], start: Optional[date] = None, end: Optional[date] = None) -> dict:
    """Statistics for trades CLOSED in the window, in the order they were closed."""
    closed = sorted((t for t in trades if t["status"] == "closed"), key=lambda t: (t["exit_date"], t["id"]))
    if start:
        closed = [t for t in closed if t["exit_date"] >= start.isoformat()]
    if end:
        closed = [t for t in closed if t["exit_date"] <= end.isoformat()]
    if not closed:
        return {"trades": 0}

    out = _block(closed)
    streak = longest_losing = longest_winning = 0
    equity = peak = max_dd = 0.0
    for t in closed:
        won = t["pnl"] > 0
        streak = (streak + 1 if streak > 0 else 1) if won else (streak - 1 if streak < 0 else -1)
        longest_winning, longest_losing = max(longest_winning, streak), max(longest_losing, -streak)
        equity += t["pnl"]
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    holding = [(date.fromisoformat(t["exit_date"]) - date.fromisoformat(t["entry_date"])).days for t in closed]
    best, worst = max(closed, key=lambda t: t["pnl"]), min(closed, key=lambda t: t["pnl"])

    by_setup: dict[str, list] = defaultdict(list)
    by_month: dict[str, list] = defaultdict(list)
    by_plan: dict[str, list] = defaultdict(list)
    for t in closed:
        by_setup[t.get("setup") or "(no setup tag)"].append(t)
        by_month[t["exit_date"][:7]].append(t)
        plan = t.get("followed_plan")
        by_plan["not recorded" if plan is None else ("followed" if plan else "broke")].append(t)
    no_stop = sum(1 for t in closed if t.get("stop") is None)

    out.update(
        first_exit=closed[0]["exit_date"], last_exit=closed[-1]["exit_date"],
        avg_holding_days=round(sum(holding) / len(holding), 1),
        longest_winning_streak=longest_winning, longest_losing_streak=longest_losing,
        current_streak=streak,
        max_drawdown_of_realised_pnl=round(max_dd, 2),
        best_trade={"id": best["id"], "symbol": best["symbol"], "pnl": round(best["pnl"], 2)},
        worst_trade={"id": worst["id"], "symbol": worst["symbol"], "pnl": round(worst["pnl"], 2)},
        trades_without_a_stop=no_stop,
        by_setup={k: _block(v) for k, v in sorted(by_setup.items())},
        by_month={k: _block(v) for k, v in sorted(by_month.items())},
        by_plan_adherence={k: _block(v) for k, v in sorted(by_plan.items())},
    )
    return out


def circuit_breaker(
    trades: list[dict], account: float, today: date,
    daily_loss_pct: float = 2.0, weekly_loss_pct: float = 4.0, monthly_loss_pct: float = 8.0,
    max_consecutive_losses: int = 3, max_open_risk_pct: float = 6.0,
) -> dict:
    """Should new risk be taken today? Blocks on realised-loss limits for the day,
    week (from Monday) and month, on a run of losses, and on total open risk.

    The default limits are common conventions, not rules: set your own.
    """
    if account <= 0:
        raise ValueError("account must be positive")
    closed = sorted((t for t in trades if t["status"] == "closed"), key=lambda t: (t["exit_date"], t["id"]))
    week_start = today - timedelta(days=today.weekday())

    def realised(since: date) -> float:
        return sum(t["pnl"] for t in closed if since.isoformat() <= t["exit_date"] <= today.isoformat())

    run = 0
    for t in reversed(closed):
        if t["pnl"] > 0:
            break
        run += 1
    open_trades = [t for t in trades if t["status"] == "open"]
    open_risk = sum(t["planned_risk"] or 0.0 for t in open_trades)
    unprotected = [t["symbol"] for t in open_trades if t.get("stop") is None]

    checks = []

    def loss_check(name: str, pnl: float, limit_pct: float) -> None:
        limit = account * limit_pct / 100
        checks.append({
            "check": name, "realised_pnl": round(pnl, 2), "limit": round(-limit, 2),
            "used_pct_of_limit": round(max(-pnl, 0.0) / limit * 100, 1) if limit else None,
            "breached": pnl <= -limit,
        })

    loss_check("daily_loss", realised(today), daily_loss_pct)
    loss_check("weekly_loss", realised(week_start), weekly_loss_pct)
    loss_check("monthly_loss", realised(today.replace(day=1)), monthly_loss_pct)
    checks.append({"check": "consecutive_losses", "count": run, "limit": max_consecutive_losses,
                   "breached": run >= max_consecutive_losses})
    risk_limit = account * max_open_risk_pct / 100
    checks.append({"check": "open_risk", "open_risk": round(open_risk, 2), "limit": round(risk_limit, 2),
                   "room_for_new_risk": round(max(risk_limit - open_risk, 0.0), 2), "breached": open_risk >= risk_limit})
    breached = [c["check"] for c in checks if c["breached"]]
    return {
        "date": today.isoformat(),
        "account": account,
        "new_risk_allowed": not breached,
        "breached": breached,
        "checks": checks,
        "open_trades": len(open_trades),
        "open_trades_without_a_stop": unprotected,
    }


def pretrade_check(
    trades: list[dict], account: float, today: date, symbol: str, direction: str, entry: float,
    stop: Optional[float], quantity: float, target: Optional[float] = None, multiplier: float = 1.0,
    max_risk_pct: float = 1.0, min_reward_to_risk: float = 2.0, max_position_pct: float = 20.0,
    leveraged: bool = False, **breaker_limits,
) -> dict:
    """Gate for a planned trade. Each rule passes, fails, or warns; any failure blocks the trade.

    Rules: a stop exists and is on the correct side; planned risk is within the
    per-trade limit; the position is within the size cap (skipped for leveraged
    instruments, whose notional is not the capital at stake); reward to risk meets
    the minimum when a target is given; the circuit breaker allows new risk; the
    new risk fits in the open-risk room; and the symbol is not already open.
    """
    if direction not in ("long", "short"):
        raise ValueError("direction must be 'long' or 'short'")
    if account <= 0 or entry <= 0 or quantity <= 0 or multiplier <= 0:
        raise ValueError("account, entry, quantity and multiplier must be positive")
    checks: list[dict] = []

    def add(name: str, status: str, detail: str) -> None:
        checks.append({"rule": name, "status": status, "detail": detail})

    risk = None
    if stop is None:
        add("stop_defined", "fail", "No stop. Without one the risk of this trade is undefined.")
    elif (direction == "long" and stop >= entry) or (direction == "short" and stop <= entry) or stop <= 0:
        add("stop_defined", "fail", f"Stop {stop} is on the wrong side of entry {entry} for a {direction} trade.")
    else:
        risk = abs(entry - stop) * quantity * multiplier
        add("stop_defined", "pass", f"Stop at {stop}: planned risk {risk:,.2f}.")

    if risk is not None:
        limit = account * max_risk_pct / 100
        pct = risk / account * 100
        add("risk_per_trade", "pass" if risk <= limit else "fail",
            f"Risk is {pct:.2f}% of the account; the limit is {max_risk_pct}% ({limit:,.2f}).")

    value = entry * quantity * multiplier
    if leveraged:
        add("position_size", "warn", f"Leveraged instrument: notional {value:,.2f} is {value / account * 100:.1f}% of the account. "
                                     "Check margin with the broker; the size cap is not applied.")
    else:
        cap = account * max_position_pct / 100
        add("position_size", "pass" if value <= cap else "fail",
            f"Position value {value:,.2f} is {value / account * 100:.1f}% of the account; the cap is {max_position_pct}%.")

    if target is None:
        add("reward_to_risk", "warn", "No target given, so reward to risk cannot be checked.")
    elif risk is not None:
        reward = (target - entry) if direction == "long" else (entry - target)
        ratio = reward / abs(entry - stop)
        if reward <= 0:
            add("reward_to_risk", "fail", f"Target {target} is on the wrong side of entry for a {direction} trade.")
        else:
            add("reward_to_risk", "pass" if ratio >= min_reward_to_risk else "fail",
                f"Reward to risk is {ratio:.2f}; the minimum is {min_reward_to_risk}.")

    breaker = circuit_breaker(trades, account, today, **breaker_limits)
    add("circuit_breaker", "pass" if breaker["new_risk_allowed"] else "fail",
        "New risk is allowed." if breaker["new_risk_allowed"] else f"Blocked by: {', '.join(breaker['breached'])}.")
    room = next(c["room_for_new_risk"] for c in breaker["checks"] if c["check"] == "open_risk")
    if risk is not None:
        add("open_risk_room", "pass" if risk <= room else "fail",
            f"This trade adds {risk:,.2f} of risk; room under the open-risk cap is {room:,.2f}.")

    already = [t["id"] for t in trades if t["status"] == "open" and t["symbol"] == symbol.upper()]
    add("not_already_open", "warn" if already else "pass",
        f"{symbol.upper()} is already open (trade id {already[0]}): this adds to an existing position." if already
        else f"No open position in {symbol.upper()}.")

    failed = [c["rule"] for c in checks if c["status"] == "fail"]
    return {
        "symbol": symbol.upper(),
        "direction": direction,
        "approved": not failed,
        "failed_rules": failed,
        "warnings": [c["rule"] for c in checks if c["status"] == "warn"],
        "planned_risk": None if risk is None else round(risk, 2),
        "planned_risk_pct": None if risk is None else round(risk / account * 100, 3),
        "position_value": round(value, 2),
        "checks": checks,
    }
