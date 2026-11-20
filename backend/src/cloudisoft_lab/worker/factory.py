from __future__ import annotations

from cloudisoft_lab.core.config import Settings
from cloudisoft_lab.data.synthetic import SyntheticProvider
from cloudisoft_lab.worker.lab import Lab


def build_lab(settings: Settings) -> Lab:
    if settings.market_data_source != "synthetic":
        # Real providers are added only after their official docs are verified (see
        # BROKER_INTEGRATION_MATRIX.md). Refuse rather than silently fall back.
        raise NotImplementedError(f"market data source {settings.market_data_source!r} not yet verified")
    return Lab(settings, SyntheticProvider(regime="volatile", seed=42))
