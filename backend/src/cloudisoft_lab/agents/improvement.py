"""Improvement Researcher: proposes parameter changes only when they beat the current version
out-of-sample in walk-forward testing with costs. Produces a proposal, never applies it."""

from __future__ import annotations

import copy
from dataclasses import dataclass

import numpy as np
import pandas as pd

from cloudisoft_lab.backtest.engine import CostModel, run_backtest
from cloudisoft_lab.strategy.schema import StrategyDefinition


def _variants(s: StrategyDefinition, max_variants: int = 12) -> list[StrategyDefinition]:
    base = s.model_dump()
    out: list[StrategyDefinition] = []

    def walk(node: object, path: list[object]) -> list[list[object]]:
        found = []
        if isinstance(node, dict):
            if "period" in node.get("params", {}):
                found.append(path + ["params", "period"])
            if node.get("value") is not None and "indicator" in node and node["indicator"] is None:
                found.append(path + ["value"])
            for k, v in node.items():
                found += walk(v, path + [k])
        elif isinstance(node, list):
            for i, v in enumerate(node):
                found += walk(v, path + [i])
        return found

    knobs = walk({"entry": base["entry"], "exit": base["exit"]}, [])
    for path in knobs:
        for f in (0.75, 1.25):
            d = copy.deepcopy(base)
            ref = d
            for k in path[:-1]:
                ref = ref[k]  # type: ignore[index]
            ref[path[-1]] = round(float(ref[path[-1]]) * f, 2)  # type: ignore[index]
            try:
                out.append(StrategyDefinition.model_validate({**d, "version": s.version + 1}))
            except ValueError:
                pass
    for sl in (0.02, 0.05):
        d = copy.deepcopy(base)
        d["risk"]["stop_loss_pct"] = sl
        out.append(StrategyDefinition.model_validate({**d, "version": s.version + 1}))
    return out[:max_variants]


@dataclass
class ImprovementResult:
    improved: bool
    baseline_oos_sharpe: float
    best_oos_sharpe: float
    baseline_oos_trades: int
    best_oos_trades: int
    candidate: StrategyDefinition | None
    tested_variants: int
    note: str


def _oos(df: pd.DataFrame, s: StrategyDefinition, costs: CostModel, capital: float, folds: int) -> tuple[float, int]:
    n = len(df)
    size = n // folds
    sharpes, trades = [], 0
    for k in range(folds):
        seg = df.iloc[k * size:(k + 1) * size]
        test = seg.iloc[int(len(seg) * 0.7):]
        r = run_backtest(test, s, capital, costs)
        sharpes.append(r.metrics.sharpe)
        trades += r.metrics.num_trades
    return float(np.mean(sharpes)), trades


def research_improvement(df: pd.DataFrame, s: StrategyDefinition, costs: CostModel | None = None,
                         capital: float = 1000.0, folds: int = 4, min_trades: int = 10,
                         min_gain: float = 0.1) -> ImprovementResult:
    costs = costs or CostModel(min_notional=0)
    base_sh, base_tr = _oos(df, s, costs, capital, folds)
    best: tuple[float, int, StrategyDefinition | None] = (base_sh, base_tr, None)
    variants = _variants(s)
    for v in variants:
        sh, tr = _oos(df, v, costs, capital, folds)
        if tr >= min_trades and sh > best[0]:
            best = (sh, tr, v)
    improved = best[2] is not None and best[0] - base_sh >= min_gain
    note = ("candidate beats baseline out-of-sample; owner approval required" if improved
            else "no variant improved out-of-sample by the required margin; keep current version")
    return ImprovementResult(improved, base_sh, best[0], base_tr, best[1], best[2] if improved else None,
                             len(variants), note)
