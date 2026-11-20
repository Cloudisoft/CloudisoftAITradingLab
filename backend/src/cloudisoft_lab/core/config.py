"""Application settings.

Safety-critical defaults live here. LIVE trading is OFF unless *every* gate is
explicitly opened by the owner; see ``risk.policy.ImmutableSafetyPolicy`` for
rules that cannot be changed through configuration at all.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CLAB_", env_file=".env", extra="ignore")

    environment: Environment = Environment.DEVELOPMENT
    app_name: str = "Cloudisoft AI Trading Lab"
    log_level: str = "INFO"
    log_json: bool = False

    database_url: str = "sqlite+aiosqlite:///./cloudisoft_lab.db"
    redis_url: str | None = None

    # Secrets: never logged, never sent to the frontend.
    jwt_secret: SecretStr = SecretStr("dev-only-change-me-dev-only-change-me")
    jwt_ttl_minutes: int = 60
    # Fernet key (urlsafe base64, 32 bytes) used to encrypt broker credentials at rest.
    credential_encryption_key: SecretStr | None = None

    # ---- Trading mode gates (all default to the safe value) ----
    live_trading_enabled: bool = False
    owner_live_trading_approved: bool = False
    kill_switch_engaged: bool = False

    # ---- Paper worker ----
    paper_starting_balance_usd: float = 5.0
    paper_symbols: list[str] = Field(default_factory=lambda: ["BTCUSDT", "ETHUSDT"])
    paper_interval: str = "1h"
    paper_loop_seconds: int = 300
    market_data_source: str = "synthetic"  # "synthetic" | "binance_public"

    run_worker: bool = True
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    @property
    def live_trading_allowed(self) -> bool:
        """Config-level gate only. The risk engine applies further, independent checks."""
        return (
            self.live_trading_enabled
            and self.owner_live_trading_approved
            and not self.kill_switch_engaged
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
