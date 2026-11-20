"""Overfitting defences: grid optimisation, out-of-sample split, walk-forward, Monte Carlo."""

from __future__ import annotations

import itertools
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from cloudisoft_lab.backtest.engine import BacktestResult, CostModel, run_backtest
from cloudisoft_lab.strategy.schema import StrategyDefinition

Builder = Callable[..., StrategyDefinition]


def _score(r: BacktestResult, min_trades: int) -> float:
    # Penalise tiny samples so the optimiser cannot "win" with 1 lucky trade.
    if r.metrics.num_trades < min_trades:
        return -np.inf
    return r.metrics.sharpe


def grid_optimise(
    df: pd.DataFrame, builder: Builder, grid: dict[str, list[float]], costs: CostModel,
    capital: float, min_trades: int = 5,
) -> tuple[dict[str, float], BacktestResult | None]:
    best: tuple[float, dict[str, float], BacktestResult | None] = (-np.inf, {}, None)
    keys = list(grid)
    for combo in itertools.product(*grid.values()):
        params = dict(zip(keys, combo, strict=True))
        r = run_backtest(df, builder(**params), capital, costs)
        s = _score(r, min_trades)
        if s > best[0]:
            best = (s, params, r)
    return best[1], best[2]


@dataclass
class WalkForwardFold:
    train_start: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    params: dict[str, float]
    in_sample_sharpe: float | None
    out_of_sample: BacktestResult | None


def walk_forward(
    df: pd.DataFrame, builder: Builder, grid: dict[str, list[float]], costs: CostModel,
    capital: float = 5.0, folds: int = 4, train_frac: float = 0.7, min_trades: int = 3,
) -> list[WalkForwardFold]:
    """Anchored-rolling walk-forward. Test windows never overlap their training window."""
    n = len(df)
    size = n // folds
    out: list[WalkForwardFold] = []
    for k in range(folds):
        seg = df.iloc[k * size : (k + 1) * size if k < folds - 1 else n]
        cut = int(len(seg) * train_frac)
        train, test = seg.iloc[:cut], seg.iloc[cut:]
        params, ins = grid_optimise(train, builder, grid, costs, capital, min_trades)
        oos = run_backtest(test, builder(**params), capital, costs) if params else None
        out.append(WalkForwardFold(train.index[0], test.index[0], test.index[-1], params,
                                   ins.metrics.sharpe if ins else None, oos))
    return out


def out_of_sample_split(df: pd.DataFrame, frac: float = 0.7) -> tuple[pd.DataFrame, pd.DataFrame]:
    cut = int(len(df) * frac)
    return df.iloc[:cut], df.iloc[cut:]


@dataclass(frozen=True)
class MonteCarloReport:
    simulations: int
    prob_loss: float
    median_return: float
    p5_return: float
    p95_return: float
    median_max_drawdown: float
    p95_max_drawdown: float


def monte_carlo(trade_returns: list[float], simulations: int = 2000, seed: int = 7) -> MonteCarloReport:
    """Bootstrap trade-return sequences to estimate the distribution of outcomes."""
    rng = np.random.default_rng(seed)
    r = np.asarray(trade_returns, dtype=float)
    if r.size == 0:
        return MonteCarloReport(simulations, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    samples = rng.choice(r, size=(simulations, r.size), replace=True)
    curves = np.cumprod(1 + samples, axis=1)
    finals = curves[:, -1] - 1
    peaks = np.maximum.accumulate(np.concatenate([np.ones((simulations, 1)), curves], axis=1), axis=1)[:, 1:]
    mdd = ((curves - peaks) / peaks).min(axis=1)
    return MonteCarloReport(
        simulations, float((finals < 0).mean()), float(np.median(finals)),
        float(np.percentile(finals, 5)), float(np.percentile(finals, 95)),
        float(np.median(mdd)), float(np.percentile(mdd, 5)),
    )
