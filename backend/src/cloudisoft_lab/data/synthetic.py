"""Deterministic synthetic OHLCV for tests and offline paper trading. Always SIMULATED."""

from __future__ import annotations

import zlib
from decimal import Decimal

import numpy as np
import pandas as pd

from cloudisoft_lab.domain.enums import DataOrigin, MarketKind
from cloudisoft_lab.markets.registry import Instrument

REGIMES = {"trend_up": (0.0008, 0.006), "trend_down": (-0.0008, 0.006), "sideways": (0.0, 0.004),
           "volatile": (0.0, 0.03), "realistic": (0.00002, 0.007)}


def make_ohlcv(n: int = 1000, regime: str = "sideways", start: float = 100.0, seed: int = 1,
               freq: str = "1h", start_ts: str = "2025-01-01", shock_at: int | None = None,
               shock: float = -0.15) -> pd.DataFrame:
    drift, vol = REGIMES[regime]
    rng = np.random.default_rng(seed)
    rets = rng.normal(drift, vol, n)
    if shock_at is not None:
        rets[shock_at] = shock
    close = start * np.exp(np.cumsum(rets))
    open_ = np.concatenate([[start], close[:-1]])
    spread = np.abs(rng.normal(0, vol, n)) * close
    high = np.maximum(open_, close) + spread
    low = np.minimum(open_, close) - spread
    volume = rng.lognormal(10, 0.5, n)
    idx = pd.date_range(start_ts, periods=n, freq=freq.replace("m", "min") if freq.endswith("m") else freq, tz="UTC")
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=idx)


START_PRICES = {"BTCUSDT": 60000.0, "ETHUSDT": 3000.0, "SOLUSDT": 150.0, "BNBUSDT": 550.0}


class SyntheticProvider:
    name = "synthetic"
    origin = DataOrigin.SIMULATED

    def __init__(self, regime: str = "sideways", seed: int = 1, fail: bool = False) -> None:
        self.regime, self.seed, self.fail, self._calls = regime, seed, fail, 0

    async def get_candles(self, symbol: str, interval: str, limit: int) -> pd.DataFrame:
        if self.fail:
            raise ConnectionError("simulated provider outage")
        self._calls += 1
        # each call reveals a little more of a fixed path => a "live" feel, deterministic tests
        df = make_ohlcv(limit + self._calls, self.regime, start=START_PRICES.get(symbol, 100.0),
                        seed=self.seed + zlib.crc32(symbol.encode()) % 1000)
        df = df.iloc[-limit:].copy()
        # Anchor the simulated series to the present so charts show today's dates.
        df.index = pd.date_range(end=pd.Timestamp.now(tz="UTC").floor("h"), periods=len(df), freq="h")
        return df

    async def get_instrument(self, symbol: str) -> Instrument:
        return Instrument(symbol, MarketKind.CRYPTO, symbol[:-4], symbol[-4:], Decimal("0.00001"),
                          Decimal("0.00001"), Decimal("5"), Decimal("0.01"))
