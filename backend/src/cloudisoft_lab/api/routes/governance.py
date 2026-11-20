"""Agent Management, proposals (owner approvals), expansion, reports, settings, users."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from cloudisoft_lab.api.deps import LabDep, Operator, Owner, Users, Viewer, persist
from cloudisoft_lab.core.config import get_settings
from cloudisoft_lab.governance.proposals import (
    GovernanceError,
    Proposal,
    ProposalKind,
    ProposalStatus,
    assess_expansion,
)
from cloudisoft_lab.governance.revenue import CHECKLIST, RevenueComplianceError, RevenueOpportunity
from cloudisoft_lab.markets.registry import HOLIDAYS, MARKETS
from cloudisoft_lab.reports import build_report
from cloudisoft_lab.risk.policy import RiskConfig
from cloudisoft_lab.strategy.schema import StrategyDefinition
from cloudisoft_lab.survival.ledger import Entry

router = APIRouter(prefix="/api")


# ---------------- agents ----------------
@router.get("/agents")
async def agents(lab: LabDep) -> dict[str, object]:
    llm = lab.llm
    out = []
    for a in lab.agents.agents.values():
        cost = lab.ledger.cost_by("agent_id").get(a.agent_id, Decimal(0))
        out.append({"agent_id": a.agent_id, "name": a.name, "scope": a.scope, "status": a.status,
                    "builtin": a.builtin, "budget_usd": str(a.budget_usd), "spent_usd": str(cost),
                    "llm_budget_spent": str(llm.budget(a.agent_id).spent_usd) if llm and a.agent_id in llm.budgets else "0",
                    "tasks": a.tasks[-10:], "task_count": len(a.tasks), "approved_by": a.approved_by})
    return {"agents": out, "max_agents": 20, "replication": "only via owner-approved AGENT_SPAWN proposals"}


class AgentStatusBody(BaseModel):
    status: Literal["active", "paused", "retired"]


@router.post("/agents/{aid}/status")
async def agent_status(aid: str, body: AgentStatusBody, lab: LabDep, user: Owner, request: Request) -> dict[str, str]:
    if aid not in lab.agents.agents:
        raise HTTPException(404, "not found")
    if aid in ("risk_manager", "survival_manager") and body.status != "active":
        raise HTTPException(409, "risk and survival managers cannot be disabled")
    lab.agents.set_status(aid, body.status)
    lab.audit.record("agent.status", user["sub"], {"agent": aid, "status": body.status})
    await persist(request)
    return {"agent_id": aid, "status": body.status}


class SpawnBody(BaseModel):
    agent_id: str = Field(pattern=r"^[a-z][a-z0-9_]{2,40}$")
    name: str = Field(max_length=80)
    scope: str = Field(max_length=500)
    budget_usd: Decimal = Field(ge=0, le=Decimal(1000))
    justification: str = Field(max_length=2000)


@router.post("/agents/proposals")
async def propose_agent(body: SpawnBody, lab: LabDep, user: Operator, request: Request) -> dict[str, str]:
    r = lab.survival_report()
    p = lab.board.submit(Proposal(ProposalKind.AGENT_SPAWN, f"New agent: {body.name}",
                                  body.model_dump(mode="json"),
                                  {"survival_state": r.state, "survival_balance": str(r.survival_balance)}, user["sub"]))
    await persist(request)
    return {"proposal_id": p.id}


# ---------------- expansion ----------------
class ExpansionBody(BaseModel):
    title: str = Field(max_length=120)
    description: str = Field(max_length=2000)
    initial_cost: Decimal = Field(ge=0)
    monthly_cost: Decimal = Field(ge=0)
    expected_monthly_benefit: Decimal = Field(ge=0)
    risk: str = Field(max_length=1000)


def _assess(lab: LabDep, b: ExpansionBody) -> dict[str, object]:
    r = lab.survival_report()
    a = assess_expansion(state=r.state, survival_balance=r.survival_balance, daily_burn=r.daily_burn,
                         initial_cost=b.initial_cost, monthly_cost=b.monthly_cost,
                         expected_monthly_benefit=b.expected_monthly_benefit)
    return {k: (str(v) if isinstance(v, Decimal) else v) for k, v in a.__dict__.items()}


@router.post("/expansion/assess")
async def expansion_assess(body: ExpansionBody, lab: LabDep) -> dict[str, object]:
    return _assess(lab, body)


@router.post("/expansion/proposals")
async def expansion_propose(body: ExpansionBody, lab: LabDep, user: Operator, request: Request) -> dict[str, object]:
    a = _assess(lab, body)
    if not a["eligible"]:
        raise HTTPException(409, {"not_eligible": a["reasons"]})
    p = lab.board.submit(Proposal(ProposalKind.EXPANSION, body.title, body.model_dump(mode="json"), a, user["sub"]))
    await lab.notifier.notify("proposal", f"Expansion proposed: {body.title}")
    await persist(request)
    return {"proposal_id": p.id, "assessment": a}


# ---------------- proposals ----------------
@router.get("/proposals")
async def proposals(lab: LabDep) -> dict[str, object]:
    return {"proposals": [p.as_dict() for p in sorted(lab.board.proposals.values(), key=lambda x: x.created_at,
                                                         reverse=True)]}


class ProposalDecision(BaseModel):
    approve: bool
    note: str = Field(default="", max_length=1000)


@router.post("/proposals/{pid}/decision")
async def decide(pid: str, body: ProposalDecision, lab: LabDep, user: Owner, request: Request) -> dict[str, object]:
    if pid not in lab.board.proposals:
        raise HTTPException(404, "not found")
    try:
        p = lab.board.decide(pid, "owner", body.approve, body.note)
        if p.status == ProposalStatus.APPROVED:
            _apply(lab, p, user["sub"])
    except (GovernanceError, ValueError, KeyError) as exc:
        raise HTTPException(409, str(exc)) from exc
    lab.audit.record("proposal.decision", user["sub"], {"id": pid, "kind": p.kind, "status": p.status})
    await persist(request)
    return p.as_dict()


def _apply(lab: LabDep, p: Proposal, actor: str) -> None:
    pl = p.payload
    match p.kind:
        case ProposalKind.STRATEGY_IMPROVEMENT:
            d = StrategyDefinition.model_validate(pl["definition"])
            lab.strategies.add_version(str(pl["strategy_id"]), d, "agent:improvement_researcher",
                                       f"approved proposal {p.id[:8]} by {actor}")
        case ProposalKind.STRATEGY_PROMOTION:
            lab.strategies.set_status(str(pl["strategy_id"]), "paper")
        case ProposalKind.AGENT_SPAWN:
            lab.agents.spawn_from(p)
            if lab.llm:
                lab.llm.budget(str(pl["agent_id"])).limit_usd = Decimal(str(pl["budget_usd"]))
        case ProposalKind.RISK_LIMIT_CHANGE:
            lab.set_risk_config(RiskConfig.model_validate(pl["config"]), actor)
        case ProposalKind.REVENUE_OPPORTUNITY:
            lab.revenue.items[str(pl["opportunity_id"])].status = "approved"
        case ProposalKind.EXPANSION | ProposalKind.CODE_CHANGE:
            pass  # recorded decision; the owner performs the purchase / merges the reviewed PR
    lab.board.mark_applied(p.id)


# ---------------- reports ----------------
@router.get("/reports/{period}")
async def report(period: Literal["daily", "monthly"], lab: LabDep) -> dict[str, object]:
    return build_report(lab, period)


@router.get("/notifications")
async def notifications(lab: LabDep) -> dict[str, object]:
    return {"notifications": lab.notifier.sent[-200:][::-1], "webhook_configured": bool(lab.notifier.webhook_url)}


# ---------------- settings ----------------
@router.get("/settings")
async def settings_view(lab: LabDep, user: Viewer) -> dict[str, object]:
    s = get_settings()
    return {
        "risk_config": lab.risk.config.model_dump(mode="json"),
        "survival_config": lab.survival.config.model_dump(mode="json"),
        "paper": {"symbols": s.paper_symbols, "interval": s.paper_interval, "loop_seconds": s.paper_loop_seconds,
                  "market_data_source": s.market_data_source},
        "live_trading_gates": {
            "CLAB_LIVE_TRADING_ENABLED": s.live_trading_enabled,
            "CLAB_OWNER_LIVE_TRADING_APPROVED": s.owner_live_trading_approved,
            "broker_connected": False, "api_permissions_verified": False, "account_verified": False,
            "compliance_checked": False, "paper_tests_passed": False, "kill_switch_tested": False,
            "markets_enabled_for_live": [k for k, m in MARKETS.items() if m.enabled_for_live],
        },
        "holidays": {k: sorted(str(d) for d in v) for k, v in HOLIDAYS.items()},
        "llm_available": bool(lab.llm and lab.llm.available),
    }


class RiskChange(BaseModel):
    config: RiskConfig
    justification: str = Field(max_length=1000)


@router.put("/settings/risk")
async def set_risk(body: RiskChange, lab: LabDep, user: Owner, request: Request) -> dict[str, object]:
    """Owner edits apply directly (the owner IS the approver); every change is audited."""
    lab.set_risk_config(body.config, user["sub"])
    await persist(request)
    return lab.risk.config.model_dump(mode="json")


@router.post("/settings/risk/proposals")
async def propose_risk(body: RiskChange, lab: LabDep, user: Operator, request: Request) -> dict[str, str]:
    p = lab.board.submit(Proposal(ProposalKind.RISK_LIMIT_CHANGE, "Risk limit change",
                                  {"config": body.config.model_dump(mode="json")},
                                  {"current": lab.risk.config.model_dump(mode="json"),
                                   "justification": body.justification}, user["sub"]))
    await persist(request)
    return {"proposal_id": p.id}


class HolidayBody(BaseModel):
    exchange: Literal["NSE", "NYSE"]
    dates: list[dt.date] = Field(max_length=60)


@router.put("/settings/holidays")
async def set_holidays(body: HolidayBody, lab: LabDep, user: Owner) -> dict[str, object]:
    HOLIDAYS[body.exchange] = set(body.dates)
    lab.audit.record("settings.holidays", user["sub"], {"exchange": body.exchange, "count": len(body.dates)})
    return {"exchange": body.exchange, "dates": sorted(str(d) for d in body.dates)}


# ---------------- users & 2FA ----------------
@router.get("/users")
async def users_list(users: Users, user: Owner) -> dict[str, object]:
    return {"users": await users.list_users()}


class NewUser(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+$", max_length=255)
    password: str = Field(min_length=12, max_length=200)
    role: Literal["operator", "viewer"]


@router.post("/users")
async def users_create(body: NewUser, users: Users, user: Owner, lab: LabDep) -> dict[str, str]:
    try:
        await users.create_user(body.email, body.password, body.role)
    except Exception as exc:
        raise HTTPException(409, str(exc)) from exc
    lab.audit.record("user.created", user["sub"], {"email": body.email, "role": body.role})
    return {"created": body.email}


@router.post("/users/me/totp")
async def totp_begin(users: Users, user: Viewer) -> dict[str, str]:
    try:
        secret, uri = await users.begin_totp(user["sub"])
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"secret": secret, "otpauth_uri": uri, "next": "POST /api/users/me/totp/confirm with secret + code"}


class TotpConfirm(BaseModel):
    secret: str = Field(min_length=16, max_length=64)
    code: str = Field(pattern=r"^\d{6}$")


@router.post("/users/me/totp/confirm")
async def totp_confirm(body: TotpConfirm, users: Users, user: Viewer) -> dict[str, bool]:
    if not await users.confirm_totp(user["sub"], body.secret, body.code):
        raise HTTPException(422, "invalid code")
    return {"totp_enabled": True}


@router.get("/security/events")
async def security_events(users: Users, user: Owner) -> dict[str, object]:
    return {"events": await users.security_events()}


# ---------------- revenue opportunities ----------------
def _opp(o: RevenueOpportunity) -> dict[str, object]:
    return {k: (str(v) if isinstance(v, Decimal) else v) for k, v in o.__dict__.items()} | {"score": o.score()}


@router.get("/revenue")
async def revenue(lab: LabDep) -> dict[str, object]:
    return {"opportunities": [_opp(o) for o in lab.revenue.items.values()], "compliance_checklist": CHECKLIST,
            "verified_external_revenue": str(lab.ledger.summary()["verified_external_revenue"])}


class OppBody(BaseModel):
    name: str = Field(max_length=120)
    description: str = Field(max_length=2000)
    target_customers: str = Field(max_length=500)
    delivery_cost_monthly: Decimal = Field(ge=0)
    expected_revenue_monthly: Decimal = Field(ge=0)
    setup_cost: Decimal = Field(default=Decimal(0), ge=0)


@router.post("/revenue")
async def add_opportunity(body: OppBody, lab: LabDep, user: Operator, request: Request) -> dict[str, object]:
    try:
        o = lab.revenue.add(RevenueOpportunity(**body.model_dump()))
    except RevenueComplianceError as exc:
        raise HTTPException(422, f"compliance: {exc}") from exc
    await persist(request)
    return _opp(o)


@router.post("/revenue/{oid}/propose")
async def propose_opportunity(oid: str, lab: LabDep, user: Operator, request: Request) -> dict[str, str]:
    o = lab.revenue.items.get(oid)
    if o is None:
        raise HTTPException(404, "not found")
    o.status = "proposed"
    p = lab.board.submit(Proposal(ProposalKind.REVENUE_OPPORTUNITY, f"Revenue: {o.name}", {"opportunity_id": oid},
                                  {"score": o.score(), "checklist": list(CHECKLIST)}, user["sub"]))
    await persist(request)
    return {"proposal_id": p.id}


class ReceiptBody(BaseModel):
    amount: Decimal = Field(gt=0)
    reference: str = Field(min_length=3, max_length=128, description="bank/payment-processor reference")
    payer: str = Field(max_length=200)


@router.post("/revenue/{oid}/receipts")
async def record_receipt(oid: str, body: ReceiptBody, lab: LabDep, user: Owner, request: Request) -> dict[str, str]:
    """Owner records money actually RECEIVED. Only this counts toward survival."""
    if oid not in lab.revenue.items:
        raise HTTPException(404, "not found")
    try:
        rec = lab.revenue.record_receipt(oid, body.amount, body.reference, body.payer)
    except RevenueComplianceError as exc:
        raise HTTPException(409, str(exc)) from exc
    lab.ledger.add(Entry.EXTERNAL_REVENUE, body.amount, reference=body.reference, memo=f"revenue:{oid}")
    lab.audit.record("revenue.received", user["sub"], rec | {"opportunity": oid})
    await persist(request)
    return rec
