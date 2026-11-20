"""Validated messages exchanged between agents, risk engine and execution."""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from cloudisoft_lab.domain.enums import (
    DataOrigin,
    MarketKind,
    OrderStatus,
    OrderType,
    Side,
    TradingMode,
)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class OrderRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    client_order_id: str = Field(default_factory=lambda: uuid.uuid4().hex, min_length=8, max_length=36)
    mode: TradingMode
    market: MarketKind
    symbol: str = Field(pattern=r"^[A-Z0-9_\-\.]{2,32}$")
    side: Side
    order_type: OrderType = OrderType.MARKET
    quantity: Decimal = Field(gt=0)
    limit_price: Decimal | None = Field(default=None, gt=0)
    stop_loss: Decimal | None = Field(default=None, gt=0)
    take_profit: Decimal | None = Field(default=None, gt=0)
    strategy_id: str | None = None
    requested_by: str = "agent"
    created_at: dt.datetime = Field(default_factory=_now)

    @field_validator("limit_price")
    @classmethod
    def _limit_needs_price(cls, v: Decimal | None, info):  # type: ignore[no-untyped-def]
        if info.data.get("order_type") == OrderType.LIMIT and v is None:
            raise ValueError("limit orders require limit_price")
        return v


class Fill(BaseModel):
    price: Decimal
    quantity: Decimal
    fee: Decimal
    fee_currency: str
    at: dt.datetime = Field(default_factory=_now)


class OrderResult(BaseModel):
    client_order_id: str
    status: OrderStatus
    origin: DataOrigin
    symbol: str
    side: Side
    requested_quantity: Decimal
    filled_quantity: Decimal = Decimal(0)
    average_price: Decimal | None = None
    fees: Decimal = Decimal(0)
    fills: list[Fill] = Field(default_factory=list)
    provider_reference: str | None = None
    reason: str | None = None


class Balance(BaseModel):
    provider: str
    account_id: str
    currency: str
    available: Decimal
    total: Decimal
    origin: DataOrigin


class Position(BaseModel):
    symbol: str
    quantity: Decimal
    average_price: Decimal
    market_price: Decimal | None = None
    origin: DataOrigin

    @property
    def unrealised_pnl(self) -> Decimal:
        if self.market_price is None:
            return Decimal(0)
        return (self.market_price - self.average_price) * self.quantity


class FundingRecord(BaseModel):
    provider: str
    kind: str  # deposit | withdrawal
    currency: str
    amount: Decimal
    status: str
    provider_reference: str | None
    origin: DataOrigin
    at: dt.datetime = Field(default_factory=_now)


class AgentMessage(BaseModel):
    """Envelope for inter-agent communication. Research agents emit, never execute."""

    model_config = ConfigDict(frozen=True)

    message_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    sender: str
    recipient: str
    kind: str  # e.g. "signal", "analysis", "order_proposal", "risk_decision"
    payload: dict[str, object]
    created_at: dt.datetime = Field(default_factory=_now)
