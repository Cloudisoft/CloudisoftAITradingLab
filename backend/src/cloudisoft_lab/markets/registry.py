"""Per-market rules. A market not listed here, or not enabled, cannot be traded."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal
from zoneinfo import ZoneInfo

from cloudisoft_lab.domain.enums import MarketKind


@dataclass(frozen=True)
class TradingSession:
    tz: str
    open_time: dt.time
    close_time: dt.time
    weekdays: frozenset[int] = frozenset({0, 1, 2, 3, 4})

    def is_open(self, at: dt.datetime) -> bool:
        local = at.astimezone(ZoneInfo(self.tz))
        if local.weekday() not in self.weekdays:
            return False
        return self.open_time <= local.time() < self.close_time


ALWAYS_OPEN = None


@dataclass(frozen=True)
class MarketSpec:
    kind: MarketKind
    quote_currency: str
    session: TradingSession | None  # None == 24x7
    enabled_for_paper: bool
    enabled_for_live: bool
    allows_leverage: bool = False
    compliance_notes: tuple[str, ...] = field(default_factory=tuple)
    max_position_fraction: Decimal = Decimal("0.5")

    def is_open(self, at: dt.datetime) -> bool:
        # Exchange holidays are NOT modelled yet (TODO: holiday calendars per exchange).
        return True if self.session is None else self.session.is_open(at)


MARKETS: dict[MarketKind, MarketSpec] = {
    MarketKind.CRYPTO: MarketSpec(
        MarketKind.CRYPTO, "USDT", None, enabled_for_paper=True, enabled_for_live=False,
        compliance_notes=("India: 30% tax on VDA gains + 1% TDS; verify before live.",),
    ),
    MarketKind.IN_EQUITY: MarketSpec(
        MarketKind.IN_EQUITY, "INR",
        TradingSession("Asia/Kolkata", dt.time(9, 15), dt.time(15, 30)),
        enabled_for_paper=True, enabled_for_live=False,
        compliance_notes=("SEBI retail algo framework & broker API rules must be verified.",),
    ),
    MarketKind.IN_DERIVATIVES: MarketSpec(
        MarketKind.IN_DERIVATIVES, "INR",
        TradingSession("Asia/Kolkata", dt.time(9, 15), dt.time(15, 30)),
        enabled_for_paper=False, enabled_for_live=False,
        compliance_notes=("Derivatives use leverage; disabled by immutable policy initially.",),
    ),
    MarketKind.US_EQUITY: MarketSpec(
        MarketKind.US_EQUITY, "USD",
        TradingSession("America/New_York", dt.time(9, 30), dt.time(16, 0)),
        enabled_for_paper=True, enabled_for_live=False,
        compliance_notes=("Indian residents: LRS/FEMA limits apply.",),
    ),
    MarketKind.FUTURES: MarketSpec(MarketKind.FUTURES, "USD", None, False, False),
    MarketKind.OPTIONS: MarketSpec(MarketKind.OPTIONS, "USD", None, False, False),
    MarketKind.FOREX: MarketSpec(
        MarketKind.FOREX, "INR", None, False, False,
        compliance_notes=("RBI/FEMA: residents may only trade permitted INR pairs on recognised exchanges.",),
    ),
    MarketKind.PREDICTION: MarketSpec(
        MarketKind.PREDICTION, "USDC", None, False, False,
        compliance_notes=("Jurisdiction restrictions apply; legal review required.",),
    ),
}


@dataclass(frozen=True)
class Instrument:
    symbol: str
    market: MarketKind
    base: str
    quote: str
    min_qty: Decimal
    qty_step: Decimal
    min_notional: Decimal
    tick_size: Decimal


def get_market(kind: MarketKind) -> MarketSpec:
    return MARKETS[kind]
