from __future__ import annotations

from enum import StrEnum


class TradingMode(StrEnum):
    PAPER = "paper"
    LIVE = "live"


class MarketKind(StrEnum):
    CRYPTO = "crypto"
    IN_EQUITY = "in_equity"
    IN_DERIVATIVES = "in_derivatives"
    US_EQUITY = "us_equity"
    FUTURES = "futures"
    OPTIONS = "options"
    FOREX = "forex"
    PREDICTION = "prediction"


class Side(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(StrEnum):
    PENDING_RISK = "pending_risk"
    REJECTED = "rejected"
    ACCEPTED = "accepted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"


class DataOrigin(StrEnum):
    """Every number shown to the owner must carry one of these labels."""

    ACTUAL = "actual"  # reported by a real provider
    SIMULATED = "simulated"  # paper trading / backtest
    ESTIMATED = "estimated"  # projections, fee estimates


class SurvivalState(StrEnum):
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW_COMPUTE = "LOW_COMPUTE"
    CRITICAL = "CRITICAL"
    DEAD = "DEAD"
    PROFITABLE = "PROFITABLE"
