import numpy as np
import pandas as pd
import pytest

from cloudisoft_lab import indicators as ta
from cloudisoft_lab.data.synthetic import make_ohlcv


def test_sma_ema_basic():
    s = pd.Series([1.0, 2, 3, 4, 5])
    assert ta.sma(s, 3).iloc[-1] == 4
    assert np.isnan(ta.sma(s, 3).iloc[1])
    assert ta.ema(s, 2).iloc[-1] > ta.sma(s, 2).iloc[-1] - 1


def test_rsi_bounds_and_extremes():
    up = pd.Series(np.arange(1, 60, dtype=float))
    assert ta.rsi(up).iloc[-1] == pytest.approx(100)
    df = make_ohlcv(500, "volatile")
    r = ta.rsi(df["close"]).dropna()
    assert ((r >= 0) & (r <= 100)).all()


@pytest.mark.parametrize("name", ["sma", "ema", "rsi", "macd", "macd_hist", "bb_upper", "atr", "adx",
                                  "vwap", "support", "resistance", "volume_z"])
def test_no_lookahead(name):
    """Value at bar t must be identical whether or not future bars exist."""
    df = make_ohlcv(400, "volatile", seed=3)
    full = ta.compute(df, name, {"period": 14} if name not in ("macd", "macd_hist") else {})
    trunc = ta.compute(df.iloc[:300], name, {"period": 14} if name not in ("macd", "macd_hist") else {})
    pd.testing.assert_series_equal(full.iloc[:300], trunc, check_names=False)


def test_support_excludes_current_bar():
    df = make_ohlcv(50)
    sr = ta.support_resistance(df, 10)
    assert sr["support"].iloc[20] == df["low"].iloc[10:20].min()


def test_unknown_indicator():
    with pytest.raises(ValueError):
        ta.compute(make_ohlcv(10), "nope", {})
