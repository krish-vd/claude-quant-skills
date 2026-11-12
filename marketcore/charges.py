"""Trade cost calculators for India (NSE, BSE cash, MCX) and US equities.

All money is ``Decimal``. Every statutory rate comes from the rulebook with its
effective date; brokerage is supplied by the caller because it differs by
broker and plan.

Amounts are exact, unrounded. Contract notes round each levy (STT to the
nearest rupee, others to paise), so a real contract note can differ from these
figures by about a rupee per levy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_CEILING, Decimal
from typing import Optional, Union

from . import rules

Number = Union[Decimal, int, str, float]

IN_SEGMENTS = (
    "equity_delivery",
    "equity_intraday",
    "etf_delivery",
    "futures",
    "options",
    "commodity_futures",
    "commodity_options",
)
_AGRI_SEBI_RATE = Decimal("0.0000001")  # Rs 1 per crore, agricultural commodity futures


def D(value: Number) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


@dataclass(frozen=True)
class Brokerage:
    """Brokerage per order = flat + pct x turnover, capped at ``cap`` if set.

    "Rs 20 or 0.03%, whichever is lower" is ``Brokerage(pct="0.0003", cap="20")``.
    """

    flat: Number = 0
    pct: Number = 0
    cap: Optional[Number] = None

    def amount(self, turnover: Decimal) -> Decimal:
        value = D(self.flat) + D(self.pct) * turnover
        if self.cap is not None:
            value = min(value, D(self.cap))
        return value


@dataclass
class Line:
    levy: str
    amount: Decimal
    rate: Optional[Decimal]
    basis: str
    source_kind: str
    source_url: str


@dataclass
class LegCost:
    market: str
    segment: str
    side: str
    trade_date: date
    turnover: Decimal
    currency: str
    lines: list[Line] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def total(self) -> Decimal:
        return sum((ln.amount for ln in self.lines), Decimal(0))

    def amount(self, levy: str) -> Decimal:
        return sum((ln.amount for ln in self.lines if ln.levy == levy), Decimal(0))

    def to_dict(self) -> dict:
        return {
            "market": self.market,
            "segment": self.segment,
            "side": self.side,
            "trade_date": self.trade_date.isoformat(),
            "turnover": str(self.turnover),
            "currency": self.currency,
            "total": str(self.total),
            "lines": [
                {
                    "levy": ln.levy,
                    "amount": str(ln.amount),
                    "rate": None if ln.rate is None else str(ln.rate),
                    "basis": ln.basis,
                    "source_kind": ln.source_kind,
                    "source_url": ln.source_url,
                }
                for ln in self.lines
            ],
            "warnings": self.warnings,
        }


def india_leg(
    segment: str,
    side: str,
    price: Number,
    quantity: Number,
    trade_date: date,
    exchange: Optional[str] = None,
    brokerage: Brokerage = Brokerage(),
    agri: bool = False,
    dp_charge: Number = 0,
) -> LegCost:
    """Cost of one buy or sell order in India.

    ``price`` is the traded price (the premium for options) and ``quantity`` is
    the number of shares or units (lots x lot size for derivatives; lots x
    contract multiplier for MCX). ``dp_charge`` is the depository charge on a
    delivery sell, inclusive of GST, as charged by your broker.
    """
    if segment not in IN_SEGMENTS:
        raise ValueError(f"segment must be one of {IN_SEGMENTS}")
    if side not in ("buy", "sell"):
        raise ValueError("side must be 'buy' or 'sell'")
    if exchange is None:
        exchange = "MCX" if segment.startswith("commodity") else "NSE"
    price_d, qty_d = D(price), D(quantity)
    if price_d <= 0 or qty_d <= 0:
        raise ValueError("price and quantity must be positive")
    turnover = price_d * qty_d

    leg = LegCost("IN", segment, side, trade_date, turnover, "INR")
    found_exchange_txn = False
    gst_base = Decimal(0)
    gst_rate: Optional[rules.Rate] = None

    broker_fee = brokerage.amount(turnover)
    if broker_fee:
        leg.lines.append(Line("brokerage", broker_fee, None, "user supplied", "user", ""))
        gst_base += broker_fee

    for rate in rules.rates_for("in_charges", trade_date, segment, exchange):
        if rate.levy == "gst":
            gst_rate = rate
            continue
        if rate.side != "both" and rate.side != side:
            continue
        value = rate.rate
        if agri and rate.levy == "ctt":
            continue  # agricultural commodity futures are exempt from CTT
        if agri and rate.levy == "sebi_fee":
            value = _AGRI_SEBI_RATE
        amount = turnover * value
        leg.lines.append(Line(rate.levy, amount, value, rate.basis, rate.source_kind, rate.source_url))
        if rate.levy == "exchange_txn":
            found_exchange_txn = True
        if rate.levy in ("exchange_txn", "ipft", "sebi_fee"):
            gst_base += amount
        if rate.source_kind != "primary":
            leg.warnings.append(f"{rate.rule_id}: rate is from a {rate.source_kind} source")

    if not found_exchange_txn:
        raise rules.RuleNotCovered(
            f"No exchange transaction charge recorded for {segment} on {exchange}"
        )
    if gst_rate is not None and gst_base:
        leg.lines.append(
            Line("gst", gst_base * gst_rate.rate, gst_rate.rate, gst_rate.basis, gst_rate.source_kind, gst_rate.source_url)
        )
    dp = D(dp_charge)
    if dp:
        if not (segment in ("equity_delivery", "etf_delivery") and side == "sell"):
            raise ValueError("dp_charge applies only to delivery sells")
        leg.lines.append(Line("dp_charge", dp, None, "user supplied, GST inclusive", "user", ""))
    return leg


def india_option_exercise_stt(intrinsic_value_total: Number, trade_date: date) -> Line:
    """STT paid by the buyer when a bought option is exercised (expires in the money)."""
    for rate in rules.rates_for("in_charges", trade_date, "options_exercise"):
        if rate.levy == "stt":
            return Line(
                "stt_on_exercise",
                D(intrinsic_value_total) * rate.rate,
                rate.rate,
                rate.basis,
                rate.source_kind,
                rate.source_url,
            )
    raise rules.RuleNotCovered("No exercise STT rate found")


def _ceil_cent(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_CEILING)


def us_equity_leg(
    side: str,
    price: Number,
    shares: Number,
    trade_date: date,
    commission: Number = 0,
) -> LegCost:
    """Cost of one US stock or ETF order: commission plus SEC and FINRA fees on sells.

    Regulatory fees are rounded up to the cent, which is how brokers pass them on.
    """
    if side not in ("buy", "sell"):
        raise ValueError("side must be 'buy' or 'sell'")
    price_d, shares_d = D(price), D(shares)
    if price_d <= 0 or shares_d <= 0:
        raise ValueError("price and shares must be positive")
    turnover = price_d * shares_d
    leg = LegCost("US", "equity", side, trade_date, turnover, "USD")
    fee = D(commission)
    if fee:
        leg.lines.append(Line("commission", fee, None, "user supplied", "user", ""))
    for rate in rules.rates_for("us_charges", trade_date):
        if rate.side != "both" and rate.side != side:
            continue
        if rate.levy == "sec_fee":
            amount = _ceil_cent(turnover * rate.rate) if rate.rate else Decimal(0)
        elif rate.levy == "finra_taf":
            amount = shares_d * rate.rate
            if rate.max_per_trade is not None:
                amount = min(amount, rate.max_per_trade)
            amount = _ceil_cent(amount) if amount else Decimal(0)
        else:  # pragma: no cover - rulebook only has the two levies
            continue
        leg.lines.append(Line(rate.levy, amount, rate.rate, rate.basis, rate.source_kind, rate.source_url))
        if rate.source_kind != "primary":
            leg.warnings.append(f"{rate.rule_id}: rate is from a {rate.source_kind} source")
    return leg


@dataclass
class RoundTrip:
    buy: LegCost
    sell: LegCost
    quantity: Decimal

    @property
    def total_cost(self) -> Decimal:
        return self.buy.total + self.sell.total

    @property
    def gross_pnl(self) -> Decimal:
        return self.sell.turnover - self.buy.turnover

    @property
    def net_pnl(self) -> Decimal:
        return self.gross_pnl - self.total_cost

    @property
    def breakeven_move_per_unit(self) -> Decimal:
        """Price move per share or unit needed to cover the costs of this round trip."""
        return self.total_cost / self.quantity

    def to_dict(self) -> dict:
        return {
            "buy": self.buy.to_dict(),
            "sell": self.sell.to_dict(),
            "total_cost": str(self.total_cost),
            "gross_pnl": str(self.gross_pnl),
            "net_pnl": str(self.net_pnl),
            "breakeven_move_per_unit": str(self.breakeven_move_per_unit),
            "warnings": sorted(set(self.buy.warnings + self.sell.warnings)),
        }


def india_round_trip(
    segment: str,
    buy_price: Number,
    sell_price: Number,
    quantity: Number,
    buy_date: date,
    sell_date: Optional[date] = None,
    **kwargs,
) -> RoundTrip:
    dp = kwargs.pop("dp_charge", 0)
    buy = india_leg(segment, "buy", buy_price, quantity, buy_date, **kwargs)
    sell = india_leg(segment, "sell", sell_price, quantity, sell_date or buy_date, dp_charge=dp, **kwargs)
    return RoundTrip(buy, sell, D(quantity))


def us_round_trip(
    buy_price: Number,
    sell_price: Number,
    shares: Number,
    buy_date: date,
    sell_date: Optional[date] = None,
    commission: Number = 0,
) -> RoundTrip:
    buy = us_equity_leg("buy", buy_price, shares, buy_date, commission)
    sell = us_equity_leg("sell", sell_price, shares, sell_date or buy_date, commission)
    return RoundTrip(buy, sell, D(shares))
