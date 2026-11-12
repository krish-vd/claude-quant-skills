"""A rule-based strategy described as data, so a trading idea can be backtested
without writing code.

A rule file is JSON:

    {
      "entry": [["close", ">", "sma:200"], ["rsi:2", "<", 10]],
      "exit":  [["close", ">", "sma:5"]],
      "exit_mode": "any",
      "stop_atr_mult": 2.0,
      "rank_by": "roc:126"
    }

Every condition in ``entry`` must hold to enter. ``exit_mode`` "any" (default) exits
when any exit condition holds; "all" needs all of them. Each condition is
[left, operator, right]. Operators: > < >= <= crosses_above crosses_below.
Terms: a number, or one of

    close open high low volume
    sma:N ema:N rsi:N atr:N roc:N            (roc is a fraction: 0.2 = 20%)
    highest:N lowest:N                       (of the N sessions BEFORE today)
    volume_sma:N
    close_pct_of_highest:N                   (close / highest of the previous N closes)

Everything is computed from data up to and including the current session, and orders
fill at the next open, so a rule cannot see the future.
"""
from __future__ import annotations

import json
import operator
from pathlib import Path
from typing import Callable, Optional, Union

from . import indicators as ind
from .backtest import Bars, Signals

OPERATORS = {">": operator.gt, "<": operator.lt, ">=": operator.ge, "<=": operator.le}
CROSS = ("crosses_above", "crosses_below")
Series = list[Optional[float]]


def _shift(values: Series, k: int = 1) -> Series:
    return [None] * k + values[:-k] if k else values


def term_series(bars: Bars, term: Union[str, float, int], cache: dict) -> Series:
    if isinstance(term, (int, float)):
        return [float(term)] * len(bars)
    key = str(term).strip().lower()
    if key in cache:
        return cache[key]
    base = {"close": bars.close, "open": bars.open, "high": bars.high, "low": bars.low, "volume": bars.volume}
    if key in base:
        out: Series = list(base[key])
    else:
        name, sep, arg = key.partition(":")
        if not sep or not arg.isdigit() or int(arg) < 1:
            raise ValueError(f"unknown term {term!r}")
        n = int(arg)
        if name == "sma":
            out = ind.sma(bars.close, n)
        elif name == "ema":
            out = ind.ema(bars.close, n)
        elif name == "rsi":
            out = ind.rsi(bars.close, n)
        elif name == "atr":
            out = ind.atr(bars.high, bars.low, bars.close, n)
        elif name == "roc":
            out = ind.roc(bars.close, n)
        elif name == "highest":
            out = _shift(ind.highest(bars.high, n))
        elif name == "lowest":
            out = _shift(ind.lowest(bars.low, n))
        elif name == "volume_sma":
            out = ind.sma(bars.volume, n)
        elif name == "close_pct_of_highest":
            prior = _shift(ind.highest(bars.close, n))
            out = [c / h if h else None for c, h in zip(bars.close, prior)]
        else:
            raise ValueError(f"unknown indicator {name!r}")
    cache[key] = out
    return out


def _condition(bars: Bars, cond: list, cache: dict) -> list[bool]:
    if not isinstance(cond, (list, tuple)) or len(cond) != 3:
        raise ValueError(f"a condition must be [left, operator, right], got {cond!r}")
    left, op, right = cond
    a, b = term_series(bars, left, cache), term_series(bars, right, cache)
    out = [False] * len(bars)
    if op in OPERATORS:
        f = OPERATORS[op]
        for i in range(len(bars)):
            if a[i] is not None and b[i] is not None:
                out[i] = f(a[i], b[i])
    elif op in CROSS:
        above = op == "crosses_above"
        for i in range(1, len(bars)):
            if None in (a[i], b[i], a[i - 1], b[i - 1]):
                continue
            out[i] = (a[i] > b[i] and a[i - 1] <= b[i - 1]) if above else (a[i] < b[i] and a[i - 1] >= b[i - 1])
    else:
        raise ValueError(f"unknown operator {op!r}; use one of {sorted(OPERATORS) + list(CROSS)}")
    return out


def validate(spec: dict) -> dict:
    if not spec.get("entry"):
        raise ValueError("the rule needs at least one entry condition")
    if spec.get("exit_mode", "any") not in ("any", "all"):
        raise ValueError("exit_mode must be 'any' or 'all'")
    if not spec.get("exit") and not spec.get("stop_atr_mult"):
        raise ValueError("the rule needs an exit condition or a stop (stop_atr_mult), or positions never close")
    return spec


def build(spec: dict) -> Callable[[Bars, dict], Signals]:
    validate(spec)
    entry_rules, exit_rules = spec["entry"], spec.get("exit") or []
    combine_exit = any if spec.get("exit_mode", "any") == "any" else all
    stop_mult = float(spec.get("stop_atr_mult") or 0)
    atr_n = int(spec.get("atr_n", 20))
    rank_by = spec.get("rank_by", "roc:126")

    def strategy(bars: Bars, _params: dict) -> Signals:
        cache: dict = {}
        entries = [_condition(bars, c, cache) for c in entry_rules]
        exits = [_condition(bars, c, cache) for c in exit_rules]
        atr = ind.atr(bars.high, bars.low, bars.close, atr_n) if stop_mult > 0 else None
        score = term_series(bars, rank_by, cache)
        n = len(bars)
        sig = Signals([False] * n, [False] * n, [None] * n, [0.0] * n)
        for i in range(n):
            if all(e[i] for e in entries):
                if stop_mult > 0:
                    if atr[i] is None:
                        continue
                    sig.stop_distance[i] = stop_mult * atr[i]
                sig.entry[i] = True
                sig.score[i] = score[i] or 0.0
            if exits and combine_exit(x[i] for x in exits):
                sig.exit[i] = True
        return sig

    return strategy


def load(path: Union[str, Path]) -> dict:
    try:
        return validate(json.loads(Path(path).read_text(encoding="utf-8")))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc
