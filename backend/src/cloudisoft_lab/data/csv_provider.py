"""Owner-supplied historical candles (CSV upload). Labelled ACTUAL only if the owner asserts the
source is a real provider export; otherwise ESTIMATED. Never fabricated."""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from decimal import Decimal

import pandas as pd

from cloudisoft_lab.data.quality import DataQualityReport, check_candles
from cloudisoft_lab.domain.enums import DataOrigin, MarketKind
from cloudisoft_lab.markets.registry import Instrument

MAX_ROWS = 500_000


def parse_csv(text: str) -> pd.DataFrame:
    df = pd.read_csv(io.StringIO(text), nrows=MAX_ROWS + 1)
    if len(df) > MAX_ROWS:
        raise ValueError(f"too many rows (max {MAX_ROWS})")
    df.columns = [c.strip().lower() for c in df.columns]
    tcol = next((c for c in ("timestamp", "time", "date", "datetime", "open_time") if c in df.columns), None)
    if tcol is None:
        raise ValueError("CSV needs a timestamp/date column")
    ts = df[tcol]
    unit = "ms" if pd.api.types.is_numeric_dtype(ts) and ts.max() > 1e11 else ("s" if pd.api.types.is_numeric_dtype(ts) else None)
    df.index = pd.to_datetime(ts, unit=unit, utc=True) if unit else pd.to_datetime(ts, utc=True)
    df = df[["open", "high", "low", "close", "volume"]].astype(float).sort_index()
    return df[~df.index.duplicated(keep="first")]


@dataclass
class DatasetStore:
    datasets: dict[str, tuple[pd.DataFrame, DataOrigin, str]] = field(default_factory=dict)

    def add(self, symbol: str, text: str, source: str, owner_asserts_real: bool) -> DataQualityReport:
        df = parse_csv(text)
        q = check_candles(df)
        if q.ok:
            self.datasets[symbol] = (df, DataOrigin.ACTUAL if owner_asserts_real else DataOrigin.ESTIMATED, source)
        return q

    def summary(self) -> list[dict[str, object]]:
        return [{"symbol": s, "rows": len(df), "start": str(df.index[0]), "end": str(df.index[-1]),
                 "origin": o, "source": src} for s, (df, o, src) in self.datasets.items()]


class CsvReplayProvider:
    """Replays an uploaded dataset bar by bar so paper trading can run on real historical prices."""

    name = "csv_replay"

    def __init__(self, store: DatasetStore, warmup: int = 300) -> None:
        self.store, self.cursor, self.warmup = store, {}, warmup
        self.origin = DataOrigin.SIMULATED  # replay of the past is a simulation

    async def get_candles(self, symbol: str, interval: str, limit: int) -> pd.DataFrame:
        if symbol not in self.store.datasets:
            raise KeyError(f"no dataset uploaded for {symbol}")
        df = self.store.datasets[symbol][0]
        i = self.cursor.get(symbol, min(self.warmup, len(df) - 1)) + 1
        if i > len(df):
            raise EOFError(f"replay of {symbol} finished")
        self.cursor[symbol] = i
        return df.iloc[max(0, i - limit):i]

    async def get_instrument(self, symbol: str) -> Instrument:
        return Instrument(symbol, MarketKind.CRYPTO, symbol[:-4], symbol[-4:], Decimal("0.00001"),
                          Decimal("0.00001"), Decimal("5"), Decimal("0.01"))
