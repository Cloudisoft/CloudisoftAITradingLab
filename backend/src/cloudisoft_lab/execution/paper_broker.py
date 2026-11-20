"""Simulated broker. Everything it produces is labelled SIMULATED.

It refuses any order whose mode is not PAPER, so a paper order cannot reach a live
account and a live order cannot be silently "filled" in simulation.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass, field
from decimal import Decimal

from cloudisoft_lab.core.money import ZERO
from cloudisoft_lab.domain.enums import DataOrigin, OrderStatus, Side, TradingMode
from cloudisoft_lab.domain.schemas import Balance, Fill, FundingRecord, OrderRequest, OrderResult, Position


class PaperModeViolation(RuntimeError):
    pass


@dataclass
class _Pos:
    qty: Decimal = ZERO
    avg: Decimal = ZERO
    last_entry_notional: Decimal | None = None


@dataclass
class PaperBroker:
    starting_cash: Decimal
    quote_currency: str = "USDT"
    fee_rate: Decimal = Decimal("0.001")
    slippage: Decimal = Decimal("0.0005")
    name: str = "paper"
    supports_live: bool = False
    cash: Decimal = field(init=False)
    realised_pnl: Decimal = field(init=False, default=ZERO)
    fees_paid: Decimal = field(init=False, default=ZERO)
    last_closed_trade_pnl: Decimal | None = field(init=False, default=None)
    positions: dict[str, _Pos] = field(init=False, default_factory=dict)
    orders: dict[str, OrderResult] = field(init=False, default_factory=dict)
    funding: list[FundingRecord] = field(init=False, default_factory=list)
    marks: dict[str, Decimal] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        self.cash = self.starting_cash

    # ---- market prices -------------------------------------------------
    def mark(self, symbol: str, price: Decimal) -> None:
        self.marks[symbol] = price

    # ---- OrderManagementInterface -------------------------------------
    async def place_order(self, order: OrderRequest) -> OrderResult:
        if order.mode != TradingMode.PAPER:
            raise PaperModeViolation("PaperBroker only accepts PAPER orders")
        if order.client_order_id in self.orders:  # idempotency: replay returns original result
            return self.orders[order.client_order_id]
        ref = self.marks.get(order.symbol)
        if ref is None:
            return self._store(order, OrderStatus.REJECTED, reason="no market price available")
        px = ref * (1 + self.slippage) if order.side == Side.BUY else ref * (1 - self.slippage)
        if order.limit_price is not None and (
            (order.side == Side.BUY and px > order.limit_price)
            or (order.side == Side.SELL and px < order.limit_price)
        ):
            return self._store(order, OrderStatus.REJECTED, reason="limit not marketable (no resting book)")
        qty = order.quantity
        fee = px * qty * self.fee_rate
        pos = self.positions.setdefault(order.symbol, _Pos())
        if order.side == Side.BUY:
            if px * qty + fee > self.cash:
                return self._store(order, OrderStatus.REJECTED, reason="insufficient simulated funds")
            self.cash -= px * qty + fee
            pos.avg = (pos.avg * pos.qty + px * qty) / (pos.qty + qty)
            pos.qty += qty
            pos.last_entry_notional = px * qty
        else:
            if qty > pos.qty:
                return self._store(order, OrderStatus.REJECTED, reason="cannot sell more than held")
            self.cash += px * qty - fee
            pnl = (px - pos.avg) * qty - fee
            self.realised_pnl += (px - pos.avg) * qty
            self.last_closed_trade_pnl = pnl
            pos.qty -= qty
            if pos.qty == 0:
                pos.avg = ZERO
        self.fees_paid += fee
        fill = Fill(price=px, quantity=qty, fee=fee, fee_currency=self.quote_currency)
        return self._store(order, OrderStatus.FILLED, fill=fill)

    def _store(self, order: OrderRequest, status: OrderStatus, fill: Fill | None = None,
               reason: str | None = None) -> OrderResult:
        res = OrderResult(
            client_order_id=order.client_order_id, status=status, origin=DataOrigin.SIMULATED,
            symbol=order.symbol, side=order.side, requested_quantity=order.quantity,
            filled_quantity=fill.quantity if fill else ZERO,
            average_price=fill.price if fill else None, fees=fill.fee if fill else ZERO,
            fills=[fill] if fill else [], provider_reference=f"PAPER-{uuid.uuid4().hex[:12]}",
            reason=reason,
        )
        self.orders[order.client_order_id] = res
        return res

    async def cancel_order(self, client_order_id: str) -> OrderResult:
        res = self.orders[client_order_id]
        return res  # paper fills are immediate; nothing rests to cancel

    async def open_orders(self) -> list[OrderResult]:
        return []

    # ---- Account / Portfolio -------------------------------------------
    async def get_balances(self) -> list[Balance]:
        return [Balance(provider=self.name, account_id="paper-1", currency=self.quote_currency,
                        available=self.cash, total=self.equity(), origin=DataOrigin.SIMULATED)]

    async def get_positions(self) -> list[Position]:
        return [Position(symbol=s, quantity=p.qty, average_price=p.avg, market_price=self.marks.get(s),
                         origin=DataOrigin.SIMULATED) for s, p in self.positions.items() if p.qty > 0]

    def equity(self) -> Decimal:
        return self.cash + sum(
            (p.qty * self.marks.get(s, p.avg) for s, p in self.positions.items()), ZERO
        )

    def unrealised_pnl(self) -> Decimal:
        return sum(((self.marks.get(s, p.avg) - p.avg) * p.qty for s, p in self.positions.items()), ZERO)

    # ---- simulated funding ---------------------------------------------
    def simulate_deposit(self, amount: Decimal) -> FundingRecord:
        if amount <= 0:
            raise ValueError("amount must be positive")
        self.cash += amount
        rec = FundingRecord(provider=self.name, kind="deposit", currency=self.quote_currency, amount=amount,
                            status="completed", provider_reference=f"PAPER-DEP-{uuid.uuid4().hex[:8]}",
                            origin=DataOrigin.SIMULATED, at=dt.datetime.now(dt.UTC))
        self.funding.append(rec)
        return rec

    def simulate_withdrawal(self, amount: Decimal) -> FundingRecord:
        ok = 0 < amount <= self.cash
        if ok:
            self.cash -= amount
        rec = FundingRecord(provider=self.name, kind="withdrawal", currency=self.quote_currency, amount=amount,
                            status="completed" if ok else "failed", provider_reference=None,
                            origin=DataOrigin.SIMULATED)
        self.funding.append(rec)
        return rec
