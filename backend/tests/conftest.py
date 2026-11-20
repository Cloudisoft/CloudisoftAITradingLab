import datetime as dt
from decimal import Decimal

import pytest

from cloudisoft_lab.domain.enums import MarketKind, SurvivalState
from cloudisoft_lab.markets.registry import MARKETS, Instrument
from cloudisoft_lab.risk.engine import RiskContext

NOW = dt.datetime(2026, 11, 18, 12, 0, tzinfo=dt.UTC)  # Wednesday


@pytest.fixture
def btc() -> Instrument:
    return Instrument("BTCUSDT", MarketKind.CRYPTO, "BTC", "USDT", Decimal("0.00001"),
                      Decimal("0.00001"), Decimal("5"), Decimal("0.01"))


@pytest.fixture
def ctx(btc):
    def make(**kw):
        base = dict(now=NOW, market=MARKETS[MarketKind.CRYPTO], instrument=btc,
                    reference_price=Decimal("50000"), available_cash=Decimal("100"),
                    equity=Decimal("100"), position_qty=Decimal("0"), open_positions=0,
                    start_of_day_equity=Decimal("100"), fee_rate=Decimal("0.001"),
                    est_slippage=Decimal("0.0005"), survival_state=SurvivalState.NORMAL)
        base.update(kw)
        return RiskContext(**base)
    return make
