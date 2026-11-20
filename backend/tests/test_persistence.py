import datetime as dt
from decimal import Decimal

import pytest

from cloudisoft_lab.core.config import Settings
from cloudisoft_lab.data.synthetic import SyntheticProvider
from cloudisoft_lab.db.base import create_all, make_sessionmaker
from cloudisoft_lab.db.persistence import RecoveryError, StateStore, restore, snapshot
from cloudisoft_lab.governance.proposals import Proposal, ProposalKind
from cloudisoft_lab.survival.ledger import Entry
from cloudisoft_lab.worker.lab import Lab

S = Settings(paper_starting_balance_usd=100.0)
T0 = dt.datetime(2026, 11, 20, tzinfo=dt.UTC)


async def busy_lab() -> Lab:
    lab = Lab(S, SyntheticProvider("volatile", seed=3))
    lab.ledger.add(Entry.OWNER_FUNDING_OPERATIONS, Decimal(50), at=T0)
    lab.ledger.add(Entry.HOSTING_COST, Decimal("0.2"), at=T0, agent_id="infra")
    for i in range(150):
        await lab.tick(T0 + dt.timedelta(hours=i))
    lab.board.submit(Proposal(ProposalKind.AGENT_SPAWN, "x", {"agent_id": "new_one"}, {}, "agent"))
    lab.wallet.request_withdrawal("paper", Decimal(1), "owner-bank", None, Decimal(0))
    return lab


async def test_snapshot_roundtrip():
    lab = await busy_lab()
    data = snapshot(lab)
    fresh = Lab(S, SyntheticProvider("volatile", seed=3))
    restore(fresh, data)
    assert fresh.paper.cash == lab.paper.cash and fresh.paper.equity() == lab.paper.equity()
    assert fresh.paper.orders.keys() == lab.paper.orders.keys()
    assert fresh.ledger.summary() == lab.ledger.summary()
    assert len(fresh.board.proposals) == 1 and len(fresh.workflow.requests) == 1
    assert fresh.audit.verify() and fresh.audit.events[-1].event == "lab.restored"
    # restored router still blocks replays of old order ids (idempotency survives restarts)
    assert set(fresh.router._seen) == set(lab.paper.orders)


async def test_tampered_audit_refuses_restore():
    lab = await busy_lab()
    data = snapshot(lab)
    data["audit"][1]["data"] = {"forged": True}
    with pytest.raises(RecoveryError):
        restore(Lab(S, SyntheticProvider()), data)


async def test_database_recovery_after_restart(tmp_path):
    sessions = make_sessionmaker(f"sqlite+aiosqlite:///{tmp_path}/db.sqlite")
    await create_all(sessions)
    lab = await busy_lab()
    store = StateStore(sessions)
    assert not await store.load(lab.__class__(S, SyntheticProvider()))
    await store.save(lab)
    await store.save(lab)  # idempotent: no duplicate audit/ledger rows
    # "crash" and restart
    sessions2 = make_sessionmaker(f"sqlite+aiosqlite:///{tmp_path}/db.sqlite")
    lab2 = Lab(S, SyntheticProvider("volatile", seed=3))
    assert await StateStore(sessions2).load(lab2)
    assert lab2.paper.equity() == lab.paper.equity() and lab2.ledger.summary() == lab.ledger.summary()
    from sqlalchemy import func, select

    from cloudisoft_lab.db.models import AuditLog, SurvivalLedgerRow
    async with sessions2() as s:
        assert await s.scalar(select(func.count()).select_from(SurvivalLedgerRow)) == len(lab.ledger.entries)
        assert await s.scalar(select(func.count()).select_from(AuditLog)) == len(lab.audit.events)
