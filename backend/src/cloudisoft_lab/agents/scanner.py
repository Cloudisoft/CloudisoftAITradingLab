"""Market Scanner + Technical Analyst agents. They only emit AgentMessages; they cannot trade."""

from __future__ import annotations

import pandas as pd

from cloudisoft_lab import indicators as ta
from cloudisoft_lab.domain.schemas import AgentMessage


def technical_snapshot(df: pd.DataFrame) -> dict[str, float | None]:
    c = df["close"]
    last = lambda s: None if pd.isna(s.iloc[-1]) else float(s.iloc[-1])  # noqa: E731
    m = ta.macd(c)
    b = ta.bollinger(c)
    sr = ta.support_resistance(df)
    return {
        "close": float(c.iloc[-1]), "rsi14": last(ta.rsi(c)), "ema20": last(ta.ema(c, 20)),
        "ema50": last(ta.ema(c, 50)), "sma200": last(ta.sma(c, 200)), "macd_hist": last(m["hist"]),
        "bb_upper": last(b["upper"]), "bb_lower": last(b["lower"]), "atr14": last(ta.atr(df)),
        "adx14": last(ta.adx(df)), "vwap20": last(ta.vwap(df, 20)), "support20": last(sr["support"]),
        "resistance20": last(sr["resistance"]), "volume_z": last(ta.volume_zscore(df)),
        "return_24": float(c.iloc[-1] / c.iloc[-25] - 1) if len(c) > 25 else None,
    }


def classify(snap: dict[str, float | None]) -> list[str]:
    flags: list[str] = []
    if (snap.get("volume_z") or 0) > 3:
        flags.append("unusual_volume")
    if snap.get("atr14") and snap["close"] and snap["atr14"] / snap["close"] > 0.03:  # type: ignore[operator]
        flags.append("high_volatility")
    if (snap.get("adx14") or 0) > 25:
        flags.append("strong_trend")
    rsi = snap.get("rsi14")
    if rsi is not None and rsi < 30:
        flags.append("oversold")
    if rsi is not None and rsi > 70:
        flags.append("overbought")
    if snap.get("resistance20") and snap["close"] > snap["resistance20"]:  # type: ignore[operator]
        flags.append("breakout")
    return flags


def scan(frames: dict[str, pd.DataFrame]) -> list[AgentMessage]:
    out = []
    for sym, df in frames.items():
        snap = technical_snapshot(df)
        out.append(AgentMessage(sender="market_scanner", recipient="strategy_researcher", kind="analysis",
                                payload={"symbol": sym, "snapshot": snap, "flags": classify(snap),
                                         "label": "analysis only; not a trade instruction"}))
    return out
