"""Portfolio Analyst: allocation, concentration and correlation of current holdings."""

from __future__ import annotations

from decimal import Decimal

import pandas as pd


def analyse(positions: dict[str, Decimal], prices: dict[str, Decimal], cash: Decimal,
            returns: dict[str, pd.Series] | None = None) -> dict[str, object]:
    values = {s: float(q * prices.get(s, Decimal(0))) for s, q in positions.items() if q > 0}
    total = sum(values.values()) + float(cash)
    weights = {s: v / total for s, v in values.items()} if total else {}
    weights_cash = float(cash) / total if total else 1.0
    hhi = sum(w * w for w in weights.values())
    out: dict[str, object] = {
        "total_value": total, "cash_weight": weights_cash, "weights": weights,
        "largest_position": max(weights.items(), key=lambda kv: kv[1]) if weights else None,
        "hhi": hhi, "effective_positions": (1 / hhi) if hhi else 0,
        "warnings": [f"{s} is {w:.0%} of portfolio" for s, w in weights.items() if w > 0.5],
    }
    if returns and len(returns) > 1:
        df = pd.DataFrame(returns).dropna()
        corr = df.corr()
        out["correlation"] = corr.round(3).to_dict()
        high = [(a, b, float(corr.loc[a, b])) for i, a in enumerate(corr) for b in list(corr)[i + 1:]
                if corr.loc[a, b] > 0.8]
        if high:
            out["warnings"] += [f"{a}/{b} highly correlated ({c:.2f})" for a, b, c in high]  # type: ignore[operator]
    return out
