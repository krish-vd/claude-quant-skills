"""NSE official end-of-day files: bhavcopy (UDiFF format) and F&O lot sizes.

Source: https://nsearchives.nseindia.com - the exchange's own archive. The
bhavcopy for a trading day is published in the evening, India time.
"""
from __future__ import annotations

import csv
import io
import zipfile
from datetime import date, timedelta
from typing import Optional

from . import DataUnavailable, cached_get

REFERER = "https://www.nseindia.com/"
CM_URL = "https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{ymd}_F_0000.csv.zip"
FO_URL = "https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_{ymd}_F_0000.csv.zip"
LOTS_URL = "https://nsearchives.nseindia.com/content/fo/fo_mktlots.csv"
_FOREVER = 10 * 365 * 86400.0  # a published bhavcopy never changes


def _bhavcopy(url_template: str, prefix: str, day: date) -> list[dict[str, str]]:
    ymd = day.strftime("%Y%m%d")
    body = cached_get(url_template.format(ymd=ymd), f"{prefix}_{ymd}.zip", _FOREVER, REFERER)
    try:
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            raw = archive.read(archive.namelist()[0]).decode("utf-8-sig")
    except zipfile.BadZipFile as exc:
        raise DataUnavailable(f"No NSE bhavcopy for {day.isoformat()} (holiday, weekend or not yet published)") from exc
    return list(csv.DictReader(io.StringIO(raw)))


def cm_bhavcopy(day: date) -> list[dict[str, str]]:
    """Cash-market bhavcopy rows for one trading day (all series)."""
    return _bhavcopy(CM_URL, "nse_cm", day)


def fo_bhavcopy(day: date) -> list[dict[str, str]]:
    """Futures and options bhavcopy rows for one trading day."""
    return _bhavcopy(FO_URL, "nse_fo", day)


def latest_cm_bhavcopy(on_or_before: Optional[date] = None, lookback_days: int = 7) -> tuple[date, list[dict[str, str]]]:
    """Most recent published cash bhavcopy on or before a date."""
    day = on_or_before or date.today()
    for _ in range(lookback_days + 1):
        if day.weekday() < 5:
            try:
                return day, cm_bhavcopy(day)
            except DataUnavailable:
                pass
        day -= timedelta(days=1)
    raise DataUnavailable(f"No NSE bhavcopy found in the {lookback_days} days up to {on_or_before or date.today()}")


def equity_quote(symbol: str, day: Optional[date] = None, series: str = "EQ") -> dict:
    """Official OHLC, close and volume for one NSE symbol from the bhavcopy."""
    found_day, rows = latest_cm_bhavcopy(day) if day is None else (day, cm_bhavcopy(day))
    wanted = symbol.upper()
    for row in rows:
        if row["TckrSymb"] == wanted and row["SctySrs"] == series:
            return {
                "symbol": wanted,
                "series": series,
                "isin": row["ISIN"],
                "date": found_day.isoformat(),
                "open": row["OpnPric"],
                "high": row["HghPric"],
                "low": row["LwPric"],
                "close": row["ClsPric"],
                "prev_close": row["PrvsClsgPric"],
                "volume": row["TtlTradgVol"],
                "traded_value": row["TtlTrfVal"],
                "currency": "INR",
                "source": CM_URL.format(ymd=found_day.strftime("%Y%m%d")),
            }
    raise DataUnavailable(f"{wanted} (series {series}) is not in the NSE bhavcopy for {found_day.isoformat()}")


def parse_lots(text: str) -> dict[str, dict[str, int]]:
    """Parse fo_mktlots.csv into {SYMBOL: {"NOV-26": 65, ...}}."""
    lots: dict[str, dict[str, int]] = {}
    months: list[str] = []
    for line in csv.reader(io.StringIO(text)):
        cells = [c.strip() for c in line]
        if len(cells) < 3:
            continue
        if cells[1].upper() == "SYMBOL":
            months = cells[2:]  # the header row repeats before the stock section
            continue
        per_month = {}
        for month, value in zip(months, cells[2:]):
            if month and value.isdigit():
                per_month[month.upper()] = int(value)
        if per_month:
            lots[cells[1].upper()] = per_month
    return lots


def fo_lot_sizes() -> dict[str, dict[str, int]]:
    """Current NSE F&O market lots per symbol and expiry month (cached for 12 hours)."""
    body = cached_get(LOTS_URL, "nse_fo_mktlots.csv", 12 * 3600.0, REFERER)
    lots = parse_lots(body.decode("utf-8-sig", errors="replace"))
    if "NIFTY" not in lots:
        raise DataUnavailable("NSE lot-size file did not parse: NIFTY missing")
    return lots


def lot_size(symbol: str, expiry_month: Optional[str] = None) -> dict:
    """Lot size for a symbol. ``expiry_month`` is like 'NOV-26'; default is the nearest listed month."""
    lots = fo_lot_sizes()
    wanted = symbol.upper()
    if wanted not in lots:
        raise DataUnavailable(f"{wanted} has no NSE F&O contracts in the current lot-size file")
    months = lots[wanted]
    month = (expiry_month or next(iter(months))).upper()
    if month not in months:
        raise DataUnavailable(f"{wanted}: no lot size listed for {month}. Listed: {', '.join(months)}")
    return {"symbol": wanted, "expiry_month": month, "lot_size": months[month], "all_months": months, "source": LOTS_URL}
