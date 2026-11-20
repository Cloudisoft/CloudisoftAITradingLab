"""AI Profit Manager: recommends (never executes) withdrawals of realised profit."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

from cloudisoft_lab.core.money import ZERO, round_money


class WithdrawalPolicy(BaseModel):
    preserve_original_capital: bool = True
    profit_withdrawal_fraction: Decimal = Field(default=Decimal("0.5"), ge=0, le=1)
    min_trading_reserve: Decimal = Field(default=Decimal("5"), ge=0)
    operational_reserve: Decimal = Field(default=Decimal("0"), ge=0)


@dataclass(frozen=True)
class WithdrawalRecommendation:
    recommended_amount: Decimal
    remaining_capital: Decimal
    reasons: list[str]
    label: str = "RECOMMENDATION ONLY — owner approval required for any real withdrawal"


def recommend_withdrawal(
    *, original_capital: Decimal, current_cash: Decimal, realised_net_profit: Decimal,
    locked_in_open_positions: Decimal, outstanding_obligations: Decimal, policy: WithdrawalPolicy,
) -> WithdrawalRecommendation:
    reasons: list[str] = []
    if realised_net_profit <= 0:
        return WithdrawalRecommendation(ZERO, current_cash, ["no realised net profit to withdraw"])
    free_cash = current_cash - outstanding_obligations  # cash in open positions is not in current_cash
    floor = max(policy.min_trading_reserve, original_capital if policy.preserve_original_capital else ZERO)
    floor += policy.operational_reserve
    headroom = free_cash - floor
    target = realised_net_profit * policy.profit_withdrawal_fraction
    amount = max(ZERO, min(target, headroom))
    if amount < target:
        reasons.append("capped to keep reserves / original capital intact")
    if locked_in_open_positions > 0:
        reasons.append("funds in open positions excluded")
    amount = round_money(amount, 2)
    return WithdrawalRecommendation(amount, current_cash - amount, reasons or ["within policy"])


class ApprovalStatus(StrEnum):
    PENDING = "pending_owner_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUBMITTED = "submitted"
    FAILED = "failed"
    COMPLETED = "completed"


REQUIRED_CONFIRMATIONS = ("provider", "asset", "amount", "destination", "network", "fees", "final_details")


@dataclass
class WithdrawalRequest:
    provider: str
    asset: str
    amount: Decimal
    destination: str
    network: str | None
    estimated_fee: Decimal
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    status: ApprovalStatus = ApprovalStatus.PENDING
    confirmations: dict[str, bool] = field(default_factory=dict)
    approved_by: str | None = None
    provider_reference: str | None = None
    history: list[str] = field(default_factory=list)


class WithdrawalWorkflowError(RuntimeError):
    pass


class WithdrawalWorkflow:
    """State machine. Nothing here can move money; it only gates a provider call made elsewhere."""

    def __init__(self, owner_ids: set[str]) -> None:
        self.owner_ids = owner_ids
        self.requests: dict[str, WithdrawalRequest] = {}

    def create(self, req: WithdrawalRequest, available: Decimal) -> WithdrawalRequest:
        if req.amount <= 0:
            raise WithdrawalWorkflowError("amount must be positive")
        if req.amount + req.estimated_fee > available:
            raise WithdrawalWorkflowError("amount + fee exceeds withdrawable balance")
        if not req.destination.strip():
            raise WithdrawalWorkflowError("destination required")
        self.requests[req.request_id] = req
        req.history.append("created")
        return req

    def approve(self, request_id: str, owner_id: str, confirmations: dict[str, bool]) -> WithdrawalRequest:
        req = self.requests[request_id]
        if owner_id not in self.owner_ids:
            raise WithdrawalWorkflowError("only the owner can approve withdrawals")
        if req.status != ApprovalStatus.PENDING:
            raise WithdrawalWorkflowError(f"cannot approve from {req.status}")
        required = [c for c in REQUIRED_CONFIRMATIONS if not (c == "network" and req.network is None)]
        missing = [c for c in required if not confirmations.get(c)]
        if missing:
            raise WithdrawalWorkflowError(f"missing confirmations: {missing}")
        req.confirmations, req.approved_by, req.status = confirmations, owner_id, ApprovalStatus.APPROVED
        req.history.append(f"approved by {owner_id}")
        return req

    def reject(self, request_id: str, owner_id: str) -> WithdrawalRequest:
        req = self.requests[request_id]
        req.status = ApprovalStatus.REJECTED
        req.history.append(f"rejected by {owner_id}")
        return req

    def mark_submitted(self, request_id: str, provider_reference: str | None) -> WithdrawalRequest:
        req = self.requests[request_id]
        if req.status != ApprovalStatus.APPROVED:
            raise WithdrawalWorkflowError("withdrawal not approved by owner")
        req.status, req.provider_reference = ApprovalStatus.SUBMITTED, provider_reference
        req.history.append("submitted")
        return req

    def mark_result(self, request_id: str, ok: bool, provider_reference: str | None = None) -> WithdrawalRequest:
        req = self.requests[request_id]
        if req.status != ApprovalStatus.SUBMITTED:
            raise WithdrawalWorkflowError("result only valid after submission")
        if ok and not (provider_reference or req.provider_reference):
            raise WithdrawalWorkflowError("cannot mark completed without a provider reference")
        req.status = ApprovalStatus.COMPLETED if ok else ApprovalStatus.FAILED
        req.provider_reference = provider_reference or req.provider_reference
        req.history.append(req.status.value)
        return req
