"""Three Indian tax helpers: F&O business income, advance-tax instalments on capital
gains, and Schedule FA figures for foreign shares.

Each rests on rules that could only be checked against secondary sources, and two
of them have points that sources disagree on. Where that is so the function
returns every reading instead of choosing one.
"""
from __future__ import annotations

from bisect import bisect_right
from datetime import date
from decimal import Decimal
from typing import Iterable, Optional

from . import rules
from .tax_india import RealisedLot, financial_year, summarise

# ---------- F&O business income ----------

_BOOK = rules.load("in_tax")
AUDIT_LIMIT_GENERAL = Decimal(_BOOK["fno_audit"]["turnover_limit_general"])  # Rs 1 crore
AUDIT_LIMIT_DIGITAL = Decimal(_BOOK["fno_audit"]["turnover_limit_low_cash"])  # Rs 10 crore, low-cash businesses


def fno_income(trades: Iterable[dict]) -> dict:
    """Summarise closed F&O trades for the business-income schedule.

    Each trade: {"kind": "future"|"option", "pnl": profit or loss before charges,
    "charges": costs, "sale_value": for options, the premium received on the sell leg}.

    Turnover is reported two ways because sources disagree on the current ICAI
    guidance: the sum of absolute profits and losses, and that sum plus the premium
    received on option sales.
    """
    futures_abs = options_abs = premium = net = charges = Decimal(0)
    count = 0
    for t in trades:
        kind = str(t.get("kind", "")).lower()
        if kind not in ("future", "option"):
            raise ValueError(f"trade kind must be 'future' or 'option', got {t.get('kind')!r}")
        pnl = Decimal(str(t["pnl"]))
        count += 1
        net += pnl
        charges += Decimal(str(t.get("charges", 0) or 0))
        if kind == "future":
            futures_abs += abs(pnl)
        else:
            options_abs += abs(pnl)
            premium += Decimal(str(t.get("sale_value", 0) or 0))
    absolute = futures_abs + options_abs
    with_premium = absolute + premium

    def audit(turnover: Decimal) -> dict:
        return {"turnover": str(turnover), "above_1_crore": turnover > AUDIT_LIMIT_GENERAL,
                "above_10_crore": turnover > AUDIT_LIMIT_DIGITAL}

    return {
        "trades": count,
        "net_profit_before_charges": str(net),
        "charges": str(charges),
        "net_profit_after_charges": str(net - charges),
        "futures_turnover": str(futures_abs),
        "options_absolute_pnl": str(options_abs),
        "options_sale_premium": str(premium),
        "turnover_absolute_method": audit(absolute),
        "turnover_absolute_plus_option_premium": audit(with_premium),
        "methods_agree": premium == 0,
    }


# ---------- advance tax on capital gains ----------

INSTALMENTS = tuple(
    (row["month"], row["day"], Decimal(row["cumulative_fraction"])) for row in _BOOK["advance_tax"]["instalments"]
)
ADVANCE_TAX_THRESHOLD = Decimal(_BOOK["advance_tax"]["applies_when_tax_at_least"])


def advance_tax_schedule(lots: Iterable[RealisedLot], fy: str, paid: Optional[dict] = None) -> dict:
    """Advance-tax instalments for the special-rate capital gains realised in ``fy`` ("2026-27").

    By each due date the cumulative amount due is that date's percentage of the tax on
    gains realised UP TO that date. Tax on gains realised later falls into the later
    instalments, and anything realised after 15 March is due by 31 March. This follows
    the relief that no interest is charged for a shortfall caused by capital gains that
    had not yet arisen, provided the tax is paid in the remaining instalments.

    Only tax on the 20% and 12.5% buckets (with cess) is covered; slab-rate gains, other
    income, TDS and surcharge are not. ``paid`` maps a due date to the amount already paid.
    """
    start_year = int(fy[:4])
    year_lots = [lot for lot in lots if lot.fy == fy]
    paid = paid or {}

    def tax_up_to(cutoff: date) -> Decimal:
        subset = [lot for lot in year_lots if lot.sell_date <= cutoff]
        summaries = summarise(subset)
        return summaries[0].tax_with_cess if summaries else Decimal(0)

    year_end = date(start_year + 1, 3, 31)
    total = tax_up_to(year_end)
    rows, cumulative_paid = [], Decimal(0)
    for month, day, pct in INSTALMENTS:
        due = date(start_year + (1 if month == 3 else 0), month, day)
        tax_so_far = tax_up_to(due)
        required = (tax_so_far * pct).quantize(Decimal("1"))
        cumulative_paid += Decimal(str(paid.get(due, 0)))
        rows.append({
            "due_date": due.isoformat(),
            "cumulative_pct": str((pct * 100).quantize(Decimal("1"))),
            "tax_on_gains_realised_by_then": str(tax_so_far.quantize(Decimal("0.01"))),
            "cumulative_amount_due": str(required),
            "cumulative_paid": str(cumulative_paid),
            "shortfall": str(max(required - cumulative_paid, Decimal(0))),
        })
    after_march = total - tax_up_to(date(start_year + 1, 3, 15))
    return {
        "financial_year": fy,
        "special_rate_tax_for_the_year": str(total.quantize(Decimal("0.01"))),
        "advance_tax_applies": total >= ADVANCE_TAX_THRESHOLD,
        "threshold": str(ADVANCE_TAX_THRESHOLD),
        "instalments": rows,
        "tax_on_gains_after_15_march_due_by_31_march": str(after_march.quantize(Decimal("0.01"))),
    }


# ---------- Schedule FA for foreign shares ----------

def _shares_on(day: date, events: list[tuple[date, float]]) -> float:
    return sum(q for d, q in events if d <= day)


def schedule_fa_rows(
    trades: list[dict], prices: dict[str, tuple[list[date], list[float]]], calendar_year: int,
    rates: Optional[dict[date, float]] = None,
) -> dict:
    """Schedule FA (Table A3) figures per foreign share, for one CALENDAR year.

    ``trades``: {"symbol", "date", "side": buy|sell, "quantity", "price"} in the foreign
    currency. ``prices``: per symbol, (dates, closes) in the foreign currency.
    ``rates``: SBI telegraphic-transfer buying rates by date, supplied by the user.

    For each symbol held at any time in the year the result gives, in foreign currency,
    the cost of the shares held (initial value), the peak holding value and its date, the
    closing value on the last trading day of the year, and the gross sale proceeds in the
    year. Each is converted to rupees only when a rate for that exact date was supplied;
    otherwise the date is listed under ``rates_needed``.
    """
    rates = rates or {}
    start, end = date(calendar_year, 1, 1), date(calendar_year, 12, 31)
    by_symbol: dict[str, list[dict]] = {}
    for t in trades:
        by_symbol.setdefault(t["symbol"].upper(), []).append(t)
    rows, needed = [], set()

    def convert(amount: Optional[float], day: Optional[date]) -> Optional[float]:
        if amount is None or day is None:
            return None
        if day in rates:
            return round(amount * rates[day], 2)
        needed.add(day)
        return None

    for symbol, items in sorted(by_symbol.items()):
        items = sorted(items, key=lambda t: t["date"])
        events = [(t["date"], float(t["quantity"]) * (1 if t["side"] == "buy" else -1)) for t in items if t["date"] <= end]
        held_at_start = _shares_on(date(calendar_year - 1, 12, 31), events)
        bought_in_year = sum(q for d, q in events if start <= d and q > 0)
        if held_at_start <= 0 and bought_in_year <= 0:
            continue
        buys = [t for t in items if t["side"] == "buy" and t["date"] <= end]
        first_buy = buys[0]["date"] if buys else None
        # Cost of everything bought up to the year end (shares sold in earlier years are a simplification the caller is told about).
        initial = sum(float(t["quantity"]) * float(t["price"]) for t in buys)
        proceeds = sum(float(t["quantity"]) * float(t["price"]) for t in items if t["side"] == "sell" and start <= t["date"] <= end)

        dates, closes = prices.get(symbol, ([], []))
        peak_value, peak_date, closing_value, closing_date = None, None, None, None
        for d, c in zip(dates, closes):
            if not (start <= d <= end):
                continue
            value = _shares_on(d, events) * c
            if peak_value is None or value > peak_value:
                peak_value, peak_date = value, d
            closing_date = d
            closing_value = value
        shares_at_end = _shares_on(end, events)
        if shares_at_end <= 0:
            closing_value = 0.0
        rows.append({
            "symbol": symbol,
            "date_of_first_acquisition": first_buy.isoformat() if first_buy else None,
            "shares_at_year_end": shares_at_end,
            "initial_value_foreign": round(initial, 2),
            "initial_value_inr": convert(initial, first_buy) if len(buys) == 1 else None,
            "peak_value_foreign": None if peak_value is None else round(peak_value, 2),
            "peak_date": peak_date.isoformat() if peak_date else None,
            "peak_value_inr": convert(peak_value, peak_date),
            "closing_value_foreign": None if closing_value is None else round(closing_value, 2),
            "closing_date": closing_date.isoformat() if closing_date else None,
            "closing_value_inr": convert(closing_value, closing_date) if closing_value else (0.0 if closing_value == 0 else None),
            "sale_proceeds_foreign": round(proceeds, 2),
            "purchase_lots": [{"date": t["date"].isoformat(), "quantity": float(t["quantity"]), "cost_foreign": round(float(t["quantity"]) * float(t["price"]), 2),
                               "cost_inr": convert(float(t["quantity"]) * float(t["price"]), t["date"])} for t in buys],
            "price_history_available": bool(dates),
        })
    return {"calendar_year": calendar_year, "rows": rows, "rates_needed": sorted(d.isoformat() for d in needed)}
