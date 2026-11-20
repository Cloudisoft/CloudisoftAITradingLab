"""Safety policy.

``IMMUTABLE`` encodes rules the owner directive says must never be modified or bypassed by
any agent. They are module constants on a frozen dataclass; there is no API or config path
that changes them, and tests assert their values. ``RiskConfig`` holds the owner-tunable
limits, which are clamped so they can only be *tighter* than the immutable ceilings.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


@dataclass(frozen=True)
class ImmutableSafetyPolicy:
    allow_leverage: bool = False
    allow_borrowing: bool = False
    allow_short_selling: bool = False
    allow_martingale: bool = False
    allow_auto_deposit: bool = False
    allow_auto_withdrawal: bool = False
    allow_auto_capital_increase: bool = False
    allow_agent_self_replication: bool = False
    allow_risk_increase_to_survive: bool = False
    live_trading_default_enabled: bool = False
    # Ceilings for owner-tunable limits
    max_position_fraction_ceiling: Decimal = Decimal("1.0")
    max_daily_loss_fraction_ceiling: Decimal = Decimal("0.20")
    max_cost_fraction_ceiling: Decimal = Decimal("0.05")


IMMUTABLE = ImmutableSafetyPolicy()


class RiskConfig(BaseModel):
    max_position_fraction: Decimal = Field(default=Decimal("0.5"), gt=0)
    max_daily_loss_fraction: Decimal = Field(default=Decimal("0.05"), gt=0)
    # Round-trip fees + slippage may consume at most this share of the order notional.
    max_cost_fraction: Decimal = Field(default=Decimal("0.01"), gt=0)
    max_order_notional: Decimal = Field(default=Decimal("100"), gt=0)
    max_open_positions: int = Field(default=3, ge=1)
    require_owner_confirmation_live: bool = True

    @model_validator(mode="after")
    def _clamp(self) -> RiskConfig:
        p = IMMUTABLE
        if self.max_position_fraction > p.max_position_fraction_ceiling:
            raise ValueError("max_position_fraction exceeds immutable ceiling")
        if self.max_daily_loss_fraction > p.max_daily_loss_fraction_ceiling:
            raise ValueError("max_daily_loss_fraction exceeds immutable ceiling")
        if self.max_cost_fraction > p.max_cost_fraction_ceiling:
            raise ValueError("max_cost_fraction exceeds immutable ceiling")
        return self
