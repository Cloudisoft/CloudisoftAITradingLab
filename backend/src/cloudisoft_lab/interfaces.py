"""Provider-agnostic interfaces. Every integration implements these, so adapters are swappable."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import Protocol, runtime_checkable

import pandas as pd

from cloudisoft_lab.domain.enums import DataOrigin
from cloudisoft_lab.domain.schemas import Balance, FundingRecord, OrderRequest, OrderResult, Position
from cloudisoft_lab.markets.registry import Instrument


@runtime_checkable
class MarketDataProvider(Protocol):
    name: str
    origin: DataOrigin

    async def get_candles(self, symbol: str, interval: str, limit: int) -> pd.DataFrame:
        """Return OHLCV indexed by UTC open time; only *closed* candles."""
        ...

    async def get_instrument(self, symbol: str) -> Instrument: ...


@runtime_checkable
class AccountConnector(Protocol):
    name: str

    async def get_balances(self) -> Sequence[Balance]: ...


@runtime_checkable
class OrderManagementInterface(Protocol):
    async def place_order(self, order: OrderRequest) -> OrderResult: ...
    async def cancel_order(self, client_order_id: str) -> OrderResult: ...
    async def open_orders(self) -> Sequence[OrderResult]: ...


@runtime_checkable
class PortfolioInterface(Protocol):
    async def get_positions(self) -> Sequence[Position]: ...


@runtime_checkable
class BrokerConnector(AccountConnector, OrderManagementInterface, PortfolioInterface, Protocol):
    """Full broker/exchange adapter (ExchangeConnector is an alias for crypto venues)."""

    supports_live: bool


ExchangeConnector = BrokerConnector


@runtime_checkable
class FundingInterface(Protocol):
    """Read-only history + links to the provider's *official* funding UI.

    Cloudisoft never custodies funds and never initiates deposits.
    """

    async def deposit_history(self) -> Sequence[FundingRecord]: ...
    def official_funding_url(self) -> str | None: ...


@runtime_checkable
class WithdrawalInterface(Protocol):
    async def withdrawal_history(self) -> Sequence[FundingRecord]: ...
    async def submit_owner_approved_withdrawal(self, approval_id: str) -> FundingRecord: ...


@runtime_checkable
class RiskManagementInterface(Protocol):
    def evaluate(self, order: OrderRequest, context: object) -> object: ...


__all__ = [
    "AccountConnector",
    "BrokerConnector",
    "Decimal",
    "ExchangeConnector",
    "FundingInterface",
    "MarketDataProvider",
    "OrderManagementInterface",
    "PortfolioInterface",
    "RiskManagementInterface",
    "WithdrawalInterface",
]
