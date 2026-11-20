"""Execution manager: the ONLY path from an order proposal to a broker.

It always runs the risk engine itself (callers cannot pass in a pre-made decision), routes
PAPER orders only to the paper broker and LIVE orders only to a live-capable connector, and
records every decision in the audit trail. Duplicate client_order_ids are rejected.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from cloudisoft_lab.audit import AuditTrail
from cloudisoft_lab.domain.enums import DataOrigin, OrderStatus, TradingMode
from cloudisoft_lab.domain.schemas import OrderRequest, OrderResult
from cloudisoft_lab.execution.paper_broker import PaperBroker
from cloudisoft_lab.interfaces import BrokerConnector
from cloudisoft_lab.risk.engine import RiskContext, RiskDecision, RiskEngine


class RoutingError(RuntimeError):
    pass


@dataclass
class ExecutionRouter:
    risk: RiskEngine
    paper: PaperBroker
    audit: AuditTrail
    live: BrokerConnector | None = None
    _seen: dict[str, OrderResult] = field(default_factory=dict)

    async def submit(self, order: OrderRequest, ctx: RiskContext) -> tuple[OrderResult, RiskDecision]:
        if order.client_order_id in self._seen:
            self.audit.record("order.duplicate", order.requested_by, {"id": order.client_order_id})
            prev = self._seen[order.client_order_id]
            return prev, RiskDecision(False, order.client_order_id, ["duplicate client_order_id"],
                                      {"idempotency": False}, prev.requested_quantity, 0, 0)  # type: ignore[arg-type]
        decision = self.risk.evaluate(order, ctx)
        self.audit.record("risk.decision", "risk_manager", decision.as_dict())
        if not decision.approved:
            res = OrderResult(client_order_id=order.client_order_id, status=OrderStatus.REJECTED,
                              origin=DataOrigin.SIMULATED if order.mode == TradingMode.PAPER else DataOrigin.ACTUAL,
                              symbol=order.symbol, side=order.side, requested_quantity=order.quantity,
                              reason="; ".join(decision.reasons))
            self._seen[order.client_order_id] = res
            return res, decision

        if order.mode == TradingMode.PAPER:
            res = await self.paper.place_order(order)
        else:
            if self.live is None or not getattr(self.live, "supports_live", False):
                raise RoutingError("no live-capable connector configured")
            if isinstance(self.live, PaperBroker):
                raise RoutingError("paper broker cannot be used as a live connector")
            res = await self.live.place_order(order)
        self._seen[order.client_order_id] = res
        self.audit.record("order.result", "execution_manager", res.model_dump(mode="json"))
        return res, decision
