from decimal import Decimal

from tests.test_api_extended import login, make


def test_markets_candles_and_insights(tmp_path):
    with make(tmp_path) as c:
        m = c.get("/api/markets").json()
        assert "Simulated" in m["label"]
        names = {r["name"] for r in m["markets"]}
        assert names == {"Bitcoin", "Ethereum"}
        btc = next(r for r in m["markets"] if r["symbol"] == "BTCUSDT")
        assert btc["price"] > 1000 and len(btc["spark"]) == 48
        d = c.get("/api/markets/BTCUSDT").json()
        k = d["candles"][-1]
        assert {"time", "open", "high", "low", "close", "volume"} <= set(k)
        assert all(x["low"] <= min(x["open"], x["close"]) and x["high"] >= max(x["open"], x["close"]) for x in d["candles"])
        assert d["insights"] and all(i["tone"] in ("up", "down", "neutral", "caution") for i in d["insights"])
        d4 = c.get("/api/markets/BTCUSDT?tf=4h").json()
        assert len(d4["candles"]) < len(d["candles"])
        assert d4["candles"][1]["time"] - d4["candles"][0]["time"] == 4 * 3600
        assert c.get("/api/markets/DOGEUSDT").status_code == 404


def test_one_tap_trade_goes_through_risk_engine(tmp_path):
    with make(tmp_path) as c:  # app_settings: $100 practice money
        h = login(c)
        c.get("/api/markets")  # loads prices (the paper loop is off in tests)
        pv = c.post("/api/trade/preview", headers=h, json={"symbol": "BTCUSDT", "side": "buy", "amount_usd": "20"}).json()
        assert pv["approved"] and Decimal(pv["notional"]) <= Decimal(20)
        small = c.post("/api/trade/preview", headers=h, json={"symbol": "BTCUSDT", "side": "buy", "amount_usd": "2"}).json()
        assert not small["approved"] and "minimum order size is $5" in small["friendly_reasons"][0]
        too_big = c.post("/api/trade/preview", headers=h, json={"symbol": "BTCUSDT", "side": "buy", "amount_usd": "80"}).json()
        assert not too_big["approved"] and any("too much of your money" in r for r in too_big["friendly_reasons"])
        done = c.post("/api/trade", headers=h, json={"symbol": "BTCUSDT", "side": "buy", "amount_usd": "20"}).json()
        assert done["status"] == "filled" and done["origin"] == "simulated"
        assert c.get("/api/markets/BTCUSDT").json()["holding"]["qty"] == done["qty"]
        sold = c.post("/api/trade", headers=h, json={"symbol": "BTCUSDT", "side": "sell", "sell_all": True}).json()
        assert sold["status"] == "filled"
        acts = c.get("/api/activity").json()["items"]
        assert [a["side"] for a in acts[:2]] == ["sell", "buy"]
        assert c.post("/api/trade", json={"symbol": "BTCUSDT", "side": "buy", "amount_usd": "20"}).status_code == 401
        assert c.post("/api/trade", headers=h, json={"symbol": "BTCUSDT", "side": "sell", "amount_usd": "5"}).status_code == 422


def test_bot_status_and_pause(tmp_path):
    with make(tmp_path) as c:
        h = login(c)
        b = c.get("/api/bot").json()
        assert b["enabled"] and "watching" in b["headline"] and b["practice_money"]
        assert c.post("/api/bot", headers=h, json={"enabled": False}).json() == {"enabled": False}
        assert "paused" in c.get("/api/bot").json()["headline"]
        assert c.post("/api/bot", json={"enabled": True}).status_code == 401


def test_small_balance_headline(tmp_path):
    from fastapi.testclient import TestClient

    from cloudisoft_lab.api.app import create_app
    from tests.test_lab_and_api import app_settings
    s = app_settings(tmp_path)
    s.paper_starting_balance_usd = 5.0
    with TestClient(create_app(s, run_worker=False)) as c:
        assert "below the $5 minimum" in c.get("/api/bot").json()["headline"]
