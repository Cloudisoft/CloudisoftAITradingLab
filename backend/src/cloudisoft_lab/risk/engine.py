"""Independent risk engine. Every order — paper or live — must pass through ``evaluate``.

The engine is pure (no I/O): it receives a snapshot ``RiskContext`` and returns a
``RiskDecision`` listing every check performed. The execution router refuses any order
without an approving decision that it obtained itself.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal

from cloudisoft_lab.core.money import ZERO, floor_to_step
from cloudisoft_lab.domain.enums import Side, SurvivalState, TradingMode
from cloudisoft_lab.domain.schemas import OrderRequest
from cloudisoft_lab.markets.registry import Instrument, MarketSpec
from cloudisoft_lab.risk.policy import IMMUTABLE, RiskConfig


@dataclass(frozen=True)
class LiveGates:
    config_allows_live: bool = False
    broker_connected: bool = False
    api_permissions_verified: bool = False  # trading on, withdrawals OFF, IP-restricted
    account_verified: bool = False
    compliance_checked: bool = False
    paper_tests_passed: bool = False
    kill_switch_tested: bool = False
    owner_confirmed_this_order: bool = False

    def missing(self, need_confirmation: bool) -> list[str]:
        items = {k: v for k, v in self.__dict__.items()}
        if not need_confirmation:
            items.pop("owner_confirmed_this_order")
        return [k for k, v in items.items() if not v]


@dataclass(frozen=True)
class RiskContext:
    now: dt.datetime
    market: MarketSpec
    instrument: Instrument
    reference_price: Decimal
    available_cash: Decimal
    equity: Decimal
    position_qty: Decimal
    open_positions: int
    start_of_day_equity: Decimal
    fee_rate: Decimal
    est_slippage: Decimal
    survival_state: SurvivalState
    kill_switch: bool = False
    last_closed_trade_pnl: Decimal | None = None
    last_entry_notional: Decimal | None = None
    live_gates: LiveGates = field(default_factory=LiveGates)


@dataclass
class RiskDecision:
    approved: bool
    order_id: str
    reasons: list[str]
    checks: dict[str, bool]
    est_notional: Decimal
    est_fees_round_trip: Decimal
    est_slippage_cost: Decimal

    def as_dict(self) -> dict[str, object]:
        return {
            "approved": self.approved, "order_id": self.order_id, "reasons": self.reasons,
            "checks": self.checks, "est_notional": str(self.est_notional),
            "est_fees_round_trip": str(self.est_fees_round_trip),
            "est_slippage_cost": str(self.est_slippage_cost),
        }


class RiskEngine:
    def __init__(self, config: RiskConfig | None = None) -> None:
        self.config = config or RiskConfig()

    def evaluate(self, order: OrderRequest, ctx: RiskContext) -> RiskDecision:
        cfg = self.config
        checks: dict[str, bool] = {}
        reasons: list[str] = []

        def check(name: str, ok: bool, why: str) -> None:
            checks[name] = ok
            if not ok:
                reasons.append(why)

        price = order.limit_price or ctx.reference_price
        notional = order.quantity * price
        fees_rt = notional * ctx.fee_rate * 2
        slip = notional * ctx.est_slippage * 2
        opening = order.side == Side.BUY

        # Owner-placed PAPER orders: survival-state and per-order caps govern the automated bot, not the
        # owner's own practice trades. Kill switch, funds, minimum size and exposure still apply. LIVE always checked.
        owner_paper = order.mode == TradingMode.PAPER and order.requested_by.startswith("owner:")
        check("kill_switch", not ctx.kill_switch, "emergency kill switch engaged")
        if opening and not owner_paper:
            check("survival_allows_new_trades",
                  ctx.survival_state not in (SurvivalState.CRITICAL, SurvivalState.DEAD),
                  f"survival state {ctx.survival_state} forbids opening trades")

        if order.mode == TradingMode.LIVE:
            missing = ctx.live_gates.missing(cfg.require_owner_confirmation_live)
            check("live_gates", not missing, f"live trading gates not satisfied: {missing}")
            check("market_enabled_live", ctx.market.enabled_for_live, "market not enabled for live")
        else:
            check("market_enabled_paper", ctx.market.enabled_for_paper, "market not enabled for paper")

        check("leverage", not ctx.market.allows_leverage or IMMUTABLE.allow_leverage,
              "leveraged market blocked by immutable policy")
        check("market_open", ctx.market.is_open(ctx.now), "market closed")
        inst = ctx.instrument
        check("instrument_match", inst.symbol == order.symbol and inst.market == order.market,
              "instrument/market mismatch")
        check("min_qty", order.quantity >= inst.min_qty, f"quantity below minimum {inst.min_qty}")
        check("qty_step", floor_to_step(order.quantity, inst.qty_step) == order.quantity,
              f"quantity not a multiple of step {inst.qty_step}")
        check("min_notional", notional >= inst.min_notional,
              f"notional {notional:.4f} below exchange minimum {inst.min_notional}")
        if not owner_paper:
            check("max_order_notional", notional <= cfg.max_order_notional, "order exceeds max notional")

        if opening:
            check("funds", notional * (1 + ctx.fee_rate) <= ctx.available_cash,
                  "insufficient funds (borrowing is never allowed)")
            check("cost_economics", notional > 0 and (fees_rt + slip) / notional <= cfg.max_cost_fraction,
                  "uneconomical: estimated round-trip costs exceed allowed share of notional")
            after = (ctx.position_qty + order.quantity) * price
            check("exposure", ctx.equity > 0 and after / ctx.equity <= cfg.max_position_fraction,
                  "position would exceed max exposure")
            check("max_open_positions",
                  ctx.position_qty > 0 or ctx.open_positions < cfg.max_open_positions,
                  "too many open positions")
            daily = (ctx.equity - ctx.start_of_day_equity) / ctx.start_of_day_equity \
                if ctx.start_of_day_equity > 0 else ZERO
            check("daily_loss_limit", daily > -cfg.max_daily_loss_fraction,
                  "daily loss limit reached; no new trades today")
            if ctx.last_closed_trade_pnl is not None and ctx.last_closed_trade_pnl < 0 \
                    and ctx.last_entry_notional is not None:
                check("no_martingale", notional <= ctx.last_entry_notional,
                      "order larger than previous after a loss (martingale blocked)")
        else:
            check("no_short", order.quantity <= ctx.position_qty,
                  "cannot sell more than held (short selling disabled)")

        return RiskDecision(not reasons, order.client_order_id, reasons, checks, notional, fees_rt, slip)
