import pandas as pd
import pytest

from cloudisoft_lab.backtest.engine import CostModel, run_backtest
from cloudisoft_lab.backtest.metrics import max_drawdown
from cloudisoft_lab.backtest.validation import grid_optimise, monte_carlo, out_of_sample_split, walk_forward
from cloudisoft_lab.data.synthetic import make_ohlcv
from cloudisoft_lab.domain.enums import MarketKind
from cloudisoft_lab.markets.registry import MARKETS
from cloudisoft_lab.strategy.schema import StrategyDefinition
from cloudisoft_lab.strategy.templates import ema_crossover


def always_in(**risk):
    return StrategyDefinition.model_validate({"name": "always", "entry": {"conditions": [
        {"left": {"value": 1}, "op": ">", "right": {"value": 0}}]}, "risk": {"stop_loss_pct": None,
        "take_profit_pct": None, "position_fraction": 1.0, **risk}})


def test_fill_next_bar_open_and_costs():
    df = make_ohlcv(50, "trend_up")
    costs = CostModel(fee_rate=0.001, half_spread=0, slippage=0, min_notional=0)
    r = run_backtest(df, always_in(), 1000, costs)
    t = r.trades[0]
    assert t.entry_time == df.index[1]
    assert t.entry_price == pytest.approx(df["open"].iloc[1])
    assert r.metrics.total_fees > 0


def test_fees_reduce_returns():
    df = make_ohlcv(800, "volatile", seed=5)
    s = ema_crossover()
    cheap = run_backtest(df, s, 1000, CostModel(fee_rate=0, half_spread=0, slippage=0, min_notional=0))
    dear = run_backtest(df, s, 1000, CostModel(fee_rate=0.005, min_notional=0))
    assert dear.metrics.final_equity < cheap.metrics.final_equity


def test_profitable_vs_losing_market():
    up = run_backtest(make_ohlcv(500, "trend_up"), always_in(), 1000, CostModel(min_notional=0))
    down = run_backtest(make_ohlcv(500, "trend_down"), always_in(), 1000, CostModel(min_notional=0))
    assert up.metrics.net_return > 0 > down.metrics.net_return


def test_stop_loss_limits_shock():
    df = make_ohlcv(100, "sideways", shock_at=50, shock=-0.30)
    held = run_backtest(df, always_in(), 1000, CostModel(min_notional=0))
    stopped = run_backtest(df, always_in(stop_loss_pct=0.02), 1000, CostModel(min_notional=0))
    assert stopped.metrics.max_drawdown > held.metrics.max_drawdown
    assert any(t.exit_reason == "stop" for t in stopped.trades)


def test_micro_capital_uneconomical_trades_skipped():
    df = make_ohlcv(200, "trend_up")
    r = run_backtest(df, always_in(), 5.0, CostModel(min_notional=10))
    assert r.metrics.num_trades == 0 and r.skipped_uneconomical > 0
    assert r.metrics.final_equity == 5.0


def test_partial_fill_volume_cap():
    df = make_ohlcv(50)
    df["volume"] = 0.001
    r = run_backtest(df, always_in(), 1_000_000, CostModel(min_notional=0))
    assert r.partial_fills >= 1


def test_market_hours_respected():
    df = make_ohlcv(24 * 7, freq="1h", start_ts="2026-11-21")  # Sat start
    r = run_backtest(df, always_in(), 100000, CostModel(min_notional=0), market=MARKETS[MarketKind.IN_EQUITY])
    assert r.trades, "should eventually enter on Monday"
    first = r.trades[0].entry_time.tz_convert("Asia/Kolkata")
    assert first.weekday() < 5 and 9 <= first.hour <= 15


def test_rejects_bad_data():
    df = make_ohlcv(20)
    with pytest.raises(ValueError):
        run_backtest(df.iloc[::-1], always_in())
    with pytest.raises(ValueError):
        run_backtest(df.drop(columns="volume"), always_in())


def test_metrics_and_drawdown():
    assert max_drawdown(pd.Series([100, 120, 60, 130])) == pytest.approx(-0.5)
    r = run_backtest(make_ohlcv(800, "volatile"), ema_crossover(), 1000, CostModel(min_notional=0))
    d = r.metrics.as_dict()
    for k in ("sharpe", "sortino", "profit_factor", "expectancy", "recovery_factor", "win_rate"):
        assert k in d
    assert "SIMULATED" in r.label


def test_validation_tools():
    df = make_ohlcv(1200, "volatile", seed=11)
    tr, te = out_of_sample_split(df)
    assert tr.index[-1] < te.index[0]
    grid = {"fast": [8, 12], "slow": [26, 40]}
    params, best = grid_optimise(tr, ema_crossover, grid, CostModel(min_notional=0), 1000, min_trades=1)
    assert params and best is not None
    folds = walk_forward(df, ema_crossover, grid, CostModel(min_notional=0), 1000, folds=3, min_trades=1)
    assert len(folds) == 3 and all(f.test_start > f.train_start for f in folds)
    mc = monte_carlo([0.02, -0.01, 0.015, -0.02, 0.01] * 5)
    assert 0 <= mc.prob_loss <= 1 and mc.p5_return <= mc.median_return <= mc.p95_return
    assert monte_carlo([]).simulations == 2000
