import datetime as dt
from decimal import Decimal

import pandas as pd
import pytest

from cloudisoft_lab.agents import fundamental, portfolio
from cloudisoft_lab.agents.improvement import research_improvement
from cloudisoft_lab.agents.news import NewsAnalyst, NewsItem, aggregate, parse_feed
from cloudisoft_lab.agents.sentiment import SentimentScore, analyse, lexicon_score
from cloudisoft_lab.agents.strategy_researcher import FlatCondition, FlatOperand, FlatStrategy, generate, parse_natural_language
from cloudisoft_lab.agents.trade_reviewer import review
from cloudisoft_lab.ai.llm import BudgetExceeded, LLMGateway
from cloudisoft_lab.backtest.engine import CostModel, Trade, run_backtest
from cloudisoft_lab.data.synthetic import make_ohlcv
from cloudisoft_lab.domain.enums import SurvivalState
from cloudisoft_lab.strategy.templates import ema_crossover
from cloudisoft_lab.survival.ledger import Entry, SurvivalLedger


class FakeBackend:
    def __init__(self, result=None, refuse=False, tin=1000, tout=500, served=None):
        self.result, self.refuse, self.tin, self.tout, self.served, self.calls = result, refuse, tin, tout, served, []

    async def parse(self, *, model, system, prompt, schema, max_tokens, effort):
        self.calls.append(model)
        return (None if self.refuse else self.result), self.served or model, self.tin, self.tout


async def test_gateway_records_cost_and_routes_by_state():
    led = SurvivalLedger()
    fb = FakeBackend(SentimentScore(score=0.5, label="positive", rationale="x"))
    g = LLMGateway(led, fb)
    out = await g.structured(agent="a", state=SurvivalState.NORMAL, system="s", prompt="p", schema=SentimentScore)
    assert out.score == 0.5 and fb.calls == ["claude-sonnet-5-5"]
    # 1000 in * $2/M + 500 out * $10/M
    assert led.summary()["ai_costs"] == Decimal("0.007")
    assert led.cost_by("agent_id")["a"] == Decimal("0.007")
    await g.structured(agent="a", state=SurvivalState.HIGH, system="s", prompt="p", schema=SentimentScore)
    assert fb.calls[-1] == "claude-opus-5-5"
    assert await g.structured(agent="a", state=SurvivalState.LOW_COMPUTE, system="s", prompt="p",
                              schema=SentimentScore) is None
    await g.structured(agent="a", state=SurvivalState.LOW_COMPUTE, system="s", prompt="p", schema=SentimentScore,
                       essential=True)
    assert fb.calls[-1] == "claude-haiku-5-5"
    assert await g.structured(agent="a", state=SurvivalState.DEAD, system="s", prompt="p", schema=SentimentScore,
                              essential=True) is None
    assert len(fb.calls) == 3


async def test_gateway_budget_and_refusal():
    led = SurvivalLedger()
    g = LLMGateway(led, FakeBackend(refuse=True), default_budget_usd=Decimal("0.0001"))
    with pytest.raises(BudgetExceeded):
        await g.structured(agent="a", state=SurvivalState.NORMAL, system="s", prompt="p", schema=SentimentScore)
    g.budget("a").limit_usd = Decimal(1)
    assert await g.structured(agent="a", state=SurvivalState.NORMAL, system="s", prompt="p",
                              schema=SentimentScore) is None
    assert g.calls[-1]["refused"] and led.summary()["ai_costs"] > 0  # refusals are still billed


async def test_gateway_unavailable_without_backend():
    g = LLMGateway(SurvivalLedger())
    assert not g.available
    assert (await analyse("Bitcoin surges to record", g)).label == "positive"


def test_lexicon_sentiment():
    assert lexicon_score("Exchange hacked, prices plunge").label == "negative"
    assert lexicon_score("Company reports record profit, shares surge").label == "positive"
    assert lexicon_score("not a loss").score > 0
    assert lexicon_score("Markets open").label == "neutral"


RSS = """<rss><channel><item><title>Bitcoin surges after ETF approval</title><link>https://x/1</link>
<pubDate>Fri, 20 Nov 2026 10:00:00 GMT</pubDate></item><item><title>Gold steady</title><link>https://x/2</link>
</item></channel></rss>"""
ATOM = """<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Ethereum exploit drains funds</title>
<link href="https://y/1"/><updated>2026-11-20T00:00:00Z</updated></entry></feed>"""


async def test_news_pipeline():
    items = parse_feed(RSS, "x") + parse_feed(ATOM, "y")
    assert len(items) == 3 and items[2].link == "https://y/1"
    out = await NewsAnalyst([]).run(["BTCUSDT", "ETHUSDT"], SurvivalState.NORMAL, items)
    agg = aggregate(out)
    assert agg["BTCUSDT"]["mean"] > 0 > agg["ETHUSDT"]["mean"]
    with pytest.raises(ValueError):
        parse_feed('<!DOCTYPE x [<!ENTITY a "b">]><rss/>', "evil")


async def test_news_fetch_outage_is_reported():
    a = NewsAnalyst(["https://127.0.0.1:9/feed"])
    out = await a.run(["BTCUSDT"], SurvivalState.NORMAL)
    assert out == [] and a.errors


def test_fundamentals():
    r = fundamental.score(fundamental.Fundamentals(symbol="INFY", pe=20, pb=4, roe=0.3, debt_to_equity=0.1,
                                                   revenue_growth=0.1, eps_growth=0.12))
    assert r.score == 100 and r.data_coverage == 1
    weak = fundamental.score(fundamental.Fundamentals(symbol="X", pe=80, roe=0.02))
    assert weak.score == 0 and weak.factors["leverage"] == "no data"


def test_nl_parser():
    s = parse_natural_language("Buy when RSI 14 below 30 and close above SMA 200, sell when RSI above 70. "
                               "Stop loss 2%, take profit 5%, position size 40%")
    assert len(s.entry.conditions) == 2 and s.entry.logic == "AND"
    assert s.exit and s.exit.conditions[0].op == ">"
    assert s.risk.stop_loss_pct == 0.02 and s.risk.take_profit_pct == 0.05 and s.risk.position_fraction == 0.4
    x = parse_natural_language("enter when EMA 12 crosses above EMA 26")
    assert x.entry.conditions[0].op == "crosses_above"
    with pytest.raises(ValueError):
        parse_natural_language("make me rich quickly")


async def test_generate_with_llm_and_fallback():
    flat = FlatStrategy(name="LLM strat", description="d", entry_logic="AND", entry=[
        FlatCondition(left=FlatOperand(indicator="rsi", period=14), op="<", right=FlatOperand(value=25))],
        exit_logic="OR", exit=[], stop_loss_pct=0.03, take_profit_pct=None, trailing_stop_pct=0.05,
        position_fraction=0.3, unsupported_requests=["options hedging"])
    g = LLMGateway(SurvivalLedger(), FakeBackend(flat))
    d, meta = await generate("buy oversold", g, SurvivalState.NORMAL)
    assert meta["source"] == "llm" and meta["unsupported"] == ["options hedging"] and d.exit is None
    bad = flat.model_copy(update={"entry": [FlatCondition(left=FlatOperand(indicator="magic"), op=">",
                                                          right=FlatOperand(value=1))]})
    g2 = LLMGateway(SurvivalLedger(), FakeBackend(bad))
    d2, meta2 = await generate("buy when rsi below 30", g2, SurvivalState.NORMAL)
    assert meta2["source"] == "parser" and "llm_error" in meta2


def test_portfolio_analysis():
    r = portfolio.analyse({"A": Decimal(10), "B": Decimal(1)}, {"A": Decimal(10), "B": Decimal(10)}, Decimal(10),
                          {"A": pd.Series([0.01, 0.02, -0.01, 0.03]), "B": pd.Series([0.01, 0.021, -0.012, 0.03])})
    assert r["weights"]["A"] == pytest.approx(100 / 120)
    assert any("A is" in w for w in r["warnings"]) and any("correlated" in w for w in r["warnings"])


def test_trade_review():
    t0 = pd.Timestamp("2026-01-01", tz="UTC")
    trades = [Trade(t0, 100, 1, 0.5, t0 + pd.Timedelta(hours=2), 99, 0.5, 0, "stop") for _ in range(6)]
    r = review(trades)
    assert r["max_losing_streak"] == 6 and r["suggestions"]
    assert review([])["trades"] == 0


def test_improvement_research_only_proposes_oos_gains():
    df = make_ohlcv(3000, "volatile", seed=4)
    r = research_improvement(df, ema_crossover(), CostModel(min_notional=0), min_trades=1, min_gain=0.0)
    assert r.tested_variants > 0
    if r.improved:
        assert r.candidate is not None and r.best_oos_sharpe >= r.baseline_oos_sharpe
    strict = research_improvement(df, ema_crossover(), CostModel(min_notional=0), min_gain=1e9)
    assert not strict.improved and strict.candidate is None


def test_unused_imports_ok():
    assert Entry and dt and run_backtest and NewsItem
