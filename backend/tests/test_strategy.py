import pytest
from pydantic import ValidationError

from cloudisoft_lab.data.synthetic import make_ohlcv
from cloudisoft_lab.strategy.evaluator import signals
from cloudisoft_lab.strategy.schema import StrategyDefinition
from cloudisoft_lab.strategy.templates import ema_crossover, rsi_mean_reversion


def test_templates_validate_and_signal():
    df = make_ohlcv(2000, "volatile", seed=3)
    for s in (ema_crossover(), rsi_mean_reversion()):
        sig = signals(df, s)
        assert sig.dtypes.eq(bool).all()
        assert sig["entry"].sum() > 0


def test_and_or_logic():
    df = make_ohlcv(200)
    base = {"name": "t", "entry": {"logic": "AND", "conditions": [
        {"left": {"indicator": "close"}, "op": ">", "right": {"value": 0}},
        {"left": {"indicator": "close"}, "op": "<", "right": {"value": 0}}]}}
    assert signals(df, StrategyDefinition.model_validate(base))["entry"].sum() == 0
    base["entry"]["logic"] = "OR"
    assert signals(df, StrategyDefinition.model_validate(base))["entry"].all()


def test_nested_groups():
    s = StrategyDefinition.model_validate({"name": "n", "entry": {"logic": "AND", "conditions": [
        {"left": {"indicator": "close"}, "op": ">", "right": {"value": 0}},
        {"logic": "OR", "conditions": [{"left": {"indicator": "rsi"}, "op": "<", "right": {"value": 50}},
                                        {"left": {"indicator": "rsi"}, "op": ">=", "right": {"value": 50}}]}]}})
    sig = signals(make_ohlcv(100), s)
    assert sig["entry"].iloc[20:].all()  # rsi defined after warm-up


def test_invalid_definitions_rejected():
    with pytest.raises(ValidationError):
        StrategyDefinition.model_validate({"name": "x", "entry": {"conditions": [
            {"left": {"indicator": "magic"}, "op": ">", "right": {"value": 1}}]}})
    with pytest.raises(ValidationError):
        StrategyDefinition.model_validate({"name": "x", "entry": {"conditions": []}})
    with pytest.raises(ValidationError):  # shorting not allowed
        StrategyDefinition.model_validate({"name": "x", "long_only": False, "entry": {"conditions": [
            {"left": {"value": 1}, "op": ">", "right": {"value": 0}}]}})


def test_versioning_changes_fingerprint():
    s = ema_crossover()
    s2 = s.bump(description="tweak")
    assert s2.version == 2 and s2.fingerprint() != s.fingerprint()
    assert s.bump().fingerprint() == s.fingerprint()  # version alone isn't content
