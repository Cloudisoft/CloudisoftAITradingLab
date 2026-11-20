import pyotp
from fastapi.testclient import TestClient

from cloudisoft_lab.api.app import create_app
from tests.test_lab_and_api import app_settings

CONF = {k: True for k in ("provider", "asset", "amount", "destination", "network", "fees", "final_details")}


def login(c, user="owner@x", pw="pw-123456", otp=None):
    data = {"username": user, "password": pw}
    if otp:
        data["otp"] = otp
    r = c.post("/api/auth/token", data=data)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def make(tmp_path):
    return TestClient(create_app(app_settings(tmp_path), run_worker=False))


def test_strategy_lab_flow(tmp_path):
    with make(tmp_path) as c:
        h = login(c)
        g = c.post("/api/strategies/generate", headers=h, json={
            "text": "buy when RSI 14 below 30 and close above SMA 50, sell when RSI above 60. stop loss 4%",
            "data": {"bars": 1500}}).json()
        sid = g["strategy"]["id"]
        assert g["meta"]["source"] == "parser" and "out_of_sample" in g["backtest"]
        assert g["strategy"]["status"] == "research"
        d = g["strategy"]["definition"]
        d["risk"]["stop_loss_pct"] = 0.05
        assert c.post(f"/api/strategies/{sid}/versions", headers=h, json={"definition": d, "note": "wider stop"}).json()["version"] == 2
        assert c.post(f"/api/strategies/{sid}/versions", headers=h, json={"definition": d}).status_code == 409
        assert c.post(f"/api/strategies/{sid}/rollback/1", headers=h).json()["version"] == 3
        ids = [s["id"] for s in c.get("/api/strategies").json()["strategies"]]
        assert len(c.post("/api/strategies/compare", headers=h, json={"ids": ids, "data": {"bars": 1000}}).json()["ranking"]) == 2
        assert c.post(f"/api/strategies/{sid}/promote", headers=h).status_code == 409  # v3 not backtested yet
        c.post(f"/api/strategies/{sid}/backtest", headers=h, json={"bars": 1000})
        pid = c.post(f"/api/strategies/{sid}/promote", headers=h).json()["proposal_id"]
        assert c.post(f"/api/proposals/{pid}/decision", headers=h, json={"approve": True}).json()["status"] == "applied"
        statuses = {s["id"]: s["status"] for s in c.get("/api/strategies").json()["strategies"]}
        assert statuses[sid] == "paper" and list(statuses.values()).count("paper") == 1
        imp = c.post(f"/api/strategies/{sid}/improve", headers=h, json={"bars": 2000}).json()
        assert "improved" in imp


def test_wallet_withdrawal_flow(tmp_path):
    with make(tmp_path) as c:
        h = login(c)
        w = c.get("/api/wallet").json()
        assert w["accounts"][0]["origin"] == "simulated" and "never holds funds" in w["custody_notice"]
        # broker disconnected => cannot withdraw from a live provider
        assert c.post("/api/wallet/withdrawals", headers=h, json={"provider": "binance", "amount": "1", "destination": "x"}).status_code == 422
        # invalid: more than withdrawable
        assert c.post("/api/wallet/withdrawals", headers=h, json={"amount": "1000", "destination": "x"}).status_code == 422
        r = c.post("/api/wallet/withdrawals", headers=h, json={"amount": "10", "destination": "bank", "estimated_fee": "0.5"}).json()
        rid = r["request"]["request_id"]
        assert c.get("/api/wallet").json()["accounts"][0]["withdrawable_balance"] == "89.5"
        # missing confirmations => refused
        assert c.post(f"/api/wallet/withdrawals/{rid}/decision", headers=h, json={"approve": True, "confirmations": {"amount": True}}).status_code == 422
        out = c.post(f"/api/wallet/withdrawals/{rid}/decision", headers=h, json={"approve": True, "confirmations": CONF}).json()
        assert out["status"] == "completed" and out["provider_reference"].startswith("PAPER-WD")
        assert c.get("/api/wallet").json()["accounts"][0]["available_balance"] == "89.5"
        r2 = c.post("/api/wallet/withdrawals", headers=h, json={"amount": "1", "destination": "bank"}).json()["request"]
        assert c.post(f"/api/wallet/withdrawals/{r2['request_id']}/decision", headers=h, json={"approve": False}).json()["status"] == "rejected"
        p = c.get("/api/profit").json()
        assert "RECOMMENDATION ONLY" in p["recommendation"]["label"]


def test_governance_reports_settings(tmp_path):
    with make(tmp_path) as c:
        h = login(c)
        assert any(a["agent_id"] == "risk_manager" for a in c.get("/api/agents").json()["agents"])
        assert c.post("/api/agents/risk_manager/status", headers=h, json={"status": "paused"}).status_code == 409
        pid = c.post("/api/agents/proposals", headers=h, json={"agent_id": "crypto_news_2", "name": "News 2",
                     "scope": "more feeds", "budget_usd": "0.5", "justification": "coverage"}).json()["proposal_id"]
        c.post(f"/api/proposals/{pid}/decision", headers=h, json={"approve": True})
        assert any(a["agent_id"] == "crypto_news_2" for a in c.get("/api/agents").json()["agents"])
        exp = {"title": "x", "description": "y", "initial_cost": "10", "monthly_cost": "5",
               "expected_monthly_benefit": "20", "risk": "low"}
        assert c.post("/api/expansion/proposals", headers=h, json=exp).status_code == 409  # not PROFITABLE
        rep = c.get("/api/reports/daily").json()
        assert "# Cloudisoft daily report" in rep["markdown"]
        s = c.get("/api/settings", headers=h).json()
        assert s["live_trading_gates"]["CLAB_LIVE_TRADING_ENABLED"] is False
        cfg = s["risk_config"] | {"max_daily_loss_fraction": "0.03"}
        assert c.put("/api/settings/risk", headers=h, json={"config": cfg, "justification": "tighter"}).json()["max_daily_loss_fraction"] == "0.03"
        bad = cfg | {"max_daily_loss_fraction": "0.9"}
        assert c.put("/api/settings/risk", headers=h, json={"config": bad, "justification": "x"}).status_code == 422
        assert c.put("/api/settings/holidays", headers=h, json={"exchange": "NSE", "dates": ["2026-12-25"]}).status_code == 200


def test_research_endpoints(tmp_path):
    with make(tmp_path) as c:
        h = login(c)
        assert c.post("/api/research/sentiment", headers=h, json={"text": "Bitcoin rally hits record"}).json()["label"] == "positive"
        n = c.post("/api/research/news", headers=h, json={"headlines": ["Ethereum hacked", "Bitcoin surges"]}).json()
        assert set(n["aggregate"]) == {"BTCUSDT", "ETHUSDT"}
        assert c.post("/api/research/news", headers=h, json={}).status_code == 422
        assert c.post("/api/research/fundamentals", headers=h, json={"symbol": "TCS", "roe": 0.4}).json()["score"] == 100
        assert c.post("/api/research/trade-review", headers=h, json={"bars": 1000}).json()["trades"] >= 0
        csv = "timestamp,open,high,low,close,volume\n" + "\n".join(
            f"{1700000000000 + i * 3600000},{100 + i},{101 + i},{99 + i},{100.5 + i},10" for i in range(400))
        ok = c.post("/api/research/datasets", headers=h, json={"symbol": "BTCUSDT", "csv": csv, "source": "export"})
        assert ok.status_code == 200 and ok.json()["datasets"][0]["origin"] == "estimated"
        bad = csv.replace(",101,", ",50,", 1)
        assert c.post("/api/research/datasets", headers=h, json={"symbol": "X1", "csv": "a,b\n1,2", "source": "s"}).status_code == 422
        assert bad
        sid = c.get("/api/strategies").json()["strategies"][0]["id"]
        bt = c.post(f"/api/strategies/{sid}/backtest", headers=h, json={"dataset": "BTCUSDT"}).json()
        assert bt["dataset"].startswith("dataset:BTCUSDT")
        assert c.get("/api/research/llm").json()["available"] is False


def test_users_totp_ratelimit_headers(tmp_path):
    with make(tmp_path) as c:
        h = login(c)
        r = c.get("/health")
        assert r.headers["x-frame-options"] == "DENY" and r.headers["x-content-type-options"] == "nosniff"
        assert c.post("/api/users", headers=h, json={"email": "op@x", "password": "short", "role": "operator"}).status_code == 422
        assert c.post("/api/users", headers=h, json={"email": "op@x", "password": "long-enough-pw", "role": "operator"}).status_code == 200
        hop = login(c, "op@x", "long-enough-pw")
        assert c.post("/api/system/kill-switch", headers=hop, json={"engaged": False}).status_code == 403
        t = c.post("/api/users/me/totp", headers=h).json()
        code = pyotp.TOTP(t["secret"]).now()
        assert c.post("/api/users/me/totp/confirm", headers=h, json={"secret": t["secret"], "code": code}).json()["totp_enabled"]
        assert c.post("/api/auth/token", data={"username": "owner@x", "password": "pw-123456"}).status_code == 401
        assert c.post("/api/auth/token", data={"username": "owner@x", "password": "pw-123456",
                                               "otp": pyotp.TOTP(t["secret"]).now()}).status_code == 200
        codes = [c.post("/api/auth/token", data={"username": "x", "password": "y"}).status_code for _ in range(6)]
        assert 429 in codes
        ev = c.get("/api/security/events", headers=h).json()["events"]
        assert any(e["kind"] == "login_failure" for e in ev) and any(e["kind"] == "totp_enabled" for e in ev)


def test_state_survives_api_restart(tmp_path):
    with make(tmp_path) as c:
        h = login(c)
        c.post("/api/paper/deposit", headers=h, json={"amount": "25"})
        c.post("/api/system/kill-switch", headers=h, json={"engaged": True})
    with make(tmp_path) as c:
        st = c.get("/api/system/status").json()
        assert st["kill_switch"] is True
        assert c.get("/api/overview").json()["available_capital"] == "125.0"
        assert c.get("/api/audit").json()["verified"]
