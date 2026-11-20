"""The Lab: wires providers, risk, execution, survival and the paper-trading loop together."""

from __future__ import annotations

import asyncio
import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal

import pandas as pd

from cloudisoft_lab.agents.scanner import scan
from cloudisoft_lab.audit import AuditTrail
from cloudisoft_lab.core.config import Settings
from cloudisoft_lab.core.logging import get_logger
from cloudisoft_lab.core.money import ZERO, floor_to_step
from cloudisoft_lab.data.quality import check_candles
from cloudisoft_lab.domain.enums import DataOrigin, MarketKind, Side, TradingMode
from cloudisoft_lab.domain.schemas import OrderRequest
from cloudisoft_lab.execution.paper_broker import PaperBroker
from cloudisoft_lab.execution.router import ExecutionRouter
from cloudisoft_lab.interfaces import MarketDataProvider
from cloudisoft_lab.markets.registry import MARKETS
from cloudisoft_lab.risk.engine import RiskContext, RiskEngine
from cloudisoft_lab.strategy.evaluator import signals
from cloudisoft_lab.strategy.schema import StrategyDefinition
from cloudisoft_lab.strategy.templates import ema_crossover
from cloudisoft_lab.survival.engine import SurvivalEngine, SurvivalReport, TradeStat
from cloudisoft_lab.survival.ledger import Entry, SurvivalLedger

log = get_logger(__name__)


@dataclass
class Lab:
    settings: Settings
    provider: MarketDataProvider
    strategy: StrategyDefinition = field(default_factory=ema_crossover)
    audit: AuditTrail = field(default_factory=AuditTrail)
    ledger: SurvivalLedger = field(default_factory=SurvivalLedger)
    kill_switch: bool = False
    started_at: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))
    ticks: int = 0
    last_error: str | None = None
    last_scan: list[dict[str, object]] = field(default_factory=list)
    closed_trades: list[TradeStat] = field(default_factory=list)
    equity_curve: list[tuple[str, float]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.paper = PaperBroker(Decimal(str(self.settings.paper_starting_balance_usd)))
        self.risk = RiskEngine()
        self.router = ExecutionRouter(self.risk, self.paper, self.audit)
        self.survival = SurvivalEngine(self.ledger)
        self.kill_switch = self.settings.kill_switch_engaged
        self._start_of_day = (self.started_at.date(), self.paper.equity())
        self.audit.record("lab.start", "system", {"mode": "paper", "live_allowed": self.settings.live_trading_allowed})

    # ------------------------------------------------------------------
    def survival_report(self, now: dt.datetime | None = None) -> SurvivalReport:
        now = now or dt.datetime.now(dt.UTC)
        eq = pd.Series([v for _, v in self.equity_curve] or [float(self.paper.equity())])
        mdd = Decimal(str(float(((eq - eq.cummax()) / eq.cummax()).min())))
        return self.survival.evaluate(now, self.closed_trades, self.started_at, mdd)

    def engage_kill_switch(self, actor: str, engaged: bool = True) -> None:
        self.kill_switch = engaged
        self.audit.record("kill_switch", actor, {"engaged": engaged})

    async def tick(self, now: dt.datetime | None = None) -> dict[str, object]:
        now = now or dt.datetime.now(dt.UTC)
        self.ticks += 1
        report = self.survival_report(now)
        frames: dict[str, pd.DataFrame] = {}
        for sym in self.settings.paper_symbols:
            try:
                df = await self.provider.get_candles(sym, self.settings.paper_interval, 300)
            except Exception as exc:  # provider outage: keep monitoring, open nothing
                self.last_error = f"{sym}: {exc}"
                self.audit.record("market_data.error", "market_scanner", {"symbol": sym, "error": str(exc)})
                continue
            q = check_candles(df)
            if not q.ok:
                self.audit.record("market_data.rejected", "market_scanner", {"symbol": sym, "issues": q.issues})
                continue
            frames[sym] = df
            self.paper.mark(sym, Decimal(str(float(df["close"].iloc[-1]))))
        # Scanning is rule-based (no inference cost), so it runs in every state but DEAD.
        self.last_scan = [m.payload for m in scan(frames)] if report.policy.risk_monitoring else []

        if now.date() != self._start_of_day[0]:
            self._start_of_day = (now.date(), self.paper.equity())

        actions = []
        for sym, df in frames.items():
            sig = signals(df, self.strategy).iloc[-1]
            held = self.paper.positions.get(sym)
            qty_held = held.qty if held else ZERO
            price = self.paper.marks[sym]
            side: Side | None = None
            qty = ZERO
            if qty_held > 0 and (sig["exit"] or self._protective_exit(sym, price)):
                side, qty = Side.SELL, qty_held
            elif qty_held == 0 and sig["entry"]:
                inst = await self.provider.get_instrument(sym)
                budget = self.paper.cash * Decimal(str(self.strategy.risk.position_fraction))
                qty = floor_to_step(budget / (price * Decimal("1.002")), inst.qty_step)
                side = Side.BUY if qty > 0 else None
            if side is None:
                continue
            actions.append(await self._submit(sym, side, qty, price, report, now))

        eq = float(self.paper.equity())
        self.equity_curve.append((now.isoformat(), eq))
        self.equity_curve = self.equity_curve[-2000:]
        return {"tick": self.ticks, "state": report.state, "actions": actions, "equity": eq}

    def _protective_exit(self, sym: str, price: Decimal) -> bool:
        pos = self.paper.positions[sym]
        r = self.strategy.risk
        if r.stop_loss_pct and price <= pos.avg * (1 - Decimal(str(r.stop_loss_pct))):
            return True
        return bool(r.take_profit_pct and price >= pos.avg * (1 + Decimal(str(r.take_profit_pct))))

    async def _submit(self, sym: str, side: Side, qty: Decimal, price: Decimal, report: SurvivalReport,
                      now: dt.datetime) -> dict[str, object]:
        inst = await self.provider.get_instrument(sym)
        held = self.paper.positions.get(sym)
        order = OrderRequest(mode=TradingMode.PAPER, market=MarketKind.CRYPTO, symbol=sym, side=side,
                             quantity=qty, strategy_id=self.strategy.fingerprint(), requested_by="strategy_researcher")
        ctx = RiskContext(
            now=now, market=MARKETS[MarketKind.CRYPTO], instrument=inst, reference_price=price,
            available_cash=self.paper.cash, equity=self.paper.equity(),
            position_qty=held.qty if held else ZERO,
            open_positions=sum(1 for p in self.paper.positions.values() if p.qty > 0),
            start_of_day_equity=self._start_of_day[1], fee_rate=self.paper.fee_rate,
            est_slippage=self.paper.slippage, survival_state=report.state, kill_switch=self.kill_switch,
            last_closed_trade_pnl=self.paper.last_closed_trade_pnl,
            last_entry_notional=held.last_entry_notional if held else None,
        )
        before = self.paper.realised_pnl
        res, decision = await self.router.submit(order, ctx)
        if res.status == "filled":
            self.ledger.add(Entry.TRADING_FEE, res.fees, origin=DataOrigin.SIMULATED, at=now)
            if side == Side.SELL:
                gross = self.paper.realised_pnl - before
                self.ledger.add(Entry.REALISED_TRADING_PNL, gross, origin=DataOrigin.SIMULATED, at=now)
                self.closed_trades.append(TradeStat(now, self.paper.last_closed_trade_pnl or ZERO))
        return {"symbol": sym, "side": side, "qty": str(qty), "status": res.status,
                "reasons": decision.reasons, "origin": res.origin}

    async def run_forever(self) -> None:
        log.info("paper_loop.start", symbols=self.settings.paper_symbols)
        while True:
            try:
                out = await self.tick()
                log.info("paper_loop.tick", **{k: str(v) for k, v in out.items()})
            except Exception as exc:  # never die silently; keep monitoring
                self.last_error = str(exc)
                log.exception("paper_loop.error")
            mult = self.survival.policy.scan_interval_multiplier or 12.0
            await asyncio.sleep(self.settings.paper_loop_seconds * mult)
