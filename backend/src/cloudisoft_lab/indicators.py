"""Causal technical indicators.

Every function uses only data at or before each bar (rolling / ewm windows), so
values at bar t never depend on bar t+1. Tests assert this property.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def sma(close: pd.Series, n: int) -> pd.Series:
    return close.rolling(n, min_periods=n).mean()


def ema(close: pd.Series, n: int) -> pd.Series:
    return close.ewm(span=n, adjust=False, min_periods=n).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = gain / loss.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    return out.where(loss != 0, 100.0).where(gain.notna())


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    line = ema(close, fast) - ema(close, slow)
    sig = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return pd.DataFrame({"macd": line, "signal": sig, "hist": line - sig})


def bollinger(close: pd.Series, n: int = 20, k: float = 2.0) -> pd.DataFrame:
    mid = sma(close, n)
    sd = close.rolling(n, min_periods=n).std(ddof=0)
    return pd.DataFrame({"mid": mid, "upper": mid + k * sd, "lower": mid - k * sd})


def true_range(df: pd.DataFrame) -> pd.Series:
    prev = df["close"].shift(1)
    return pd.concat(
        [df["high"] - df["low"], (df["high"] - prev).abs(), (df["low"] - prev).abs()], axis=1
    ).max(axis=1)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    return true_range(df).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def adx(df: pd.DataFrame, n: int = 14) -> pd.Series:
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)
    tr = atr(df, n)
    plus_di = 100 * plus_dm.ewm(alpha=1 / n, adjust=False, min_periods=n).mean() / tr
    minus_di = 100 * minus_dm.ewm(alpha=1 / n, adjust=False, min_periods=n).mean() / tr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def vwap(df: pd.DataFrame, n: int | None = None) -> pd.Series:
    """Rolling VWAP over ``n`` bars (or cumulative if n is None)."""
    typical = (df["high"] + df["low"] + df["close"]) / 3
    pv = typical * df["volume"]
    if n is None:
        return pv.cumsum() / df["volume"].cumsum()
    return pv.rolling(n, min_periods=n).sum() / df["volume"].rolling(n, min_periods=n).sum()


def support_resistance(df: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    """Prior-window extremes (shifted by 1 so the current bar is excluded)."""
    return pd.DataFrame(
        {
            "support": df["low"].rolling(n, min_periods=n).min().shift(1),
            "resistance": df["high"].rolling(n, min_periods=n).max().shift(1),
        }
    )


def volume_zscore(df: pd.DataFrame, n: int = 20) -> pd.Series:
    v = df["volume"]
    mean = v.rolling(n, min_periods=n).mean().shift(1)
    sd = v.rolling(n, min_periods=n).std(ddof=0).shift(1)
    return (v - mean) / sd.replace(0, np.nan)


def compute(df: pd.DataFrame, name: str, params: dict[str, float]) -> pd.Series:
    """Dispatch used by the strategy evaluator. Returns one series."""
    p = {k: int(v) if float(v).is_integer() else v for k, v in params.items()}
    c = df["close"]
    match name:
        case "close" | "open" | "high" | "low" | "volume":
            return df[name]
        case "sma":
            return sma(c, int(p.get("period", 20)))
        case "ema":
            return ema(c, int(p.get("period", 20)))
        case "rsi":
            return rsi(c, int(p.get("period", 14)))
        case "macd" | "macd_signal" | "macd_hist":
            m = macd(c, int(p.get("fast", 12)), int(p.get("slow", 26)), int(p.get("signal", 9)))
            return m[{"macd": "macd", "macd_signal": "signal", "macd_hist": "hist"}[name]]
        case "bb_upper" | "bb_lower" | "bb_mid":
            b = bollinger(c, int(p.get("period", 20)), float(p.get("k", 2.0)))
            return b[name.removeprefix("bb_")]
        case "atr":
            return atr(df, int(p.get("period", 14)))
        case "adx":
            return adx(df, int(p.get("period", 14)))
        case "vwap":
            return vwap(df, int(p["period"]) if "period" in p else None)
        case "support" | "resistance":
            return support_resistance(df, int(p.get("period", 20)))[name]
        case "volume_z":
            return volume_zscore(df, int(p.get("period", 20)))
    raise ValueError(f"unknown indicator: {name}")


INDICATORS = (
    "close open high low volume sma ema rsi macd macd_signal macd_hist bb_upper bb_lower "
    "bb_mid atr adx vwap support resistance volume_z"
).split()
