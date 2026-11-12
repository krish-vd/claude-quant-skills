"""Capital gains for an Indian resident individual: FIFO lot matching,
short/long-term classification, 31-Jan-2018 grandfathering and special-rate tax.

Scope is deliberately narrow (see ``in_tax.json`` -> ``not_handled``). The
engine reports each bucket separately and does not set losses off between
buckets, because the order of set-off is the taxpayer's choice.
"""
from __future__ import annotations

import calendar
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Iterable, Optional

from . import rules
from .charges import D, Number

GRANDFATHER_CUTOFF = date(2018, 2, 1)  # acquired BEFORE this date qualifies


@dataclass(frozen=True)
class Trade:
    """One buy or sell. ``charges`` are brokerage and other transfer expenses
    EXCLUDING STT, which is not deductible when computing capital gains.
    Amounts are in INR (convert foreign trades before passing them in)."""

    trade_date: date
    symbol: str
    side: str
    quantity: Number
    price: Number
    asset_class: str = "listed_equity"
    charges: Number = 0


@dataclass
class RealisedLot:
    symbol: str
    asset_class: str
    quantity: Decimal
    buy_date: date
    sell_date: date
    sale_value: Decimal
    sale_expenses: Decimal
    actual_cost: Decimal
    cost_used: Decimal
    grandfathered: bool
    term: str  # "short" or "long"
    gain: Decimal
    fy: str


def add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    year, month = d.year + y, m + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def financial_year(d: date) -> str:
    start = d.year if d.month >= 4 else d.year - 1
    return f"{start}-{str(start + 1)[-2:]}"


def is_long_term(buy_date: date, sell_date: date, months: Optional[int]) -> bool:
    """Long-term means held for MORE than ``months`` months before the transfer.
    Bought 1 Jan 2025 with a 12-month rule: a sale on 1 Jan 2026 is short-term
    (held exactly 12 months), a sale on 2 Jan 2026 is long-term."""
    if months is None:
        return False
    return sell_date > add_months(buy_date, months)


def realised_gains(
    trades: Iterable[Trade],
    fmv_31jan2018: Optional[dict[str, Number]] = None,
) -> tuple[list[RealisedLot], list[str]]:
    """Match sells to buys FIFO per symbol. Returns (lots, warnings).

    Sells before the rulebook's coverage date still consume lots, so FIFO stays
    correct, but they are not reported.
    """
    book = rules.load("in_tax")
    classes = book["asset_classes"]
    coverage = date.fromisoformat(book["coverage_from"])
    fmv = {k.upper(): D(v) for k, v in (fmv_31jan2018 or {}).items()}
    warnings: list[str] = []
    skipped = 0

    ordered = sorted(trades, key=lambda t: (t.trade_date, 0 if t.side == "buy" else 1))
    open_lots: dict[str, deque] = defaultdict(deque)
    out: list[RealisedLot] = []

    for t in ordered:
        if t.asset_class not in classes:
            raise ValueError(f"unknown asset_class {t.asset_class!r}; use one of {sorted(classes)}")
        if t.side not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")
        qty, price, charges = D(t.quantity), D(t.price), D(t.charges)
        if qty <= 0 or price < 0:
            raise ValueError(f"{t.symbol} {t.trade_date}: quantity must be positive and price not negative")
        key = t.symbol.upper()
        if t.side == "buy":
            open_lots[key].append({"date": t.trade_date, "qty": qty, "unit_cost": price + charges / qty, "cls": t.asset_class})
            continue

        remaining = qty
        rule = classes[t.asset_class]
        while remaining > 0:
            if not open_lots[key]:
                raise ValueError(
                    f"{t.symbol}: sell of {qty} on {t.trade_date} exceeds the buys supplied "
                    f"(short by {remaining}). Add the missing purchase history."
                )
            lot = open_lots[key][0]
            take = min(remaining, lot["qty"])
            lot["qty"] -= take
            remaining -= take
            if lot["qty"] == 0:
                open_lots[key].popleft()
            if t.trade_date < coverage:
                skipped += 1
                continue

            sale_value = take * price
            sale_expenses = charges * take / qty
            actual_cost = take * lot["unit_cost"]
            cost_used, grandfathered = actual_cost, False
            if rule["grandfathering_31jan2018"] and lot["date"] < GRANDFATHER_CUTOFF:
                if key in fmv:
                    stepped = min(fmv[key] * take, sale_value)
                    if stepped > actual_cost:
                        cost_used, grandfathered = stepped, True
                else:
                    warnings.append(
                        f"{t.symbol}: bought before 1 Feb 2018 but no 31-Jan-2018 fair market value "
                        f"supplied; actual cost used, so the gain may be overstated."
                    )
            term = "long" if is_long_term(lot["date"], t.trade_date, rule["long_term_after_months"]) else "short"
            out.append(
                RealisedLot(
                    symbol=key, asset_class=t.asset_class, quantity=take, buy_date=lot["date"],
                    sell_date=t.trade_date, sale_value=sale_value, sale_expenses=sale_expenses,
                    actual_cost=actual_cost, cost_used=cost_used, grandfathered=grandfathered,
                    term=term, gain=sale_value - sale_expenses - cost_used, fy=financial_year(t.trade_date),
                )
            )
    if skipped:
        warnings.append(
            f"{skipped} matched lot(s) were sold before {coverage.isoformat()} and are not reported: "
            f"earlier years are outside the rulebook's coverage."
        )
    return out, sorted(set(warnings))


@dataclass
class Bucket:
    asset_class: str
    term: str
    mode: str  # "special_rate" or "slab"
    gains: Decimal = Decimal(0)
    losses: Decimal = Decimal(0)
    rate: Optional[Decimal] = None
    exemption: Decimal = Decimal(0)
    section: str = ""
    tax: Decimal = Decimal(0)

    @property
    def net(self) -> Decimal:
        return self.gains + self.losses


@dataclass
class YearSummary:
    fy: str
    buckets: list[Bucket] = field(default_factory=list)
    tax_before_cess: Decimal = Decimal(0)
    cess: Decimal = Decimal(0)
    slab_income: Decimal = Decimal(0)
    notes: list[str] = field(default_factory=list)

    @property
    def tax_with_cess(self) -> Decimal:
        return self.tax_before_cess + self.cess

    def to_dict(self) -> dict:
        return {
            "fy": self.fy,
            "buckets": [
                {
                    "asset_class": b.asset_class, "term": b.term, "mode": b.mode,
                    "gains": str(b.gains), "losses": str(b.losses), "net": str(b.net),
                    "rate": None if b.rate is None else str(b.rate),
                    "exemption": str(b.exemption), "section": b.section, "tax": str(b.tax),
                }
                for b in self.buckets
            ],
            "special_rate_tax_before_cess": str(self.tax_before_cess),
            "cess": str(self.cess),
            "special_rate_tax_with_cess": str(self.tax_with_cess),
            "gains_taxed_at_slab_rates": str(self.slab_income),
            "notes": self.notes,
        }


def summarise(lots: Iterable[RealisedLot]) -> list[YearSummary]:
    """Per financial year: net gain per bucket and tax on the special-rate buckets."""
    book = rules.load("in_tax")
    classes = book["asset_classes"]
    cess_rate = Decimal(book["cess_rate"])
    by_year: dict[str, dict[tuple[str, str], Bucket]] = defaultdict(dict)

    for lot in lots:
        rule = classes[lot.asset_class]
        spec = rule["ltcg"] if lot.term == "long" else rule["stcg"]
        key = (lot.asset_class, lot.term)
        bucket = by_year[lot.fy].get(key)
        if bucket is None:
            bucket = Bucket(lot.asset_class, lot.term, spec["mode"])
            if spec["mode"] == "special_rate":
                bucket.rate = Decimal(spec["rate"])
                bucket.exemption = Decimal(spec.get("exemption_per_fy", "0"))
                bucket.section = f"s.{spec['section_2025']} (ITA 2025) / s.{spec['section_1961']} (ITA 1961)"
            by_year[lot.fy][key] = bucket
        if lot.gain >= 0:
            bucket.gains += lot.gain
        else:
            bucket.losses += lot.gain

    summaries: list[YearSummary] = []
    for fy in sorted(by_year):
        summary = YearSummary(fy)
        has_loss = False
        for key in sorted(by_year[fy]):
            b = by_year[fy][key]
            if b.net < 0:
                has_loss = True
            if b.mode == "special_rate":
                taxable = max(Decimal(0), b.net - b.exemption)
                b.tax = taxable * (b.rate or Decimal(0))
                summary.tax_before_cess += b.tax
            elif b.net > 0:
                summary.slab_income += b.net
            summary.buckets.append(b)
        summary.cess = summary.tax_before_cess * cess_rate
        summary.notes.append("Surcharge is not included. Cess is 4% of the tax.")
        if summary.slab_income:
            summary.notes.append("Slab-rate gains are added to your other income; their tax depends on your slab and is not computed here.")
        if has_loss:
            summary.notes.append(
                "A bucket has a net loss. Losses are NOT set off here: a short-term loss can be set off "
                "against any capital gain, a long-term loss only against long-term gains, and unused "
                "losses carry forward 8 years if the return is filed on time."
            )
        summaries.append(summary)
    return summaries
