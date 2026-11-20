from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from cloudisoft_lab.backtest.engine import Trade


@dataclass(frozen=True)
class PerformanceMetrics:
    net_return: float
    annualised_return: float
    win_rate: float
    profit_factor: float
    sharpe: float
    sortino: float
    max_drawdown: float
    expectancy: float
    avg_win: float
    avg_loss: float
    total_fees: float
    num_trades: int
    recovery_factor: float
    final_equity: float

    def as_dict(self) -> dict[str, float]:
        return {k: (None if isinstance(v, float) and not math.isfinite(v) else v)
                for k, v in asdict(self).items()}  # type: ignore[misc]


def max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    peak = equity.cummax()
    return float(((equity - peak) / peak).min())


def compute_metrics(
    equity: pd.Series, trades: list[Trade], initial: float, bars_per_year: float
) -> PerformanceMetrics:
    final = float(equity.iloc[-1]) if len(equity) else initial
    net = final / initial - 1 if initial else 0.0
    years = len(equity) / bars_per_year if bars_per_year else 0
    ann = (1 + net) ** (1 / years) - 1 if years > 0 and net > -1 else float("nan")
    rets = equity.pct_change().dropna()
    sd = rets.std(ddof=0)
    sharpe = float(rets.mean() / sd * math.sqrt(bars_per_year)) if sd and sd > 0 else 0.0
    downside = rets[rets < 0]
    dsd = math.sqrt(float((downside**2).mean())) if len(downside) else 0.0
    sortino = float(rets.mean() / dsd * math.sqrt(bars_per_year)) if dsd > 0 else 0.0
    pnls = np.array([t.pnl for t in trades])
    wins, losses = pnls[pnls > 0], pnls[pnls <= 0]
    gross_loss = -losses.sum()
    pf = float(wins.sum() / gross_loss) if gross_loss > 0 else (float("inf") if len(wins) else 0.0)
    mdd = max_drawdown(equity)
    net_profit = final - initial
    return PerformanceMetrics(
        net_return=net,
        annualised_return=ann,
        win_rate=float(len(wins) / len(pnls)) if len(pnls) else 0.0,
        profit_factor=pf,
        sharpe=sharpe,
        sortino=sortino,
        max_drawdown=mdd,
        expectancy=float(pnls.mean()) if len(pnls) else 0.0,
        avg_win=float(wins.mean()) if len(wins) else 0.0,
        avg_loss=float(losses.mean()) if len(losses) else 0.0,
        total_fees=float(sum(t.entry_fee + t.exit_fee for t in trades)),
        num_trades=len(trades),
        recovery_factor=float(net_profit / (abs(mdd) * initial)) if mdd < 0 else 0.0,
        final_equity=final,
    )
