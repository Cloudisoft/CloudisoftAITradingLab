"""Milestone 14: failure simulations."""
import datetime as dt
from decimal import Decimal

import numpy as np

from cloudisoft_lab.core.config import Settings
from cloudisoft_lab.data.csv_provider import CsvReplayProvider, DatasetStore
from cloudisoft_lab.data.synthetic import SyntheticProvider, make_ohlcv
from cloudisoft_lab.domain.enums import SurvivalState
from cloudisoft_lab.profit.manager import ApprovalStatus
from cloudisoft_lab.survival.ledger import Entry
from cloudisoft_lab.worker.lab import Lab

S = Settings(paper_starting_balance_usd=100.0)
T0 = dt.datetime(2026, 11, 20, tzinfo=dt.UTC)
CONF = {k: True for k in ("provider", "asset", "amount", "destination", "network", "fees", "final_details")}


class GappyProvider(SyntheticProvider):
    async def get_candles(self, symbol, interval, limit):
        df = await super().get_candles(symbol, interval, limit)
        df.iloc[-5, df.columns.get_loc("close")] = np.nan
        return df


class FlakyProvider(SyntheticProvider):
    def __init__(self):
        super().__init__("volatile", seed=3)
        self.n = 0

    async def get_candles(self, symbol, interval, limit):
        self.n += 1
        if 20 <= self.n < 60:
            raise ConnectionError("exchange API outage")
        return await super().get_candles(symbol, interval, limit)


async def test_missing_market_data_blocks_trading():
    lab = Lab(S, GappyProvider("volatile", seed=3))
    for i in range(100):
        out = await lab.tick(T0 + dt.timedelta(hours=i))
        assert out["actions"] == []
    assert any(e.event == "market_data.rejected" for e in lab.audit.events)


async def test_outage_then_recovery():
    lab = Lab(S, FlakyProvider())
    for i in range(200):
        await lab.tick(T0 + dt.timedelta(hours=i))
    errors = [e for e in lab.audit.events if e.event == "market_data.error"]
    assert errors and lab.equity_curve[-1][1] > 0
    assert lab.audit.verify()


async def test_sudden_volatility_shock_is_contained():
    class Shock(SyntheticProvider):
        async def get_candles(self, symbol, interval, limit):
            df = make_ohlcv(limit + self._calls + 1, "trend_up", seed=9, shock_at=limit + 40, shock=-0.4)
            self._calls += 1
            return df.iloc[-limit:]
    lab = Lab(S, Shock())
    for i in range(120):
        await lab.tick(T0 + dt.timedelta(hours=i))
    # long-only, unleveraged, position cap => cannot lose more than the capital at risk
    assert lab.paper.equity() > Decimal(0)
    assert lab.paper.equity() >= Decimal(100) * (1 - Decimal(str(lab.active_strategy().risk.position_fraction)))


async def test_critical_state_stops_new_trades_but_keeps_monitoring():
    lab = Lab(S, SyntheticProvider("volatile", seed=3))
    lab.ledger.add(Entry.OWNER_FUNDING_OPERATIONS, Decimal(2), at=T0)
    for d in range(7):
        lab.ledger.add(Entry.HOSTING_COST, Decimal("0.25"), at=T0 - dt.timedelta(days=d))
    for _ in range(150):
        await lab.tick(T0 + dt.timedelta(hours=1))
    assert lab.survival.state == SurvivalState.CRITICAL
    assert not [o for o in lab.paper.orders.values() if o.side == "buy"]
    assert lab.last_scan, "risk monitoring / scanning continues"
    assert any(n["kind"] == "survival_state" for n in lab.notifier.sent)


async def test_failed_withdrawal_is_not_reported_as_success():
    lab = Lab(S, SyntheticProvider())
    r = lab.wallet.request_withdrawal("paper", Decimal(50), "bank", None, Decimal(0))
    lab.workflow.approve(r.request_id, "owner", CONF)
    lab.paper.cash = Decimal(10)  # funds disappear between approval and execution (e.g. a fill)
    lab.wallet.execute_approved(r.request_id)
    assert lab.workflow.requests[r.request_id].status == ApprovalStatus.FAILED
    assert lab.paper.cash == Decimal(10)


async def test_csv_replay_end_of_data():
    store = DatasetStore()
    df = make_ohlcv(320, "sideways")
    csv = df.reset_index(names="timestamp").to_csv(index=False)
    assert store.add("BTCUSDT", csv, "test", owner_asserts_real=False).ok
    s = Settings(paper_starting_balance_usd=100.0, paper_symbols=["BTCUSDT"])
    lab = Lab(s, CsvReplayProvider(store))
    for i in range(40):
        await lab.tick(T0 + dt.timedelta(hours=i))
    assert "replay of BTCUSDT finished" in (lab.last_error or "")
