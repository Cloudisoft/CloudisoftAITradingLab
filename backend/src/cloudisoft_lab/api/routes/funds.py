"""Wallet & Funds and Profit Manager."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from cloudisoft_lab.agents import portfolio
from cloudisoft_lab.api.deps import LabDep, Operator, Owner, persist
from cloudisoft_lab.profit.manager import REQUIRED_CONFIRMATIONS, WithdrawalPolicy, WithdrawalWorkflowError
from cloudisoft_lab.profit.wallet import WalletError

router = APIRouter(prefix="/api")


def _req(r) -> dict[str, object]:  # type: ignore[no-untyped-def]
    return {k: (str(v) if isinstance(v, Decimal) else v) for k, v in r.__dict__.items()}


@router.get("/wallet")
async def wallet(lab: LabDep) -> dict[str, object]:
    return {
        "accounts": lab.wallet.accounts(),
        "transactions": [f.model_dump(mode="json") for f in lab.paper.funding],
        "withdrawal_requests": [_req(r) for r in lab.workflow.requests.values()],
        "providers": [
            {"provider": "binance", "status": "not connected", "funding": "use Binance's official app/website"},
            {"provider": "zerodha", "status": "not connected", "funding": "use Zerodha Console's official funds page"},
        ],
        "custody_notice": "Cloudisoft never holds funds. Real money stays in your broker/exchange account.",
    }


class WithdrawBody(BaseModel):
    provider: str = "paper"
    amount: Decimal = Field(gt=0)
    destination: str = Field(min_length=1, max_length=200)
    network: str | None = Field(default=None, max_length=32)
    estimated_fee: Decimal = Field(default=Decimal(0), ge=0)


@router.post("/wallet/withdrawals")
async def create_withdrawal(body: WithdrawBody, lab: LabDep, user: Operator, request: Request) -> dict[str, object]:
    try:
        r = lab.wallet.request_withdrawal(body.provider, body.amount, body.destination, body.network, body.estimated_fee)
    except (WalletError, WithdrawalWorkflowError) as exc:
        raise HTTPException(422, str(exc)) from exc
    lab.audit.record("withdrawal.requested", user["sub"], _req(r))
    await lab.notifier.notify("withdrawal", f"Withdrawal of {r.amount} requested; owner approval required")
    await persist(request)
    return {"request": _req(r), "required_confirmations": list(REQUIRED_CONFIRMATIONS)}


class DecisionBody(BaseModel):
    approve: bool
    confirmations: dict[str, bool] = Field(default_factory=dict)


@router.post("/wallet/withdrawals/{rid}/decision")
async def decide_withdrawal(rid: str, body: DecisionBody, lab: LabDep, user: Owner, request: Request) -> dict[str, object]:
    if rid not in lab.workflow.requests:
        raise HTTPException(404, "not found")
    owner = "owner"  # the single owner identity in the workflow
    try:
        if not body.approve:
            r = lab.workflow.reject(rid, owner)
        else:
            lab.workflow.approve(rid, owner, body.confirmations)
            lab.wallet.execute_approved(rid)
            r = lab.workflow.requests[rid]
    except (WalletError, WithdrawalWorkflowError) as exc:
        raise HTTPException(422, str(exc)) from exc
    lab.audit.record("withdrawal.decision", user["sub"], _req(r))
    await persist(request)
    return _req(r)


@router.get("/profit")
async def profit(lab: LabDep) -> dict[str, object]:
    rec = lab.withdrawal_recommendation()
    s = lab.ledger.summary()
    p = lab.paper
    return {
        "paper": {"label": "simulated", "realised_pnl": str(p.realised_pnl), "fees": str(p.fees_paid),
                  "net_realised": str(p.realised_pnl - p.fees_paid), "unrealised_pnl": str(p.unrealised_pnl()),
                  "equity": str(p.equity()), "original_capital": str(p.starting_cash)},
        "actual": {k: str(s[k]) for k in ("net_trading_profit", "net_operating_profit", "operating_expenses",
                                          "verified_external_revenue", "survival_balance", "trading_capital")},
        "recommendation": {"amount": str(rec.recommended_amount), "remaining_capital": str(rec.remaining_capital),
                           "reasons": rec.reasons, "label": rec.label},
        "policy": lab.withdrawal_policy.model_dump(mode="json"),
        "overexposure": portfolio.analyse({k: v.qty for k, v in p.positions.items()}, p.marks, p.cash)["warnings"],
    }


@router.put("/profit/policy")
async def set_policy(body: WithdrawalPolicy, lab: LabDep, user: Owner, request: Request) -> dict[str, object]:
    lab.withdrawal_policy = body
    lab.audit.record("profit.policy", user["sub"], body.model_dump(mode="json"))
    await persist(request)
    return body.model_dump(mode="json")
