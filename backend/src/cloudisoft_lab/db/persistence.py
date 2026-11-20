"""Crash-safe persistence of the Lab.

* A full JSON snapshot (``system_state``) is written after every tick and every owner action;
  on startup it is restored, so a restart resumes with the same balances, ledger and history.
* Audit events, ledger entries and survival transitions are ALSO appended to their normalised
  tables (``audit_logs``, ``survival_ledger``, ``survival_state_history``) for traceability.
* Restore verifies the audit hash chain; a broken chain aborts startup rather than continuing silently.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cloudisoft_lab.audit import AuditEvent
from cloudisoft_lab.db.models import AuditLog, SurvivalLedgerRow, SurvivalStateHistory, SystemState
from cloudisoft_lab.domain.enums import DataOrigin, OrderStatus, Side, SurvivalState
from cloudisoft_lab.domain.schemas import FundingRecord, OrderResult
from cloudisoft_lab.execution.paper_broker import _Pos
from cloudisoft_lab.governance.agents import AgentInfo
from cloudisoft_lab.governance.proposals import Proposal, ProposalKind, ProposalStatus
from cloudisoft_lab.governance.revenue import RevenueOpportunity
from cloudisoft_lab.profit.manager import ApprovalStatus, WithdrawalRequest
from cloudisoft_lab.risk.policy import RiskConfig
from cloudisoft_lab.strategy.schema import StrategyDefinition
from cloudisoft_lab.strategy.store import StrategyRec, StrategyVersionRec
from cloudisoft_lab.survival.engine import TradeStat
from cloudisoft_lab.survival.ledger import Entry, LedgerEntry

if TYPE_CHECKING:
    from cloudisoft_lab.worker.lab import Lab

SNAPSHOT_VERSION = 1


class RecoveryError(RuntimeError):
    pass


def _d(x: object) -> str | None:
    return None if x is None else str(x)


def snapshot(lab: Lab) -> dict[str, Any]:
    p = lab.paper
    return {
        "v": SNAPSHOT_VERSION,
        "saved_at": dt.datetime.now(dt.UTC).isoformat(),
        "started_at": lab.started_at.isoformat(), "ticks": lab.ticks, "kill_switch": lab.kill_switch,
        "paper": {
            "starting_cash": str(p.starting_cash), "cash": str(p.cash), "realised_pnl": str(p.realised_pnl),
            "fees_paid": str(p.fees_paid), "last_closed_trade_pnl": _d(p.last_closed_trade_pnl),
            "positions": {s: {"qty": str(x.qty), "avg": str(x.avg), "last": _d(x.last_entry_notional)}
                          for s, x in p.positions.items()},
            "marks": {s: str(v) for s, v in p.marks.items()},
            "orders": [o.model_dump(mode="json") for o in list(p.orders.values())[-2000:]],
            "funding": [f.model_dump(mode="json") for f in p.funding],
        },
        "ledger": [{"kind": e.kind, "amount": str(e.amount), "origin": e.origin, "at": e.at.isoformat(),
                    "memo": e.memo, "agent_id": e.agent_id, "strategy_id": e.strategy_id,
                    "verified": e.verified, "reference": e.reference} for e in lab.ledger.entries],
        "audit": [e.__dict__ for e in lab.audit.events],
        "survival": {"state": lab.survival.state, "awaiting": lab.survival.awaiting_owner_recovery,
                     "history": [(t.isoformat(), s, w) for t, s, w in lab.survival.history]},
        "closed_trades": [(t.closed_at.isoformat(), str(t.net_pnl)) for t in lab.closed_trades],
        "equity_curve": lab.equity_curve[-2000:],
        "risk_config": lab.risk.config.model_dump(mode="json"),
        "strategies": [{"id": r.id, "name": r.name, "status": r.status, "versions": [
            {"version": v.version, "definition": v.definition.model_dump(mode="json"), "fingerprint": v.fingerprint,
             "author": v.author, "change_note": v.change_note, "created_at": v.created_at, "backtests": v.backtests}
            for v in r.versions]} for r in lab.strategies.items.values()],
        "proposals": [pr.as_dict() for pr in lab.board.proposals.values()],
        "agents": [{"agent_id": a.agent_id, "name": a.name, "scope": a.scope, "budget_usd": str(a.budget_usd),
                    "status": a.status, "builtin": a.builtin, "approved_by": a.approved_by,
                    "tasks": a.tasks[-50:], "performance": a.performance} for a in lab.agents.agents.values()],
        "withdrawals": [{**{k: (str(v) if isinstance(v, Decimal) else v) for k, v in r.__dict__.items()}}
                        for r in lab.workflow.requests.values()],
        "revenue": [{k: (str(v) if isinstance(v, Decimal) else v) for k, v in o.__dict__.items()}
                    for o in lab.revenue.items.values()],
        "llm_budgets": {k: {"limit": str(b.limit_usd), "spent": str(b.spent_usd)} for k, b in lab.llm.budgets.items()}
        if lab.llm else {},
    }


def restore(lab: Lab, data: dict[str, Any]) -> None:
    if data.get("v") != SNAPSHOT_VERSION:
        raise RecoveryError(f"unsupported snapshot version {data.get('v')}")
    events = [AuditEvent(**e) for e in data["audit"]]
    lab.audit.events = events
    if not lab.audit.verify():
        raise RecoveryError("audit hash chain verification failed; refusing to start")
    p, ps = lab.paper, data["paper"]
    p.starting_cash, p.cash = Decimal(ps["starting_cash"]), Decimal(ps["cash"])
    p.realised_pnl, p.fees_paid = Decimal(ps["realised_pnl"]), Decimal(ps["fees_paid"])
    p.last_closed_trade_pnl = Decimal(ps["last_closed_trade_pnl"]) if ps["last_closed_trade_pnl"] else None
    p.positions = {s: _Pos(Decimal(x["qty"]), Decimal(x["avg"]), Decimal(x["last"]) if x["last"] else None)
                   for s, x in ps["positions"].items()}
    p.marks = {s: Decimal(v) for s, v in ps["marks"].items()}
    p.orders = {o["client_order_id"]: OrderResult.model_validate(o) for o in ps["orders"]}
    p.funding = [FundingRecord.model_validate(f) for f in ps["funding"]]
    lab.router._seen = dict(p.orders)
    lab.ledger.entries = [LedgerEntry(Entry(e["kind"]), Decimal(e["amount"]), DataOrigin(e["origin"]),
                                      dt.datetime.fromisoformat(e["at"]), e["memo"], e["agent_id"], e["strategy_id"],
                                      e["verified"], e["reference"]) for e in data["ledger"]]
    sv = data["survival"]
    lab.survival.state = SurvivalState(sv["state"])
    lab.survival.awaiting_owner_recovery = sv["awaiting"]
    lab.survival.history = [(dt.datetime.fromisoformat(t), SurvivalState(s), w) for t, s, w in sv["history"]]
    lab.closed_trades = [TradeStat(dt.datetime.fromisoformat(t), Decimal(v)) for t, v in data["closed_trades"]]
    lab.equity_curve = [tuple(x) for x in data["equity_curve"]]  # type: ignore[misc]
    lab.kill_switch, lab.ticks = data["kill_switch"], data["ticks"]
    lab.started_at = dt.datetime.fromisoformat(data["started_at"])
    lab.risk.config = RiskConfig.model_validate(data["risk_config"])
    lab.strategies.items = {r["id"]: StrategyRec(r["id"], r["name"], r["status"], [
        StrategyVersionRec(v["version"], StrategyDefinition.model_validate(v["definition"]), v["fingerprint"],
                           v["author"], v["change_note"], v["created_at"], v["backtests"]) for v in r["versions"]])
        for r in data["strategies"]}
    lab.board.proposals = {}
    for pr in data["proposals"]:
        obj = Proposal(ProposalKind(pr["kind"]), pr["title"], pr["payload"], pr["evidence"], pr["created_by"],
                       pr["id"], ProposalStatus(pr["status"]), pr["created_at"], pr["decided_by"],
                       pr["decided_at"], pr["note"])
        lab.board.proposals[obj.id] = obj
    for a in data["agents"]:
        lab.agents.agents[a["agent_id"]] = AgentInfo(a["agent_id"], a["name"], a["scope"], Decimal(a["budget_usd"]),
                                                     a["status"], a["builtin"], a["approved_by"], a["tasks"],
                                                     a["performance"])
    lab.workflow.requests = {}
    for w in data["withdrawals"]:
        r = WithdrawalRequest(w["provider"], w["asset"], Decimal(w["amount"]), w["destination"], w["network"],
                              Decimal(w["estimated_fee"]), w["request_id"], ApprovalStatus(w["status"]),
                              w["confirmations"], w["approved_by"], w["provider_reference"], w["history"])
        lab.workflow.requests[r.request_id] = r
    if "revenue" in data:
        lab.revenue.items = {}
        for o in data["revenue"]:
            obj = RevenueOpportunity(**{k: (Decimal(v) if k in ("delivery_cost_monthly", "expected_revenue_monthly",
                                                                 "setup_cost") else v) for k, v in o.items()})
            lab.revenue.items[obj.id] = obj
    if lab.llm:
        for k, b in data.get("llm_budgets", {}).items():
            lab.llm.budget(k).limit_usd, lab.llm.budget(k).spent_usd = Decimal(b["limit"]), Decimal(b["spent"])
    lab.audit.record("lab.restored", "system", {"from": data["saved_at"], "ticks": lab.ticks})


class StateStore:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions
        self._audit_n = self._ledger_n = self._hist_n = None  # type: int | None

    async def load(self, lab: Lab) -> bool:
        async with self.sessions() as s:
            row = await s.get(SystemState, "lab")
            self._audit_n = await s.scalar(select(func.count()).select_from(AuditLog)) or 0
            self._ledger_n = await s.scalar(select(func.count()).select_from(SurvivalLedgerRow)) or 0
            self._hist_n = await s.scalar(select(func.count()).select_from(SurvivalStateHistory)) or 0
        if row is None:
            return False
        restore(lab, row.data)
        return True

    async def save(self, lab: Lab) -> None:
        if self._audit_n is None:
            await self.load_counts()
        data = snapshot(lab)
        async with self.sessions() as s, s.begin():
            row = await s.get(SystemState, "lab")
            now = dt.datetime.now(dt.UTC)
            if row is None:
                s.add(SystemState(key="lab", version=SNAPSHOT_VERSION, data=data, updated_at=now))
            else:
                row.data, row.updated_at = data, now
            existing = await s.scalar(select(func.max(AuditLog.seq)))
            start = -1 if existing is None else existing
            for e in lab.audit.events:
                if e.seq > start:
                    s.add(AuditLog(seq=e.seq, at=e.at, event=e.event, actor=e.actor, data=e.data,
                                   prev_hash=e.prev_hash, hash=e.hash))
            for e in lab.ledger.entries[self._ledger_n or 0:]:
                s.add(SurvivalLedgerRow(kind=e.kind.value, amount=e.amount, origin=e.origin.value, verified=e.verified,
                                        at=e.at, agent_id=e.agent_id, strategy_id=e.strategy_id,
                                        reference=e.reference, memo=e.memo))
            for t, st, why in lab.survival.history[self._hist_n or 0:]:
                s.add(SurvivalStateHistory(state=st.value, reason=why, snapshot={"at": t.isoformat()}))
        self._ledger_n = len(lab.ledger.entries)
        self._hist_n = len(lab.survival.history)

    async def load_counts(self) -> None:
        async with self.sessions() as s:
            self._ledger_n = await s.scalar(select(func.count()).select_from(SurvivalLedgerRow)) or 0
            self._hist_n = await s.scalar(select(func.count()).select_from(SurvivalStateHistory)) or 0


__all__ = ["OrderStatus", "Side", "StateStore", "restore", "snapshot"]


async def persistent_secret(sessions: async_sessionmaker[AsyncSession], name: str, factory=None) -> str:  # type: ignore[no-untyped-def]
    """Generate-once server secret kept in the database (used when none is configured), so no
    secret has to be typed or pasted anywhere. Survives restarts; rotate by deleting the row."""
    import secrets

    async with sessions() as s, s.begin():
        row = await s.get(SystemState, f"secret:{name}")
        if row is None:
            value = factory() if factory else secrets.token_urlsafe(48)
            row = SystemState(key=f"secret:{name}", version=1, data={"value": value},
                              updated_at=dt.datetime.now(dt.UTC))
            s.add(row)
        return str(row.data["value"])


async def delete_secret(sessions: async_sessionmaker[AsyncSession], name: str) -> None:
    async with sessions() as s, s.begin():
        row = await s.get(SystemState, f"secret:{name}")
        if row is not None:
            await s.delete(row)
