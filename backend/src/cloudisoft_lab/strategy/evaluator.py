"""Turn a StrategyDefinition into boolean entry/exit signal series (causal)."""

from __future__ import annotations

import pandas as pd

from cloudisoft_lab.indicators import compute
from cloudisoft_lab.strategy.schema import Condition, ConditionGroup, Operand, StrategyDefinition


def _operand(df: pd.DataFrame, o: Operand) -> pd.Series:
    if o.value is not None:
        return pd.Series(o.value, index=df.index, dtype=float)
    assert o.indicator is not None
    return compute(df, o.indicator, o.params).astype(float)


def _condition(df: pd.DataFrame, c: Condition) -> pd.Series:
    a, b = _operand(df, c.left), _operand(df, c.right)
    valid = a.notna() & b.notna()
    match c.op:
        case ">":
            r = a > b
        case "<":
            r = a < b
        case ">=":
            r = a >= b
        case "<=":
            r = a <= b
        case "crosses_above":
            r = (a > b) & (a.shift(1) <= b.shift(1))
        case "crosses_below":
            r = (a < b) & (a.shift(1) >= b.shift(1))
    return (r & valid).fillna(False).astype(bool)


def evaluate_group(df: pd.DataFrame, g: ConditionGroup) -> pd.Series:
    parts = [
        evaluate_group(df, c) if isinstance(c, ConditionGroup) else _condition(df, c)
        for c in g.conditions
    ]
    out = parts[0]
    for p in parts[1:]:
        out = (out & p) if g.logic == "AND" else (out | p)
    return out


def signals(df: pd.DataFrame, s: StrategyDefinition) -> pd.DataFrame:
    entry = evaluate_group(df, s.entry)
    exit_ = evaluate_group(df, s.exit) if s.exit else pd.Series(False, index=df.index)
    return pd.DataFrame({"entry": entry, "exit": exit_})
