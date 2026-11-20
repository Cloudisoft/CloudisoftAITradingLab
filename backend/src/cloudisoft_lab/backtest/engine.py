"""Event-driven, bar-based backtester with conservative execution assumptions.

Execution model (documented in ARCHITECTURE.md):
* Signals are computed on bar *t* close and filled at bar *t+1* **open** (no look-ahead).
* Buys pay ``open * (1 + half_spread + slippage)``; sells receive ``open * (1 - ...)``.
* Fees are charged on notional for every fill.
* Fill size is capped at ``max_volume_participation`` × bar volume (partial fills).
* Stop-loss / take-profit / trailing stops are checked intrabar from t+1 onwards. If
  both stop and target are touched in one bar the **stop** is assumed (pessimistic).
  Gaps through a stop fill at the (worse) open.
* Optional per-bar funding cost on open notional (perpetuals); 0 for spot.
* Bars where the market is closed are skipped for new orders.
* Orders below ``min_notional`` or that round to zero at ``qty_step`` are skipped and
  counted as ``skipped_uneconomical``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from cloudisoft_lab.backtest.metrics import PerformanceMetrics, compute_metrics
from cloudisoft_lab.markets.registry import MarketSpec
from cloudisoft_lab.strategy.evaluator import signals
from cloudisoft_lab.strategy.schema import StrategyDefinition


@dataclass(frozen=True)
class CostModel:
    fee_rate: float = 0.001  # 0.10% per side (typical spot taker; verify per provider)
    half_spread: float = 0.0002
    slippage: float = 0.0005
    funding_rate_per_bar: float = 0.0
    max_volume_participation: float = 0.05
    min_notional: float = 5.0
    qty_step: float = 1e-6


@dataclass
class Trade:
    entry_time: pd.Timestamp
    entry_price: float
    quantity: float
    entry_fee: float
    exit_time: pd.Timestamp | None = None
    exit_price: float | None = None
    exit_fee: float = 0.0
    funding: float = 0.0
    exit_reason: str = ""

    @property
    def pnl(self) -> float:
        if self.exit_price is None:
            return 0.0
        gross = (self.exit_price - self.entry_price) * self.quantity
        return gross - self.entry_fee - self.exit_fee - self.funding

    @property
    def return_pct(self) -> float:
        cost = self.entry_price * self.quantity + self.entry_fee
        return self.pnl / cost if cost else 0.0


@dataclass
class BacktestResult:
    strategy_name: str
    strategy_version: int
    equity: pd.Series
    trades: list[Trade]
    metrics: PerformanceMetrics
    skipped_uneconomical: int = 0
    partial_fills: int = 0
    assumptions: dict[str, object] = field(default_factory=dict)
    label: str = "SIMULATED — historical backtest; not a guarantee of future results"


def _floor(q: float, step: float) -> float:
    return math.floor(q / step + 1e-12) * step if step > 0 else q


def run_backtest(
    df: pd.DataFrame,
    strategy: StrategyDefinition,
    initial_capital: float = 5.0,
    costs: CostModel | None = None,
    market: MarketSpec | None = None,
    bars_per_year: float = 24 * 365,
) -> BacktestResult:
    costs = costs or CostModel()
    required = {"open", "high", "low", "close", "volume"}
    if not required.issubset(df.columns):
        raise ValueError(f"data missing columns: {required - set(df.columns)}")
    if not df.index.is_monotonic_increasing or df.index.has_duplicates:
        raise ValueError("data index must be strictly increasing timestamps")
    df = df.dropna(subset=list(required))

    sig = signals(df, strategy)
    risk = strategy.risk
    o, h, l, c, v = (df[k].to_numpy(float) for k in ("open", "high", "low", "close", "volume"))
    idx = df.index
    entry_sig, exit_sig = sig["entry"].to_numpy(), sig["exit"].to_numpy()

    cash = initial_capital
    pos: Trade | None = None
    peak = 0.0
    trades: list[Trade] = []
    equity = np.empty(len(df))
    skipped = partial = 0
    buy_mult = 1 + costs.half_spread + costs.slippage
    sell_mult = 1 - costs.half_spread - costs.slippage

    def close_pos(i: int, raw_price: float, reason: str) -> None:
        nonlocal cash, pos
        assert pos is not None
        px = raw_price * sell_mult
        fee = px * pos.quantity * costs.fee_rate
        pos.exit_time, pos.exit_price, pos.exit_fee, pos.exit_reason = idx[i], px, fee, reason
        cash += px * pos.quantity - fee
        trades.append(pos)
        pos = None

    for i in range(len(df)):
        # 1) act at this bar's open on the PREVIOUS bar's signals
        if i > 0:
            if pos is not None and exit_sig[i - 1]:
                close_pos(i, o[i], "exit_signal")
            elif pos is None and entry_sig[i - 1] and (market is None or market.is_open(idx[i].to_pydatetime())):
                px = o[i] * buy_mult
                budget = cash * risk.position_fraction
                qty = budget / (px * (1 + costs.fee_rate))
                cap = v[i] * costs.max_volume_participation
                if qty > cap:
                    qty, partial = cap, partial + 1
                qty = _floor(qty, costs.qty_step)
                if qty <= 0 or qty * px < costs.min_notional:
                    skipped += 1
                else:
                    fee = qty * px * costs.fee_rate
                    cash -= qty * px + fee
                    pos = Trade(idx[i], px, qty, fee)
                    peak = o[i]

        # 2) intrabar protective exits (bar i, including the entry bar)
        if pos is not None:
            raw_entry = pos.entry_price / buy_mult
            peak = max(peak, h[i])
            stops = []
            if risk.stop_loss_pct:
                stops.append(raw_entry * (1 - risk.stop_loss_pct))
            if risk.trailing_stop_pct:
                stops.append(peak * (1 - risk.trailing_stop_pct))
            stop = max(stops) if stops else None
            target = raw_entry * (1 + risk.take_profit_pct) if risk.take_profit_pct else None
            if stop is not None and l[i] <= stop:
                close_pos(i, min(o[i], stop), "stop")
            elif target is not None and h[i] >= target:
                close_pos(i, max(o[i], target), "take_profit")
            elif risk.max_holding_bars and idx.get_loc(pos.entry_time) + risk.max_holding_bars <= i:
                close_pos(i, c[i], "time_exit")

        if pos is not None and costs.funding_rate_per_bar:
            f = pos.quantity * c[i] * costs.funding_rate_per_bar
            pos.funding += f
            cash -= f
        equity[i] = cash + (pos.quantity * c[i] * sell_mult if pos else 0.0)

    if pos is not None:  # mark open trade closed at the final close for reporting
        close_pos(len(df) - 1, c[-1], "end_of_data")
        equity[-1] = cash

    eq = pd.Series(equity, index=idx, name="equity")
    return BacktestResult(
        strategy_name=strategy.name,
        strategy_version=strategy.version,
        equity=eq,
        trades=trades,
        metrics=compute_metrics(eq, trades, initial_capital, bars_per_year),
        skipped_uneconomical=skipped,
        partial_fills=partial,
        assumptions={**costs.__dict__, "fill": "next_bar_open", "same_bar_stop_and_target": "stop"},
    )
