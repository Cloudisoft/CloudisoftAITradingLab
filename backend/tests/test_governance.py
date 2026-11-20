from decimal import Decimal

import pytest

from cloudisoft_lab.domain.enums import SurvivalState
from cloudisoft_lab.governance.agents import MAX_AGENTS, AgentRegistry
from cloudisoft_lab.governance.proposals import (
    GovernanceError,
    Proposal,
    ProposalBoard,
    ProposalKind,
    ProposalStatus,
    assess_expansion,
)

D = Decimal


def spawn(i=0):
    return Proposal(ProposalKind.AGENT_SPAWN, "x", {"agent_id": f"extra_{i}", "budget_usd": "1"}, {}, "agent:y")


def test_only_owner_decides_and_once():
    b = ProposalBoard({"owner"})
    p = b.submit(spawn())
    with pytest.raises(GovernanceError):
        b.decide(p.id, "agent:y", True)
    b.decide(p.id, "owner", False)
    with pytest.raises(GovernanceError):
        b.decide(p.id, "owner", True)
    with pytest.raises(GovernanceError):
        b.mark_applied(p.id)


def test_code_change_requires_branch():
    with pytest.raises(GovernanceError):
        ProposalBoard({"owner"}).submit(Proposal(ProposalKind.CODE_CHANGE, "x", {}, {}, "agent"))


def test_no_uncontrolled_replication():
    reg, b = AgentRegistry(), ProposalBoard({"owner"})
    with pytest.raises(GovernanceError):
        reg.spawn_from(b.submit(spawn()))  # pending, not approved
    n = len(reg.agents)
    for i in range(MAX_AGENTS - n):
        p = b.submit(spawn(i))
        b.decide(p.id, "owner", True)
        reg.spawn_from(p)
    p = b.submit(spawn(999))
    b.decide(p.id, "owner", True)
    with pytest.raises(GovernanceError):
        reg.spawn_from(p)
    assert len(reg.agents) == MAX_AGENTS
    assert reg.agents["extra_0"].approved_by == "owner" and p.status == ProposalStatus.APPROVED


def test_expansion_assessment():
    kw = dict(survival_balance=D(300), daily_burn=D(1), initial_cost=D(50), monthly_cost=D(10),
              expected_monthly_benefit=D(40))
    a = assess_expansion(state=SurvivalState.PROFITABLE, **kw)
    assert a.eligible and a.payback_months == D(50) / D(30) and a.runway_days_after < a.runway_days_before
    assert not assess_expansion(state=SurvivalState.NORMAL, **kw).eligible
    assert not assess_expansion(state=SurvivalState.PROFITABLE, **{**kw, "initial_cost": D(290)}).eligible
    assert not assess_expansion(state=SurvivalState.PROFITABLE, **{**kw, "expected_monthly_benefit": D(5)}).eligible
