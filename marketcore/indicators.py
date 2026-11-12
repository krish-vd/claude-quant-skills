"""Technical indicators on plain lists. Warm-up positions are ``None``.

Every value at index ``i`` uses data up to and including ``i`` only, so an
indicator can never see the future.
"""
from __future__ import annotations

from typing import Optional, Sequence

Series = list[Optional[float]]


def sma(values: Sequence[float], n: int) -> Series:
    """Simple moving average of the last ``n`` values."""
    _check(n)
    out: Series = [None] * len(values)
    running = 0.0
    for i, v in enumerate(values):
        running += v
        if i >= n:
            running -= values[i - n]
        if i >= n - 1:
            out[i] = running / n
    return out


def ema(values: Sequence[float], n: int) -> Series:
    """Exponential moving average, seeded with the SMA of the first ``n`` values."""
    _check(n)
    out: Series = [None] * len(values)
    if len(values) < n:
        return out
    alpha = 2.0 / (n + 1)
    current = sum(values[:n]) / n
    out[n - 1] = current
    for i in range(n, len(values)):
        current = alpha * values[i] + (1 - alpha) * current
        out[i] = current
    return out


def rsi(values: Sequence[float], n: int = 14) -> Series:
    """Wilder's RSI. The first value is at index ``n`` (it needs ``n`` changes)."""
    _check(n)
    out: Series = [None] * len(values)
    if len(values) <= n:
        return out
    gains = losses = 0.0
    for i in range(1, n + 1):
        change = values[i] - values[i - 1]
        gains += max(change, 0.0)
        losses += max(-change, 0.0)
    avg_gain, avg_loss = gains / n, losses / n
    out[n] = _rsi_value(avg_gain, avg_loss)
    for i in range(n + 1, len(values)):
        change = values[i] - values[i - 1]
        avg_gain = (avg_gain * (n - 1) + max(change, 0.0)) / n
        avg_loss = (avg_loss * (n - 1) + max(-change, 0.0)) / n
        out[i] = _rsi_value(avg_gain, avg_loss)
    return out


def _rsi_value(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    return 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)


def true_range(high: Sequence[float], low: Sequence[float], close: Sequence[float]) -> list[float]:
    out = []
    for i in range(len(close)):
        if i == 0:
            out.append(high[0] - low[0])
        else:
            out.append(max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1])))
    return out


def atr(high: Sequence[float], low: Sequence[float], close: Sequence[float], n: int = 14) -> Series:
    """Wilder's average true range. First value at index ``n - 1`` is the mean of the first ``n`` true ranges."""
    _check(n)
    tr = true_range(high, low, close)
    out: Series = [None] * len(close)
    if len(close) < n:
        return out
    current = sum(tr[:n]) / n
    out[n - 1] = current
    for i in range(n, len(close)):
        current = (current * (n - 1) + tr[i]) / n
        out[i] = current
    return out


def highest(values: Sequence[float], n: int) -> Series:
    """Highest of the last ``n`` values, including the current one."""
    _check(n)
    return [max(values[i - n + 1 : i + 1]) if i >= n - 1 else None for i in range(len(values))]


def lowest(values: Sequence[float], n: int) -> Series:
    """Lowest of the last ``n`` values, including the current one."""
    _check(n)
    return [min(values[i - n + 1 : i + 1]) if i >= n - 1 else None for i in range(len(values))]


def roc(values: Sequence[float], n: int) -> Series:
    """Rate of change over ``n`` bars: values[i] / values[i - n] - 1."""
    _check(n)
    return [values[i] / values[i - n] - 1.0 if i >= n and values[i - n] else None for i in range(len(values))]


def _check(n: int) -> None:
    if n < 1:
        raise ValueError("period must be at least 1")
