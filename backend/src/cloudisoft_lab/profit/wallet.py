"""Wallet & Funds service. Cloudisoft never custodies funds: for real providers it only reads history
and links to the provider's official funding page. Simulated funds live in the paper broker."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from cloudisoft_lab.core.money import ZERO
from cloudisoft_lab.domain.enums import DataOrigin
from cloudisoft_lab.domain.schemas import FundingRecord
from cloudisoft_lab.execution.paper_broker import PaperBroker
from cloudisoft_lab.profit.manager import ApprovalStatus, WithdrawalRequest, WithdrawalWorkflow


class WalletError(RuntimeError):
    pass


@dataclass
class WalletService:
    paper: PaperBroker
    workflow: WithdrawalWorkflow
    connected_live_providers: frozenset[str] = frozenset()  # none until adapters exist

    def accounts(self) -> list[dict[str, object]]:
        p = self.paper
        open_value = p.equity() - p.cash
        deposits = sum((f.amount for f in p.funding if f.kind == "deposit" and f.status == "completed"), ZERO)
        withdrawals = sum((f.amount for f in p.funding if f.kind == "withdrawal" and f.status == "completed"), ZERO)
        return [{
            "provider": "paper", "account_id": "paper-1", "currency": p.quote_currency, "origin": DataOrigin.SIMULATED,
            "available_balance": str(p.cash), "total_balance": str(p.equity()), "invested_capital": str(open_value),
            "withdrawable_balance": str(self.withdrawable()), "open_positions": sum(1 for x in p.positions.values() if x.qty > 0),
            "realised_pnl": str(p.realised_pnl), "unrealised_pnl": str(p.unrealised_pnl()),
            "deposits": str(deposits + p.starting_cash), "withdrawals": str(withdrawals),
        }]

    def withdrawable(self) -> Decimal:
        pending = sum((r.amount + r.estimated_fee for r in self.workflow.requests.values()
                       if r.status in (ApprovalStatus.PENDING, ApprovalStatus.APPROVED, ApprovalStatus.SUBMITTED)), ZERO)
        return max(ZERO, self.paper.cash - pending)

    def request_withdrawal(self, provider: str, amount: Decimal, destination: str, network: str | None,
                           fee: Decimal) -> WithdrawalRequest:
        if provider != "paper" and provider not in self.connected_live_providers:
            raise WalletError(f"provider {provider!r} is not connected")
        return self.workflow.create(WithdrawalRequest(provider, self.paper.quote_currency, amount, destination,
                                                      network, fee), available=self.withdrawable())

    def execute_approved(self, request_id: str) -> FundingRecord | None:
        """Paper: settle simulated. Live: would call the provider's WithdrawalInterface (not connected)."""
        req = self.workflow.requests[request_id]
        if req.status != ApprovalStatus.APPROVED:
            raise WalletError("withdrawal is not owner-approved")
        if req.provider != "paper":
            raise WalletError("live withdrawals are not available: no provider connected")
        self.workflow.mark_submitted(request_id, None)
        rec = self.paper.simulate_withdrawal(req.amount + req.estimated_fee)
        self.workflow.mark_result(request_id, rec.status == "completed", provider_reference=f"PAPER-WD-{request_id[:8]}")
        return rec
