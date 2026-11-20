from __future__ import annotations

import datetime as dt
import hmac
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field

from cloudisoft_lab.api.deps import LabDep, Operator, Owner, Users, app_settings, persist
from cloudisoft_lab.backtest.engine import CostModel, run_backtest
from cloudisoft_lab.backtest.validation import monte_carlo
from cloudisoft_lab.core.config import get_settings
from cloudisoft_lab.core.security import create_access_token
from cloudisoft_lab.data.synthetic import REGIMES, make_ohlcv
from cloudisoft_lab.domain.enums import DataOrigin
from cloudisoft_lab.markets.registry import MARKETS
from cloudisoft_lab.risk.policy import IMMUTABLE
from cloudisoft_lab.strategy.schema import StrategyDefinition
from cloudisoft_lab.strategy.templates import TEMPLATES
from cloudisoft_lab.survival.ledger import EXPENSES, Entry

router = APIRouter()


def _s(d: dict[str, Decimal]) -> dict[str, str]:
    return {k: str(v) for k, v in d.items()}


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(lab: LabDep) -> dict[str, object]:
    return {"status": "ready", "ticks": lab.ticks, "last_error": lab.last_error}


@router.post("/api/auth/token")
async def token(form: Annotated[OAuth2PasswordRequestForm, Depends()], users: Users, request: Request,
                otp: Annotated[str | None, Form()] = None) -> dict[str, str]:
    ip = request.client.host if request.client else None
    user = await users.authenticate(form.username, form.password, otp, ip)
    if user is None:
        raise HTTPException(401, "invalid credentials or one-time code")
    s = app_settings(request)
    return {"access_token": create_access_token(user.email, user.role, s.jwt_secret.get_secret_value(),
                                                s.jwt_ttl_minutes), "token_type": "bearer", "role": user.role}


@router.get("/api/setup/status")
async def setup_status(users: Users) -> dict[str, bool]:
    return {"owner_exists": await users.owner_exists()}


class OwnerSetup(BaseModel):
    setup_code: str = Field(min_length=4, max_length=32)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+$", max_length=255)
    password: str = Field(min_length=12, max_length=200)


@router.post("/api/setup/owner")
async def setup_owner(body: OwnerSetup, users: Users, request: Request) -> dict[str, str]:
    code = getattr(request.app.state, "setup_code", None)
    if not code or not hmac.compare_digest(code, body.setup_code.strip().upper()):
        raise HTTPException(403, "invalid or expired setup code (see the API server log)")
    try:
        await users.create_owner(body.email, body.password)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    request.app.state.setup_code = None  # single use
    return {"created": body.email}


@router.get("/api/system/status")
async def status(lab: LabDep) -> dict[str, object]:
    s = get_settings()
    return {
        "mode": "paper", "live_trading_allowed": s.live_trading_allowed, "kill_switch": lab.kill_switch,
        "started_at": lab.started_at.isoformat(), "ticks": lab.ticks, "strategy": lab.active_strategy().name,
        "llm_available": bool(lab.llm and lab.llm.available), "last_error": lab.last_error,
        "immutable_policy": {k: str(v) for k, v in IMMUTABLE.__dict__.items()},
        "markets": {k: {"paper": m.enabled_for_paper, "live": m.enabled_for_live, "notes": m.compliance_notes}
                    for k, m in MARKETS.items()},
    }


class KillSwitchBody(BaseModel):
    engaged: bool = True


@router.post("/api/system/kill-switch")
async def kill_switch(body: KillSwitchBody, lab: LabDep, user: Operator, request: Request) -> dict[str, bool]:
    # any operator may ENGAGE; only the owner may release
    if not body.engaged and user["role"] != "owner":
        raise HTTPException(403, "only the owner can release the kill switch")
    lab.engage_kill_switch(user["sub"], body.engaged)
    await lab.notifier.notify("kill_switch", f"{'engaged' if body.engaged else 'released'} by {user['sub']}", "critical")
    await persist(request)
    return {"kill_switch": lab.kill_switch}


@router.get("/api/overview")
async def overview(lab: LabDep) -> dict[str, object]:
    p = lab.paper
    r = lab.survival_report()
    return {
        "label": DataOrigin.SIMULATED, "account_value": str(p.equity()), "available_capital": str(p.cash),
        "realised_pnl": str(p.realised_pnl), "unrealised_pnl": str(p.unrealised_pnl()),
        "fees_paid": str(p.fees_paid), "open_positions": len([1 for x in p.positions.values() if x.qty > 0]),
        "survival_state": r.state, "survival_runway_days": str(r.runway_days) if r.runway_days else None,
        "net_operating_profit": str(r.summary["net_operating_profit"]),
        "equity_curve": lab.equity_curve[-500:], "opportunities": lab.last_scan,
    }


@router.get("/api/paper/portfolio")
async def portfolio(lab: LabDep) -> dict[str, object]:
    return {"balances": [b.model_dump(mode="json") for b in await lab.paper.get_balances()],
            "positions": [p.model_dump(mode="json") for p in await lab.paper.get_positions()],
            "orders": [o.model_dump(mode="json") for o in list(lab.paper.orders.values())[-100:]],
            "funding": [f.model_dump(mode="json") for f in lab.paper.funding]}


class AmountBody(BaseModel):
    amount: Decimal = Field(gt=0, le=Decimal("1000000"))


@router.post("/api/paper/deposit")
async def paper_deposit(body: AmountBody, lab: LabDep, user: Owner, request: Request) -> dict[str, object]:
    rec = lab.paper.simulate_deposit(body.amount)
    lab.audit.record("paper.deposit", user["sub"], rec.model_dump(mode="json"))
    await persist(request)
    return rec.model_dump(mode="json")


@router.get("/api/survival")
async def survival(lab: LabDep) -> dict[str, object]:
    r = lab.survival_report()
    return {"state": r.state, "previous": r.previous, "survival_balance": str(r.survival_balance),
            "daily_burn": str(r.daily_burn), "monthly_burn_estimate": str(r.daily_burn * 30),
            "runway_days": str(r.runway_days) if r.runway_days is not None else None,
            "summary": _s(r.summary), "policy": r.policy.__dict__, "profitability": r.profitability,
            "reasons": r.reasons, "cost_by_agent": _s(lab.ledger.cost_by("agent_id")),
            "cost_by_strategy": _s(lab.ledger.cost_by("strategy_id")),
            "history": [(t.isoformat(), s, why) for t, s, why in lab.survival.history],
            "note": "Simulated trading P&L is excluded from survival economics."}


class LedgerBody(BaseModel):
    kind: Entry
    amount: Decimal = Field(ge=0)
    memo: str = Field(default="", max_length=500)
    agent_id: str | None = None
    reference: str | None = None


@router.post("/api/survival/ledger")
async def add_ledger(body: LedgerBody, lab: LabDep, user: Owner, request: Request) -> dict[str, str]:
    allowed = EXPENSES | {Entry.OWNER_FUNDING_OPERATIONS, Entry.OWNER_FUNDING_TRADING, Entry.EXTERNAL_REVENUE}
    if body.kind not in allowed:
        raise HTTPException(422, "trading P&L entries come from fills, not manual input")
    if body.kind == Entry.EXTERNAL_REVENUE and not body.reference:
        raise HTTPException(422, "external revenue requires a payment reference (verified receipt)")
    e = lab.ledger.add(body.kind, body.amount, memo=body.memo, agent_id=body.agent_id, reference=body.reference)
    lab.audit.record("ledger.add", user["sub"], {"kind": e.kind, "amount": str(e.amount)})
    await persist(request)
    return {"ok": "recorded"}


@router.post("/api/survival/recover")
async def recover(lab: LabDep, user: Owner, request: Request) -> dict[str, str]:
    lab.survival.owner_authorise_recovery(dt.datetime.now(dt.UTC), user["sub"])
    lab.audit.record("survival.recover", user["sub"], {})
    await persist(request)
    return {"state": lab.survival_report().state}


@router.get("/api/strategies/templates")
async def templates() -> dict[str, object]:
    return {k: f().model_dump(mode="json") for k, f in TEMPLATES.items()}


class BacktestBody(BaseModel):
    strategy: StrategyDefinition
    regime: str = Field(default="volatile", pattern="|".join(REGIMES))
    bars: int = Field(default=2000, ge=100, le=20000)
    seed: int = 1
    capital: float = Field(default=5.0, gt=0)
    fee_rate: float = Field(default=0.001, ge=0, le=0.05)
    slippage: float = Field(default=0.0005, ge=0, le=0.05)
    min_notional: float = Field(default=5.0, ge=0)


@router.post("/api/backtest")
async def backtest(body: BacktestBody) -> dict[str, object]:
    df = make_ohlcv(body.bars, body.regime, seed=body.seed)
    r = run_backtest(df, body.strategy, body.capital,
                     CostModel(fee_rate=body.fee_rate, slippage=body.slippage, min_notional=body.min_notional))
    mc = monte_carlo([t.return_pct for t in r.trades])
    return {"label": r.label, "dataset": f"synthetic:{body.regime}:seed={body.seed}", "metrics": r.metrics.as_dict(),
            "monte_carlo": mc.__dict__, "skipped_uneconomical": r.skipped_uneconomical,
            "partial_fills": r.partial_fills, "assumptions": r.assumptions,
            "equity": [(str(i), float(v)) for i, v in r.equity.iloc[:: max(1, len(r.equity) // 400)].items()],
            "trades": [{"entry": str(t.entry_time), "exit": str(t.exit_time), "pnl": t.pnl, "reason": t.exit_reason}
                       for t in r.trades[-200:]]}


@router.get("/api/audit")
async def audit(lab: LabDep, limit: int = 200) -> dict[str, object]:
    ev = lab.audit.events[-min(limit, 1000):]
    return {"verified": lab.audit.verify(), "events": [e.__dict__ for e in ev]}
