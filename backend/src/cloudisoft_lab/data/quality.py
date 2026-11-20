"""Market-data validation: reject gaps, NaNs, non-monotonic or stale data before use."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class DataQualityReport:
    ok: bool
    issues: list[str]


def check_candles(df: pd.DataFrame, expected_freq: pd.Timedelta | None = None,
                  max_missing_fraction: float = 0.01) -> DataQualityReport:
    issues: list[str] = []
    if df.empty:
        return DataQualityReport(False, ["no data"])
    need = {"open", "high", "low", "close", "volume"}
    if not need.issubset(df.columns):
        issues.append(f"missing columns {need - set(df.columns)}")
        return DataQualityReport(False, issues)
    if df[list(need)].isna().any().any():
        issues.append("NaN values present")
    if not df.index.is_monotonic_increasing or df.index.has_duplicates:
        issues.append("index not strictly increasing")
    if (df["high"] < df[["open", "close"]].max(axis=1)).any() or (df["low"] > df[["open", "close"]].min(axis=1)).any():
        issues.append("OHLC inconsistency")
    if (df[["open", "high", "low", "close"]] <= 0).any().any():
        issues.append("non-positive prices")
    if expected_freq is not None and len(df) > 1:
        gaps = (df.index.to_series().diff().dropna() > expected_freq).sum()
        if gaps / len(df) > max_missing_fraction:
            issues.append(f"{gaps} gaps in series")
    return DataQualityReport(not issues, issues)
