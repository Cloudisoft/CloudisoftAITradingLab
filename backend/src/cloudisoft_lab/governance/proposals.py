"""Owner-approval governance for everything that changes risk, spend or capability.

Agents may *create* proposals; only the owner can approve. Applying a proposal is a separate,
explicit step that re-validates it. Nothing here purchases infrastructure or moves money:
"expansion" approval records the owner's decision, the purchase itself is done by the owner.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from cloudisoft_lab.core.money import ZERO
from cloudisoft_lab.domain.enums import SurvivalState


class ProposalKind(StrEnum):
    STRATEGY_IMPROVEMENT = "strategy_improvement"
    STRATEGY_PROMOTION = "strategy_promotion"  # research -> paper
    AGENT_SPAWN = "agent_spawn"
    EXPANSION = "expansion"
    RISK_LIMIT_CHANGE = "risk_limit_change"
    REVENUE_OPPORTUNITY = "revenue_opportunity"
    CODE_CHANGE = "code_change"  # must go through git review; board only tracks the decision


class ProposalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"


@dataclass
class Proposal:
    kind: ProposalKind
    title: str
    payload: dict[str, object]
    evidence: dict[str, object]
    created_by: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    status: ProposalStatus = ProposalStatus.PENDING
    created_at: str = field(default_factory=lambda: dt.datetime.now(dt.UTC).isoformat())
    decided_by: str | None = None
    decided_at: str | None = None
    note: str = ""

    def as_dict(self) -> dict[str, object]:
        return {k: (v.value if isinstance(v, StrEnum) else v) for k, v in self.__dict__.items()}


class GovernanceError(RuntimeError):
    pass


@dataclass
class ProposalBoard:
    owner_ids: set[str]
    proposals: dict[str, Proposal] = field(default_factory=dict)

    def submit(self, p: Proposal) -> Proposal:
        if p.kind == ProposalKind.CODE_CHANGE and not p.payload.get("branch"):
            raise GovernanceError("code changes must reference a reviewed git branch/PR")
        self.proposals[p.id] = p
        return p

    def decide(self, pid: str, owner: str, approve: bool, note: str = "") -> Proposal:
        p = self.proposals[pid]
        if owner not in self.owner_ids:
            raise GovernanceError("only the owner can decide proposals")
        if p.status != ProposalStatus.PENDING:
            raise GovernanceError(f"proposal already {p.status}")
        p.status = ProposalStatus.APPROVED if approve else ProposalStatus.REJECTED
        p.decided_by, p.decided_at, p.note = owner, dt.datetime.now(dt.UTC).isoformat(), note
        return p

    def mark_applied(self, pid: str) -> Proposal:
        p = self.proposals[pid]
        if p.status != ProposalStatus.APPROVED:
            raise GovernanceError("only approved proposals can be applied")
        p.status = ProposalStatus.APPLIED
        return p

    def pending(self) -> list[Proposal]:
        return [p for p in self.proposals.values() if p.status == ProposalStatus.PENDING]


@dataclass(frozen=True)
class ExpansionAssessment:
    eligible: bool
    reasons: list[str]
    initial_cost: Decimal
    monthly_cost: Decimal
    expected_monthly_benefit: Decimal
    reserve_required: Decimal
    available_after: Decimal
    runway_days_before: Decimal | None
    runway_days_after: Decimal | None
    payback_months: Decimal | None


def assess_expansion(*, state: SurvivalState, survival_balance: Decimal, daily_burn: Decimal,
                     initial_cost: Decimal, monthly_cost: Decimal, expected_monthly_benefit: Decimal,
                     reserve_days: Decimal = Decimal(30)) -> ExpansionAssessment:
    reasons = []
    if state != SurvivalState.PROFITABLE:
        reasons.append(f"state is {state}; expansion requires verified sustained profitability")
    reserve = daily_burn * reserve_days
    available_after = survival_balance - initial_cost
    new_burn = daily_burn + monthly_cost / 30
    if available_after < reserve:
        reasons.append("would breach the operating reserve")
    before = survival_balance / daily_burn if daily_burn > 0 else None
    after = available_after / new_burn if new_burn > 0 else None
    net_monthly = expected_monthly_benefit - monthly_cost
    payback = (initial_cost / net_monthly) if net_monthly > 0 else None
    if net_monthly <= 0:
        reasons.append("expected benefit does not cover the monthly cost")
    return ExpansionAssessment(not reasons, reasons or ["eligible to propose (owner approval still required)"],
                               initial_cost, monthly_cost, expected_monthly_benefit, reserve,
                               available_after, before, after, payback)


__all__ = ["ZERO"]
