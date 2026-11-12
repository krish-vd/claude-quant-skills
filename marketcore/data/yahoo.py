"""Yahoo Finance chart endpoint: keyless daily prices for US stocks, ETFs and
futures (for example AAPL, SPY, GC=F, CL=F) and a fallback for other markets.

This is an UNOFFICIAL endpoint. It can change or be rate-limited without
notice, and prices are not an exchange record. Use the NSE bhavcopy adapter for
Indian equities; treat this as indicative.
"""
from __future__ import annotations

import json
import urllib.parse
from datetime import datetime, timezone

from . import DataUnavailable, http_get

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={range}&interval=1d"


def daily_history(symbol: str, range_: str = "1mo") -> dict:
    """Daily OHLCV bars. ``range_`` is one of 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max."""
    url = CHART_URL.format(symbol=urllib.parse.quote(symbol.upper()), range=range_)
    try:
        payload = json.loads(http_get(url))
        result = payload["chart"]["result"][0]
        meta = result["meta"]
        quote = result["indicators"]["quote"][0]
        stamps = result["timestamp"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise DataUnavailable(f"Yahoo returned no chart data for {symbol}") from exc
    bars = []
    for i, ts in enumerate(stamps):
        close = quote["close"][i]
        if close is None:
            continue
        bars.append(
            {
                "date": datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat(),
                "open": quote["open"][i],
                "high": quote["high"][i],
                "low": quote["low"][i],
                "close": close,
                "volume": quote["volume"][i],
            }
        )
    if not bars:
        raise DataUnavailable(f"Yahoo returned empty bars for {symbol}")
    return {
        "symbol": meta.get("symbol", symbol.upper()),
        "currency": meta.get("currency"),
        "exchange": meta.get("fullExchangeName") or meta.get("exchangeName"),
        "bars": bars,
        "source": url,
        "source_kind": "unofficial",
    }


def last_close(symbol: str) -> dict:
    data = daily_history(symbol, "5d")
    bar = data["bars"][-1]
    return {
        "symbol": data["symbol"],
        "date": bar["date"],
        "close": bar["close"],
        "currency": data["currency"],
        "exchange": data["exchange"],
        "source": data["source"],
        "source_kind": "unofficial",
    }
