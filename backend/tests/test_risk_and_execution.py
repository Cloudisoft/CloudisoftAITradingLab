import datetime as dt
from decimal import Decimal

import pytest
from pydantic import ValidationError

from cloudisoft_lab.audit import AuditTrail
from cloudisoft_lab.domain.enums import MarketKind, OrderStatus, Side, SurvivalState, TradingMode
from cloudisoft_lab.domain.schemas import OrderRequest
from cloudisoft_lab.execution.paper_broker import PaperBroker, PaperModeViolation
from cloudisoft_lab.execution.router import ExecutionRouter, RoutingError
from cloudisoft_lab.markets.registry import MARKETS
from cloudisoft_lab.risk.engine import LiveGates, RiskEngine
from cloudisoft_lab.risk.policy import IMMUTABLE, RiskConfig


def order(qty="0.0004", side=Side.BUY, mode=TradingMode.PAPER, **kw):
    return OrderRequest(mode=mode, market=MarketKind.CRYPTO, symbol="BTCUSDT", side=side,
                        quantity=Decimal(qty), **kw)


def test_immutable_policy_values():
    assert not any([IMMUTABLE.allow_leverage, IMMUTABLE.allow_borrowing, IMMUTABLE.allow_martingale,
                    IMMUTABLE.allow_auto_withdrawal, IMMUTABLE.allow_auto_deposit,
                    IMMUTABLE.allow_agent_self_replication, IMMUTABLE.allow_risk_increase_to_survive,
                    IMMUTABLE.live_trading_default_enabled, IMMUTABLE.allow_short_selling])
    with pytest.raises(Exception):
        IMMUTABLE.allow_leverage = True  # type: ignore[misc]


def test_config_cannot_exceed_ceiling():
    with pytest.raises(ValidationError):
        RiskConfig(max_daily_loss_fraction=Decimal("0.5"))


def test_approves_valid_paper_order(ctx):
    d = RiskEngine().evaluate(order(), ctx())
    assert d.approved, d.reasons


@pytest.mark.parametrize("kw,why", [
    ({"kill_switch": True}, "kill switch"),
    ({"survival_state": SurvivalState.CRITICAL}, "survival"),
    ({"survival_state": SurvivalState.DEAD}, "survival"),
    ({"available_cash": Decimal("10")}, "insufficient funds"),
    ({"start_of_day_equity": Decimal("120")}, "daily loss"),
    ({"position_qty": Decimal("0.001")}, "exposure"),
    ({"open_positions": 3}, "too many"),
])
def test_rejections(ctx, kw, why):
    d = RiskEngine().evaluate(order(), ctx(**kw))
    assert not d.approved and any(why in r for r in d.reasons), d.reasons


def test_min_notional_and_step(ctx):
    assert not RiskEngine().evaluate(order("0.00005"), ctx()).approved  # $2.5 < $5
    assert not RiskEngine().evaluate(order("0.000155"), ctx()).checks["qty_step"]


def test_high_costs_uneconomical(ctx):
    d = RiskEngine().evaluate(order(), ctx(fee_rate=Decimal("0.01")))
    assert not d.approved and not d.checks["cost_economics"]


def test_no_martingale_after_loss(ctx):
    c = ctx(last_closed_trade_pnl=Decimal("-1"), last_entry_notional=Decimal("10"))
    assert not RiskEngine().evaluate(order("0.0004"), c).checks["no_martingale"]  # $20 > $10
    c2 = ctx(last_closed_trade_pnl=Decimal("-1"), last_entry_notional=Decimal("25"))
    assert RiskEngine().evaluate(order("0.0004"), c2).approved


def test_no_short_selling(ctx):
    d = RiskEngine().evaluate(order(side=Side.SELL), ctx())
    assert not d.approved and "short" in d.reasons[0]


def test_sell_allowed_in_critical_to_protect(ctx):
    c = ctx(survival_state=SurvivalState.CRITICAL, position_qty=Decimal("0.0004"))
    assert RiskEngine().evaluate(order(side=Side.SELL), c).approved


def test_market_closed(ctx, btc):
    from cloudisoft_lab.markets.registry import Instrument
    inst = Instrument("BTCUSDT", MarketKind.IN_EQUITY, "X", "INR", Decimal(1), Decimal(1), Decimal(1), Decimal("0.05"))
    sat = dt.datetime(2026, 11, 21, 6, 0, tzinfo=dt.UTC)
    o = OrderRequest(mode=TradingMode.PAPER, market=MarketKind.IN_EQUITY, symbol="BTCUSDT", side=Side.BUY, quantity=Decimal(1))
    d = RiskEngine().evaluate(o, ctx(now=sat, market=MARKETS[MarketKind.IN_EQUITY], instrument=inst,
                                     reference_price=Decimal(10)))
    assert not d.checks["market_open"]


def test_live_requires_all_gates(ctx):
    d = RiskEngine().evaluate(order(mode=TradingMode.LIVE), ctx())
    assert not d.approved and not d.checks["live_gates"]
    all_gates = LiveGates(*([True] * 8))
    d2 = RiskEngine().evaluate(order(mode=TradingMode.LIVE), ctx(live_gates=all_gates))
    # crypto market itself is still not enabled for live in the registry
    assert not d2.checks.get("market_enabled_live", True)


def test_leveraged_market_blocked(ctx):
    from dataclasses import replace
    lev = replace(MARKETS[MarketKind.CRYPTO], allows_leverage=True)
    assert not RiskEngine().evaluate(order(), ctx(market=lev)).checks["leverage"]


async def test_paper_broker_fills_and_pnl():
    b = PaperBroker(Decimal("100"))
    b.mark("BTCUSDT", Decimal("50000"))
    buy = await b.place_order(order())
    assert buy.status == OrderStatus.FILLED and buy.origin == "simulated"
    b.mark("BTCUSDT", Decimal("55000"))
    assert b.unrealised_pnl() > 0
    sell = await b.place_order(order(side=Side.SELL))
    assert sell.status == OrderStatus.FILLED
    assert b.realised_pnl > 0 and b.fees_paid > 0 and not await b.get_positions()


async def test_paper_broker_refuses_live_and_is_idempotent():
    b = PaperBroker(Decimal("100"))
    b.mark("BTCUSDT", Decimal("50000"))
    with pytest.raises(PaperModeViolation):
        await b.place_order(order(mode=TradingMode.LIVE))
    o = order()
    r1, r2 = await b.place_order(o), await b.place_order(o)
    assert r1 == r2 and len(b.orders) == 1
    assert b.cash == Decimal("100") - r1.average_price * o.quantity - r1.fees


async def test_paper_broker_insufficient_and_missing_price():
    b = PaperBroker(Decimal("1"))
    assert (await b.place_order(order())).reason == "no market price available"
    b.mark("BTCUSDT", Decimal("50000"))
    assert (await b.place_order(order())).status == OrderStatus.REJECTED


async def test_router_runs_risk_and_blocks_duplicates(ctx):
    audit = AuditTrail()
    b = PaperBroker(Decimal("100"))
    b.mark("BTCUSDT", Decimal("50000"))
    r = ExecutionRouter(RiskEngine(), b, audit)
    o = order()
    res, dec = await r.submit(o, ctx())
    assert dec.approved and res.status == OrderStatus.FILLED
    res2, dec2 = await r.submit(o, ctx())
    assert not dec2.approved and "duplicate" in dec2.reasons[0]
    assert len(b.orders) == 1
    bad, d3 = await r.submit(order(), ctx(kill_switch=True))
    assert bad.status == OrderStatus.REJECTED
    assert audit.verify() and len(audit.events) >= 4


async def test_router_never_routes_live_to_paper(ctx):
    b = PaperBroker(Decimal("100"))
    r = ExecutionRouter(RiskEngine(RiskConfig()), b, AuditTrail(), live=b)
    from dataclasses import replace
    c = ctx(live_gates=LiveGates(*([True] * 8)), market=replace(MARKETS[MarketKind.CRYPTO], enabled_for_live=True))
    with pytest.raises(RoutingError):
        await r.submit(order(mode=TradingMode.LIVE), c)


def test_audit_tamper_detected():
    a = AuditTrail()
    a.record("x", "y", {"v": 1})
    a.record("x", "y", {"v": 2})
    assert a.verify()
    a.events[0].data["v"] = 99
    assert not a.verify()


def test_owner_manual_paper_orders_skip_per_order_cap(ctx):
    big = ctx(available_cash=Decimal("100000"), equity=Decimal("100000"), start_of_day_equity=Decimal("100000"))
    bot = order("0.01")  # $500 > default $100 cap
    assert not RiskEngine().evaluate(bot, big).checks["max_order_notional"]
    mine = order("0.01", requested_by="owner:me@x")
    d = RiskEngine().evaluate(mine, big)
    assert d.approved and "max_order_notional" not in d.checks
    # still bound by funds and exposure
    assert not RiskEngine().evaluate(order("1.5", requested_by="owner:me@x"), big).approved  # 75% in one coin
    live = OrderRequest(mode=TradingMode.LIVE, market=MarketKind.CRYPTO, symbol="BTCUSDT", side=Side.BUY,
                        quantity=Decimal("0.01"), requested_by="owner:me@x")
    assert not RiskEngine().evaluate(live, big).checks["max_order_notional"]
