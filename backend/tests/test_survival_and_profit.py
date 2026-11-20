import datetime as dt
from decimal import Decimal

import pytest

from cloudisoft_lab.domain.enums import DataOrigin, SurvivalState
from cloudisoft_lab.profit.manager import (
    ApprovalStatus,
    WithdrawalPolicy,
    WithdrawalRequest,
    WithdrawalWorkflow,
    WithdrawalWorkflowError,
    recommend_withdrawal,
)
from cloudisoft_lab.survival.engine import SurvivalEngine, TradeStat
from cloudisoft_lab.survival.ledger import Entry, SurvivalLedger
from cloudisoft_lab.survival.model_router import ModelRouter

NOW = dt.datetime(2026, 11, 20, tzinfo=dt.UTC)
D = Decimal


def ledger_with(ops=D(10), burn_per_day=D("0.5"), days=7):
    l = SurvivalLedger()
    l.add(Entry.OWNER_FUNDING_OPERATIONS, ops, at=NOW - dt.timedelta(days=30))
    l.add(Entry.OWNER_FUNDING_TRADING, D(5), at=NOW - dt.timedelta(days=30))
    for i in range(days):
        l.add(Entry.AI_INFERENCE_COST, burn_per_day, at=NOW - dt.timedelta(days=i, hours=1), agent_id="scanner")
    return l


def test_formulas():
    l = SurvivalLedger(earnings_to_operations_fraction=D("0.5"))
    l.add(Entry.OWNER_FUNDING_OPERATIONS, D(20))
    l.add(Entry.OWNER_FUNDING_TRADING, D(5))
    l.add(Entry.REALISED_TRADING_PNL, D(3))
    l.add(Entry.TRADING_FEE, D("0.5"))
    l.add(Entry.EXECUTION_COST, D("0.5"))
    l.add(Entry.EXTERNAL_REVENUE, D(4))
    l.add(Entry.AI_INFERENCE_COST, D(1)); l.add(Entry.HOSTING_COST, D(2))
    l.add(Entry.DATA_COST, D("0.5")); l.add(Entry.OTHER_EXPENSE, D("0.5"))
    s = l.summary()
    assert s["net_trading_profit"] == D(2)
    assert s["net_operating_profit"] == D(2) + D(4) - D(4)
    assert s["eligible_realised_earnings"] == D(1) + D(4)
    assert s["survival_balance"] == D(20) + D(5) - D(4)
    # trading capital keeps the half of profit not swept to ops: no double counting
    assert s["trading_capital"] + s["eligible_realised_earnings"] - D(4) == D(5) + D(2)


def test_owner_deposits_are_not_revenue():
    l = SurvivalLedger()
    l.add(Entry.OWNER_FUNDING_OPERATIONS, D(1000))
    assert l.summary()["net_operating_profit"] == 0
    assert l.summary()["verified_external_revenue"] == 0


def test_unverified_and_simulated_excluded():
    l = SurvivalLedger()
    l.add(Entry.EXTERNAL_REVENUE, D(50), verified=False)
    l.add(Entry.REALISED_TRADING_PNL, D(100), origin=DataOrigin.SIMULATED)
    assert l.summary()["net_operating_profit"] == 0
    with pytest.raises(ValueError):
        l.add(Entry.EXTERNAL_REVENUE, D(1), origin=DataOrigin.ESTIMATED)
    with pytest.raises(ValueError):
        l.add(Entry.HOSTING_COST, D(-1))


@pytest.mark.parametrize("ops,burn,state", [
    (D(100), D("0.5"), SurvivalState.HIGH),        # ~93d runway
    (D(30), D("0.5"), SurvivalState.NORMAL),       # ~53d
    (D(8), D("0.5"), SurvivalState.LOW_COMPUTE),   # ~9d
    (D("4.5"), D("0.5"), SurvivalState.CRITICAL),  # ~1d
    (D(3), D("0.5"), SurvivalState.DEAD),          # exhausted
])
def test_state_transitions(ops, burn, state):
    e = SurvivalEngine(ledger_with(ops, burn))
    r = e.evaluate(NOW)
    assert r.state == state, (r.survival_balance, r.runway_days)


def test_critical_and_dead_policies():
    e = SurvivalEngine(ledger_with(D("4.5")))
    assert not e.evaluate(NOW).policy.open_new_trades
    assert e.policy.risk_monitoring and e.policy.notify_owner


def test_dead_requires_owner_recovery_no_auto_revive():
    l = ledger_with(D(3))
    e = SurvivalEngine(l)
    assert e.evaluate(NOW).state == SurvivalState.DEAD
    l.add(Entry.OWNER_FUNDING_OPERATIONS, D(500), at=NOW)  # owner tops up
    assert e.evaluate(NOW).state == SurvivalState.DEAD  # still waits for explicit recovery
    e.owner_authorise_recovery(NOW, "owner")
    assert e.evaluate(NOW).state == SurvivalState.HIGH
    assert len(e.history) >= 2


def test_not_profitable_after_one_trade():
    l = ledger_with(D(100), D("0.01"))
    l.add(Entry.REALISED_TRADING_PNL, D(50), at=NOW)
    e = SurvivalEngine(l)
    r = e.evaluate(NOW, [TradeStat(NOW, D(50))], NOW - dt.timedelta(days=60))
    assert r.state != SurvivalState.PROFITABLE and not r.profitability["checks"]["trade_count"]


def test_sustained_profitability():
    l = ledger_with(D(100), D("0.01"))
    start = NOW - dt.timedelta(days=60)
    trades = [TradeStat(start + dt.timedelta(days=i), D(1)) for i in range(60)]
    l.add(Entry.REALISED_TRADING_PNL, D(60), at=NOW)
    r = SurvivalEngine(l).evaluate(NOW, trades, start, D("-0.05"))
    assert r.state == SurvivalState.PROFITABLE and r.policy.expansion_proposals


def test_budget_exhaustion_reduces_model_costs():
    router = ModelRouter()
    assert router.select(SurvivalState.HIGH) == "claude-opus-5-5"
    assert router.select(SurvivalState.LOW_COMPUTE) is None  # non-essential deferred
    assert router.select(SurvivalState.LOW_COMPUTE, essential=True) == "claude-haiku-5-5"
    assert router.select(SurvivalState.DEAD, essential=True) is None
    assert router.cost("claude-haiku-5-5", 1_000_000, 0) == D("0.10")


def test_cost_attribution():
    l = ledger_with()
    assert l.cost_by("agent_id")["scanner"] == D("3.5")


def test_withdrawal_recommendation():
    p = WithdrawalPolicy(min_trading_reserve=D(5))
    r = recommend_withdrawal(original_capital=D(5), current_cash=D(9), realised_net_profit=D(4),
                             locked_in_open_positions=D(0), outstanding_obligations=D(0), policy=p)
    assert r.recommended_amount == D(2) and r.remaining_capital == D(7)
    r2 = recommend_withdrawal(original_capital=D(5), current_cash=D(6), realised_net_profit=D(4),
                              locked_in_open_positions=D(3), outstanding_obligations=D(0), policy=p)
    assert r2.recommended_amount == D(1)
    assert recommend_withdrawal(original_capital=D(5), current_cash=D(5), realised_net_profit=D(-1),
                                locked_in_open_positions=D(0), outstanding_obligations=D(0),
                                policy=p).recommended_amount == 0


def test_withdrawal_workflow_requires_owner_and_confirmations():
    wf = WithdrawalWorkflow({"owner"})
    with pytest.raises(WithdrawalWorkflowError):
        wf.create(WithdrawalRequest("binance", "USDT", D(100), "addr", "TRC20", D(1)), available=D(50))
    req = wf.create(WithdrawalRequest("binance", "USDT", D(10), "addr", "TRC20", D(1)), available=D(50))
    with pytest.raises(WithdrawalWorkflowError):
        wf.mark_submitted(req.request_id, None)  # not approved
    with pytest.raises(WithdrawalWorkflowError):
        wf.approve(req.request_id, "agent", {})
    with pytest.raises(WithdrawalWorkflowError):
        wf.approve(req.request_id, "owner", {"provider": True})
    full = {k: True for k in ("provider", "asset", "amount", "destination", "network", "fees", "final_details")}
    wf.approve(req.request_id, "owner", full)
    wf.mark_submitted(req.request_id, None)
    with pytest.raises(WithdrawalWorkflowError):
        wf.mark_result(req.request_id, ok=True)  # no fabricated success without provider ref
    assert wf.mark_result(req.request_id, ok=False).status == ApprovalStatus.FAILED


def test_fresh_install_is_not_dead():
    e = SurvivalEngine(SurvivalLedger())
    r = e.evaluate(NOW)
    assert r.state == SurvivalState.NORMAL and "operating budget" in r.reasons[0]
    e.ledger.add(Entry.HOSTING_COST, D(1), at=NOW)
    assert e.evaluate(NOW).state == SurvivalState.DEAD


def test_simulated_entries_do_not_kill_unfunded_install():
    """Regression (found in E2E): a paper fee on a fresh install flipped the engine to DEAD."""
    e = SurvivalEngine(SurvivalLedger())
    e.ledger.add(Entry.TRADING_FEE, D("0.01"), origin=DataOrigin.SIMULATED, at=NOW)
    e.ledger.add(Entry.REALISED_TRADING_PNL, D("-1"), origin=DataOrigin.SIMULATED, at=NOW)
    assert e.evaluate(NOW).state == SurvivalState.NORMAL
