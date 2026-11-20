"""Built-in strategy templates. These are starting points, not recommendations."""

from __future__ import annotations

from cloudisoft_lab.strategy.schema import StrategyDefinition


def ema_crossover(fast: int = 12, slow: int = 26) -> StrategyDefinition:
    return StrategyDefinition.model_validate(
        {
            "name": f"EMA {fast}/{slow} crossover + ADX filter",
            "entry": {
                "logic": "AND",
                "conditions": [
                    {"left": {"indicator": "ema", "params": {"period": fast}}, "op": "crosses_above",
                     "right": {"indicator": "ema", "params": {"period": slow}}},
                    {"left": {"indicator": "adx", "params": {"period": 14}}, "op": ">", "right": {"value": 20}},
                ],
            },
            "exit": {"logic": "OR", "conditions": [
                {"left": {"indicator": "ema", "params": {"period": fast}}, "op": "crosses_below",
                 "right": {"indicator": "ema", "params": {"period": slow}}},
            ]},
            "risk": {"stop_loss_pct": 0.03, "take_profit_pct": 0.08, "position_fraction": 0.5},
        }
    )


def rsi_mean_reversion(low: float = 30, high: float = 60) -> StrategyDefinition:
    return StrategyDefinition.model_validate(
        {
            "name": f"RSI mean reversion {low}/{high} above SMA200",
            "entry": {"logic": "AND", "conditions": [
                {"left": {"indicator": "rsi", "params": {"period": 14}}, "op": "crosses_above",
                 "right": {"value": low}},
                {"left": {"indicator": "close"}, "op": ">", "right": {"indicator": "sma", "params": {"period": 200}}},
            ]},
            "exit": {"logic": "OR", "conditions": [
                {"left": {"indicator": "rsi", "params": {"period": 14}}, "op": ">", "right": {"value": high}},
            ]},
            "risk": {"stop_loss_pct": 0.04, "take_profit_pct": 0.06, "position_fraction": 0.5},
        }
    )


TEMPLATES = {"ema_crossover": ema_crossover, "rsi_mean_reversion": rsi_mean_reversion}
