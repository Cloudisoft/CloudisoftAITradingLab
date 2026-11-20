"""Persistent storage. Financial tables are append-oriented; nothing is hard-deleted."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from cloudisoft_lab.db.base import Base, IdMixin


class User(IdMixin, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="viewer")  # owner|operator|viewer
    totp_secret_enc: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Account(IdMixin, Base):
    __tablename__ = "accounts"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    provider: Mapped[str] = mapped_column(String(32))
    external_account_id: Mapped[str | None] = mapped_column(String(128))
    mode: Mapped[str] = mapped_column(String(8))  # paper|live
    base_currency: Mapped[str] = mapped_column(String(12))


class BrokerConnection(IdMixin, Base):
    __tablename__ = "broker_connections"
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    status: Mapped[str] = mapped_column(String(24), default="disconnected")
    permissions: Mapped[dict] = mapped_column(default=dict)  # verified trade/withdraw/ip flags
    last_verified_at: Mapped[dt.datetime | None]


class EncryptedCredential(IdMixin, Base):
    __tablename__ = "encrypted_credentials"
    connection_id: Mapped[str] = mapped_column(ForeignKey("broker_connections.id"))
    name: Mapped[str] = mapped_column(String(64))
    ciphertext: Mapped[str] = mapped_column(Text)
    masked: Mapped[str] = mapped_column(String(32))
    rotated_at: Mapped[dt.datetime | None]
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class InstrumentRow(IdMixin, Base):
    __tablename__ = "instruments"
    __table_args__ = (UniqueConstraint("provider", "symbol"),)
    provider: Mapped[str] = mapped_column(String(32))
    market: Mapped[str] = mapped_column(String(24))
    symbol: Mapped[str] = mapped_column(String(48))
    spec: Mapped[dict] = mapped_column(default=dict)


class MarketDataRef(IdMixin, Base):
    __tablename__ = "market_data_refs"
    provider: Mapped[str] = mapped_column(String(32))
    symbol: Mapped[str] = mapped_column(String(48))
    interval: Mapped[str] = mapped_column(String(8))
    uri: Mapped[str] = mapped_column(Text)  # parquet/object-store location
    start: Mapped[dt.datetime]
    end: Mapped[dt.datetime]


class Strategy(IdMixin, Base):
    __tablename__ = "strategies"
    name: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(16), default="research")  # research|paper|live|paused


class StrategyVersion(IdMixin, Base):
    __tablename__ = "strategy_versions"
    __table_args__ = (UniqueConstraint("strategy_id", "version"),)
    strategy_id: Mapped[str] = mapped_column(ForeignKey("strategies.id"))
    version: Mapped[int] = mapped_column(Integer)
    fingerprint: Mapped[str] = mapped_column(String(16))
    definition: Mapped[dict]
    author: Mapped[str] = mapped_column(String(64))  # owner | agent:<name>
    change_note: Mapped[str] = mapped_column(Text, default="")


class Backtest(IdMixin, Base):
    __tablename__ = "backtests"
    strategy_version_id: Mapped[str] = mapped_column(ForeignKey("strategy_versions.id"))
    dataset: Mapped[dict]
    assumptions: Mapped[dict]
    metrics: Mapped[dict]
    kind: Mapped[str] = mapped_column(String(24), default="in_sample")  # in_sample|oos|walk_forward|monte_carlo


class Order(IdMixin, Base):
    __tablename__ = "orders"
    client_order_id: Mapped[str] = mapped_column(String(36), unique=True)  # idempotency key
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    mode: Mapped[str] = mapped_column(String(8))
    symbol: Mapped[str] = mapped_column(String(48))
    side: Mapped[str] = mapped_column(String(4))
    quantity: Mapped[Decimal]
    status: Mapped[str] = mapped_column(String(24))
    origin: Mapped[str] = mapped_column(String(12))
    provider_reference: Mapped[str | None] = mapped_column(String(128))
    risk_decision_id: Mapped[str | None] = mapped_column(ForeignKey("risk_decisions.id"))
    strategy_version_id: Mapped[str | None] = mapped_column(ForeignKey("strategy_versions.id"))


class TradeRow(IdMixin, Base):
    __tablename__ = "trades"
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"))
    price: Mapped[Decimal]
    quantity: Mapped[Decimal]
    fee: Mapped[Decimal]
    fee_currency: Mapped[str] = mapped_column(String(12))
    origin: Mapped[str] = mapped_column(String(12))
    executed_at: Mapped[dt.datetime]


class PositionRow(IdMixin, Base):
    __tablename__ = "positions"
    __table_args__ = (UniqueConstraint("account_id", "symbol"),)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    symbol: Mapped[str] = mapped_column(String(48))
    quantity: Mapped[Decimal]
    average_price: Mapped[Decimal]
    origin: Mapped[str] = mapped_column(String(12))


class PortfolioSnapshot(IdMixin, Base):
    __tablename__ = "portfolio_snapshots"
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    equity: Mapped[Decimal]
    cash: Mapped[Decimal]
    realised_pnl: Mapped[Decimal]
    unrealised_pnl: Mapped[Decimal]
    origin: Mapped[str] = mapped_column(String(12))


class FundingTransaction(IdMixin, Base):
    """Deposits and withdrawals. Status only becomes completed with a provider reference."""

    __tablename__ = "funding_transactions"
    __table_args__ = (UniqueConstraint("idempotency_key"),)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    kind: Mapped[str] = mapped_column(String(12))  # deposit|withdrawal
    currency: Mapped[str] = mapped_column(String(12))
    amount: Mapped[Decimal]
    fee: Mapped[Decimal] = mapped_column(default=0)
    destination: Mapped[str | None] = mapped_column(Text)
    network: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32))
    provider_reference: Mapped[str | None] = mapped_column(String(128))
    origin: Mapped[str] = mapped_column(String(12))
    idempotency_key: Mapped[str] = mapped_column(String(64))
    owner_approval_id: Mapped[str | None] = mapped_column(ForeignKey("owner_approvals.id"))


class SurvivalLedgerRow(IdMixin, Base):
    """Also stores operating expenses and inference costs (kind column)."""

    __tablename__ = "survival_ledger"
    __table_args__ = (Index("ix_survival_kind_at", "kind", "at"),)
    kind: Mapped[str] = mapped_column(String(40))
    amount: Mapped[Decimal]
    currency: Mapped[str] = mapped_column(String(12), default="USD")
    origin: Mapped[str] = mapped_column(String(12))
    verified: Mapped[bool] = mapped_column(Boolean, default=True)
    at: Mapped[dt.datetime]
    agent_id: Mapped[str | None] = mapped_column(String(64))
    strategy_id: Mapped[str | None] = mapped_column(String(32))
    reference: Mapped[str | None] = mapped_column(String(128))
    memo: Mapped[str] = mapped_column(Text, default="")


class InferenceCost(IdMixin, Base):
    __tablename__ = "inference_costs"
    agent_id: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(64))
    input_tokens: Mapped[int] = mapped_column(Integer)
    output_tokens: Mapped[int] = mapped_column(Integer)
    cost_usd: Mapped[Decimal]


class SurvivalStateHistory(IdMixin, Base):
    __tablename__ = "survival_state_history"
    state: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str] = mapped_column(Text)
    snapshot: Mapped[dict]


class AgentRecord(IdMixin, Base):
    __tablename__ = "agents"
    name: Mapped[str] = mapped_column(String(64), unique=True)
    role: Mapped[str] = mapped_column(String(48))
    status: Mapped[str] = mapped_column(String(16), default="active")
    budget_usd: Mapped[Decimal] = mapped_column(default=0)
    task_scope: Mapped[dict] = mapped_column(default=dict)
    approved_by: Mapped[str | None] = mapped_column(String(32))


class AgentTask(IdMixin, Base):
    __tablename__ = "agent_tasks"
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"))
    kind: Mapped[str] = mapped_column(String(48))
    status: Mapped[str] = mapped_column(String(16))
    input: Mapped[dict] = mapped_column(default=dict)
    output: Mapped[dict] = mapped_column(default=dict)
    cost_usd: Mapped[Decimal] = mapped_column(default=0)


class RiskDecisionRow(IdMixin, Base):
    __tablename__ = "risk_decisions"
    client_order_id: Mapped[str] = mapped_column(String(36))
    approved: Mapped[bool] = mapped_column(Boolean)
    reasons: Mapped[dict]
    checks: Mapped[dict]


class OwnerApproval(IdMixin, Base):
    __tablename__ = "owner_approvals"
    subject: Mapped[str] = mapped_column(String(48))  # live_trading|withdrawal|expansion|risk_limit
    subject_id: Mapped[str] = mapped_column(String(64))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(12))
    confirmations: Mapped[dict] = mapped_column(default=dict)


class SecurityEvent(IdMixin, Base):
    __tablename__ = "security_events"
    kind: Mapped[str] = mapped_column(String(48))
    severity: Mapped[str] = mapped_column(String(12))
    detail: Mapped[dict] = mapped_column(default=dict)
    ip: Mapped[str | None] = mapped_column(String(64))


class AuditLog(Base):
    __tablename__ = "audit_logs"
    seq: Mapped[int] = mapped_column(Integer, primary_key=True)
    at: Mapped[str] = mapped_column(String(40))
    event: Mapped[str] = mapped_column(String(64))
    actor: Mapped[str] = mapped_column(String(64))
    data: Mapped[dict]
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64), unique=True)
