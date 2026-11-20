import datetime as dt
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from cloudisoft_lab.api.app import create_app
from cloudisoft_lab.core.config import Settings
from cloudisoft_lab.core.security import CredentialVault, CredentialVaultError, create_access_token, hash_password
from cloudisoft_lab.data.synthetic import SyntheticProvider
from cloudisoft_lab.domain.enums import DataOrigin, SurvivalState
from cloudisoft_lab.survival.ledger import Entry
from cloudisoft_lab.worker.lab import Lab

S = Settings(paper_starting_balance_usd=100.0)
T0 = dt.datetime(2026, 11, 20, tzinfo=dt.UTC)


def tok(role="owner"):
    return {"Authorization": "Bearer " + create_access_token("owner@x", role, S.jwt_secret.get_secret_value(), 5)}


async def test_lab_paper_loop_trades_and_labels():
    lab = Lab(S, SyntheticProvider("volatile", seed=3))
    lab.ledger.add(Entry.OWNER_FUNDING_OPERATIONS, Decimal(50), at=T0)
    for i in range(150):
        await lab.tick(T0 + dt.timedelta(hours=i))
    assert lab.paper.orders, "strategy should have produced paper orders"
    assert all(o.origin == DataOrigin.SIMULATED for o in lab.paper.orders.values())
    assert lab.audit.verify()
    # simulated P&L never changes real survival economics
    assert lab.ledger.summary()["net_trading_profit"] == 0


async def test_lab_survives_provider_outage():
    lab = Lab(S, SyntheticProvider(fail=True))
    out = await lab.tick(T0)
    assert out["actions"] == [] and "outage" in lab.last_error
    assert any(e.event == "market_data.error" for e in lab.audit.events)


async def test_kill_switch_blocks_new_trades():
    lab = Lab(S, SyntheticProvider("volatile", seed=3))
    lab.engage_kill_switch("owner")
    for i in range(150):
        out = await lab.tick(T0 + dt.timedelta(hours=i))
        for a in out["actions"]:
            assert a["status"] == "rejected"
    assert not lab.paper.orders


async def test_compute_exhaustion_stops_trading():
    lab = Lab(S, SyntheticProvider("volatile", seed=3))
    lab.ledger.add(Entry.OWNER_FUNDING_OPERATIONS, Decimal(1), at=T0)
    lab.ledger.add(Entry.AI_INFERENCE_COST, Decimal(2), at=T0)
    for i in range(150):
        await lab.tick(T0 + dt.timedelta(hours=i))
    assert lab.survival.state == SurvivalState.DEAD
    assert not lab.paper.orders


def test_credential_vault():
    with pytest.raises(CredentialVaultError):
        CredentialVault(None)
    v = CredentialVault(CredentialVault.generate_key())
    c = v.encrypt("super-secret")
    assert "super-secret" not in c and v.decrypt(c) == "super-secret"
    assert CredentialVault.mask("abcdefghijkl") == "abcd…ijkl"


def app_settings(tmp_path, **kw):
    return Settings(paper_starting_balance_usd=100.0, database_url=f"sqlite+aiosqlite:///{tmp_path}/t.db",
                    auto_migrate=False, owner_email="owner@x", owner_password_hash=hash_password("pw-123456"),
                    credential_encryption_key=CredentialVault.generate_key(), **kw)


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(app_settings(tmp_path), run_worker=False)) as c:
        yield c


def test_api_health_status_overview(client):
    assert client.get("/health").json() == {"status": "ok"}
    st = client.get("/api/system/status").json()
    assert st["mode"] == "paper" and st["live_trading_allowed"] is False
    ov = client.get("/api/overview").json()
    assert ov["label"] == "simulated"


def test_api_auth_and_roles(client):
    assert client.post("/api/auth/token", data={"username": "owner@x", "password": "bad"}).status_code == 401
    t = client.post("/api/auth/token", data={"username": "owner@x", "password": "pw-123456"}).json()["access_token"]
    h = {"Authorization": f"Bearer {t}"}
    assert client.post("/api/paper/deposit", json={"amount": "10"}).status_code == 401
    assert client.post("/api/paper/deposit", json={"amount": "10"}, headers=tok("viewer")).status_code == 403
    assert client.post("/api/paper/deposit", json={"amount": "10"}, headers=h).status_code == 200
    assert client.post("/api/paper/deposit", json={"amount": "-1"}, headers=h).status_code == 422


def test_api_kill_switch_release_owner_only(client):
    assert client.post("/api/system/kill-switch", json={"engaged": True}, headers=tok("operator")).json()["kill_switch"]
    assert client.post("/api/system/kill-switch", json={"engaged": False}, headers=tok("operator")).status_code == 403
    assert not client.post("/api/system/kill-switch", json={"engaged": False}, headers=tok()).json()["kill_switch"]


def test_api_ledger_rules(client):
    h = tok()
    assert client.post("/api/survival/ledger", json={"kind": "realised_trading_pnl", "amount": "5"}, headers=h).status_code == 422
    assert client.post("/api/survival/ledger", json={"kind": "external_revenue", "amount": "5"}, headers=h).status_code == 422
    assert client.post("/api/survival/ledger", json={"kind": "hosting_cost", "amount": "5"}, headers=h).status_code == 200
    s = client.get("/api/survival").json()
    assert s["summary"]["hosting_costs"] == "5"


def test_api_backtest(client):
    tpl = client.get("/api/strategies/templates").json()["ema_crossover"]
    r = client.post("/api/backtest", json={"strategy": tpl, "capital": 1000, "bars": 1500}).json()
    assert "SIMULATED" in r["label"] and "sharpe" in r["metrics"] and "prob_loss" in r["monte_carlo"]
    assert client.post("/api/backtest", json={"strategy": tpl, "regime": "moon"}).status_code == 422


def test_api_audit(client):
    a = client.get("/api/audit").json()
    assert a["verified"] and a["events"][0]["event"] == "lab.start"


def test_production_bootstrap(tmp_path, monkeypatch):
    from cloudisoft_lab.core.config import Environment
    s = Settings(database_url=f"sqlite+aiosqlite:///{tmp_path}/p.db", auto_migrate=False, environment=Environment.PRODUCTION,
                 owner_email="o@x", owner_password="a-long-owner-password")
    assert s.jwt_secret_is_default
    with TestClient(create_app(s, run_worker=False)) as c:
        r = c.post("/api/auth/token", data={"username": "o@x", "password": "a-long-owner-password"})
        assert r.status_code == 200
        assert not s.jwt_secret_is_default  # generated + persisted secret replaced the dev default
        first = s.jwt_secret.get_secret_value()
    s2 = Settings(database_url=f"sqlite+aiosqlite:///{tmp_path}/p.db", auto_migrate=False, environment=Environment.PRODUCTION)
    with TestClient(create_app(s2, run_worker=False)):
        assert s2.jwt_secret.get_secret_value() == first  # stable across restarts


def test_settings_normalise_db_url_and_vault_derivation():
    assert Settings(database_url="postgresql://u:p@h:5432/d").database_url == "postgresql+asyncpg://u:p@h:5432/d"
    assert Settings(database_url="postgres://u@h/d").database_url.startswith("postgresql+asyncpg://")
    v = CredentialVault("x" * 40)
    assert v.decrypt(v.encrypt("s")) == "s"
    with pytest.raises(CredentialVaultError):
        CredentialVault("short")


def test_first_run_owner_setup(tmp_path):
    from cloudisoft_lab.core.config import Environment
    s = Settings(database_url=f"sqlite+aiosqlite:///{tmp_path}/s.db", auto_migrate=False, environment=Environment.PRODUCTION)
    app = create_app(s, run_worker=False)
    with TestClient(app) as c:
        assert c.get("/api/setup/status").json() == {"owner_exists": False}
        code = app.state.setup_code
        assert code and code not in c.get("/api/system/status").text  # never exposed via the API
        body = {"setup_code": "WRONG123", "email": "me@x", "password": "a-very-long-pass"}
        assert c.post("/api/setup/owner", json=body).status_code == 403
        assert c.post("/api/setup/owner", json=body | {"setup_code": code, "password": "short"}).status_code == 422
        assert c.post("/api/setup/owner", json=body | {"setup_code": code.lower()}).status_code == 200
        assert c.post("/api/setup/owner", json=body | {"setup_code": code}).status_code == 403  # single use
        assert c.get("/api/setup/status").json() == {"owner_exists": True}
        tok = c.post("/api/auth/token", data={"username": "me@x", "password": "a-very-long-pass"}).json()["access_token"]
        # auto-generated encryption key makes 2FA available without manual configuration
        assert c.post("/api/users/me/totp", headers={"Authorization": f"Bearer {tok}"}).status_code == 200
    with TestClient(create_app(Settings(database_url=f"sqlite+aiosqlite:///{tmp_path}/s.db", auto_migrate=False,
                                        environment=Environment.PRODUCTION), run_worker=False)) as c2:
        assert c2.app.state.setup_code is None  # owner exists, no new code printed
