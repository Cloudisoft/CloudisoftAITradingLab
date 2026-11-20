from decimal import Decimal

import pytest

from cloudisoft_lab.governance.revenue import RevenueComplianceError, RevenueDesk, RevenueOpportunity
from tests.test_api_extended import login, make


def test_compliance_guard():
    d = RevenueDesk()
    assert len(d.items) == 3
    for bad in ["Guaranteed returns of 5% monthly", "risk-free signals", "cold email 10k traders",
                "Sell buy signals for subscribers", "investment advice service"]:
        with pytest.raises(RevenueComplianceError):
            d.add(RevenueOpportunity(bad, bad, "x", Decimal(1), Decimal(2)))


def test_receipt_requires_approval_and_reference():
    d = RevenueDesk()
    o = next(iter(d.items.values()))
    with pytest.raises(RevenueComplianceError):
        d.record_receipt(o.id, Decimal(10), "REF1", "client")
    o.status = "approved"
    with pytest.raises(RevenueComplianceError):
        d.record_receipt(o.id, Decimal(10), " ", "client")
    assert d.record_receipt(o.id, Decimal(10), "REF1", "client")["amount"] == "10"


def test_revenue_api_flow(tmp_path):
    with make(tmp_path) as c:
        h = login(c)
        r = c.get("/api/revenue").json()
        oid = r["opportunities"][0]["id"]
        assert "ESTIMATED" in r["opportunities"][0]["score"]["label"]
        assert c.post("/api/revenue", headers=h, json={"name": "x", "description": "guaranteed profits!", "target_customers": "y",
                      "delivery_cost_monthly": "1", "expected_revenue_monthly": "2"}).status_code == 422
        assert c.post(f"/api/revenue/{oid}/receipts", headers=h, json={"amount": "5", "reference": "UTR123", "payer": "p"}).status_code == 409
        pid = c.post(f"/api/revenue/{oid}/propose", headers=h).json()["proposal_id"]
        c.post(f"/api/proposals/{pid}/decision", headers=h, json={"approve": True})
        assert c.post(f"/api/revenue/{oid}/receipts", headers=h, json={"amount": "5", "reference": "UTR123", "payer": "p"}).status_code == 200
        s = c.get("/api/survival").json()["summary"]
        assert s["verified_external_revenue"] == "5" and s["net_operating_profit"] == "5"
