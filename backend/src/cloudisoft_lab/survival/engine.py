"""Survival state machine and per-state operating policy."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal

from pydantic import BaseModel, Field

from cloudisoft_lab.core.money import ZERO
from cloudisoft_lab.domain.enums import SurvivalState
from cloudisoft_lab.survival.ledger import SurvivalLedger


class SurvivalConfig(BaseModel):
    high_runway_days: Decimal = Decimal(90)
    low_compute_runway_days: Decimal = Decimal(14)
    critical_runway_days: Decimal = Decimal(3)
    burn_window_days: int = 7
    # PROFITABLE classification requirements
    min_evaluation_days: int = Field(default=30, ge=7)
    min_trades: int = Field(default=50, ge=10)
    min_profitable_period_share: Decimal = Decimal("0.6")  # share of weekly periods net-positive
    max_drawdown_fraction: Decimal = Decimal("0.2")
    reserve_days: Decimal = Decimal(30)


@dataclass(frozen=True)
class StatePolicy:
    open_new_trades: bool
    scan_interval_multiplier: float
    model_tier: str  # "premium" | "standard" | "economy" | "none"
    run_non_essential_jobs: bool
    risk_monitoring: bool = True
    notify_owner: bool = False
    expansion_proposals: bool = False


POLICIES: dict[SurvivalState, StatePolicy] = {
    SurvivalState.HIGH: StatePolicy(True, 1.0, "premium", True),
    SurvivalState.NORMAL: StatePolicy(True, 1.0, "standard", True),
    SurvivalState.LOW_COMPUTE: StatePolicy(True, 4.0, "economy", False, notify_owner=True),
    SurvivalState.CRITICAL: StatePolicy(False, 12.0, "economy", False, notify_owner=True),
    SurvivalState.DEAD: StatePolicy(False, 0.0, "none", False, risk_monitoring=True, notify_owner=True),
    SurvivalState.PROFITABLE: StatePolicy(True, 1.0, "standard", True, expansion_proposals=True),
}


@dataclass(frozen=True)
class SurvivalReport:
    state: SurvivalState
    previous: SurvivalState | None
    at: dt.datetime
    survival_balance: Decimal
    daily_burn: Decimal
    runway_days: Decimal | None  # None == no burn
    summary: dict[str, Decimal]
    policy: StatePolicy
    profitability: dict[str, object]
    reasons: list[str]


@dataclass
class TradeStat:
    closed_at: dt.datetime
    net_pnl: Decimal


@dataclass
class SurvivalEngine:
    ledger: SurvivalLedger
    config: SurvivalConfig = field(default_factory=SurvivalConfig)
    state: SurvivalState = SurvivalState.NORMAL
    history: list[tuple[dt.datetime, SurvivalState, str]] = field(default_factory=list)
    awaiting_owner_recovery: bool = False

    def profitability(self, now: dt.datetime, trades: list[TradeStat], first_activity: dt.datetime | None,
                      max_drawdown: Decimal) -> dict[str, object]:
        c = self.config
        days = (now - first_activity).days if first_activity else 0
        weeks: dict[int, Decimal] = {}
        s = self.ledger.summary()
        for t in trades:
            wk = (t.closed_at - first_activity).days // 7 if first_activity else 0
            weeks[wk] = weeks.get(wk, ZERO) + t.net_pnl
        share = (Decimal(sum(1 for v in weeks.values() if v > 0)) / len(weeks)) if weeks else ZERO
        checks = {
            "evaluation_days": days >= c.min_evaluation_days,
            "trade_count": len(trades) >= c.min_trades,
            "net_operating_profit_positive": s["net_operating_profit"] > 0,
            "consistency": share >= c.min_profitable_period_share,
            "drawdown_within_limit": abs(max_drawdown) <= c.max_drawdown_fraction,
        }
        return {"sustained": all(checks.values()), "checks": checks, "days": days,
                "trades": len(trades), "profitable_week_share": str(share)}

    def evaluate(self, now: dt.datetime, trades: list[TradeStat] | None = None,
                 first_activity: dt.datetime | None = None, max_drawdown: Decimal = ZERO) -> SurvivalReport:
        c = self.config
        s = self.ledger.summary()
        burn = self.ledger.daily_burn(now, c.burn_window_days)
        bal = s["survival_balance"]
        runway = (bal / burn) if burn > 0 else None
        prof = self.profitability(now, trades or [], first_activity, max_drawdown)
        reasons: list[str] = []

        if not self.ledger.has_actual_activity():
            new = SurvivalState.NORMAL
            reasons.append("no economic activity recorded yet; owner should record the operating budget")
        elif self.awaiting_owner_recovery:
            new = SurvivalState.DEAD
            reasons.append("DEAD: awaiting owner-authorised recovery")
        elif bal <= 0:
            new = SurvivalState.DEAD
            reasons.append("survival balance exhausted")
        elif runway is not None and runway < c.critical_runway_days:
            new = SurvivalState.CRITICAL
            reasons.append(f"runway {runway:.1f}d < {c.critical_runway_days}d")
        elif runway is not None and runway < c.low_compute_runway_days:
            new = SurvivalState.LOW_COMPUTE
            reasons.append(f"runway {runway:.1f}d < {c.low_compute_runway_days}d")
        elif prof["sustained"]:
            new = SurvivalState.PROFITABLE
            reasons.append("sustained net operating profitability verified")
        elif runway is None or runway >= c.high_runway_days:
            new = SurvivalState.HIGH
        else:
            new = SurvivalState.NORMAL

        prev = self.state
        if new == SurvivalState.DEAD:
            self.awaiting_owner_recovery = True
        if new != prev:
            self.history.append((now, new, "; ".join(reasons) or "threshold"))
            self.state = new
        return SurvivalReport(new, prev, now, bal, burn, runway, s, POLICIES[new], prof, reasons)

    def owner_authorise_recovery(self, now: dt.datetime, owner_id: str) -> None:
        """Only an explicit owner action can leave DEAD. It does NOT add funds itself."""
        self.awaiting_owner_recovery = False
        self.history.append((now, self.state, f"owner {owner_id} authorised recovery"))

    @property
    def policy(self) -> StatePolicy:
        return POLICIES[self.state]
