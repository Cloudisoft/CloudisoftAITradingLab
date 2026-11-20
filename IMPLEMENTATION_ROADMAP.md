# Implementation Roadmap

Owner decision (session 2): **broker/exchange connections are deferred**. Everything else is built.

| # | Milestone | Status |
|---|---|---|
| 1 | Environment & project audit | ✅ |
| 2 | Repository research & compatibility | ✅ (stars/advisories still TODO) |
| 3 | Architecture, schema, security model | ✅ |
| 4 | Backend & frontend foundations | ✅ |
| 5 | Auth, database, account management | ✅ DB users, roles, TOTP 2FA, login throttling, rate limits, security headers, crash-safe persistence |
| 6 | Market data & scanner | ✅ scanner, data-quality gate, CSV upload + replay provider, holiday calendars · ⏸ live feeds (deferred with brokers) |
| 7 | AI quant research | ✅ news, sentiment, fundamental, portfolio, trade reviewer. Budget-aware Claude gateway with rule-based fallback. |
| 8 | Strategy generation & backtesting | ✅ NL→strategy (LLM + parser), visual builder, versioning/rollback, comparison, OOS, walk-forward, Monte Carlo |
| 9 | Risk management & paper trading | ✅ |
| 10 | Broker connections & portfolio | ⏸ connections deferred by owner · ✅ portfolio monitoring/analysis (paper) |
| 11 | Wallet & Funds, withdrawal approvals | ✅ (paper provider; live providers report "not connected") |
| 12 | Profit Manager & Survival Engine | ✅ + daily/monthly reports, owner notifications, revenue-opportunity desk |
| 13 | Self-improvement & expansion | ✅ walk-forward-gated improvement proposals, agent registry with budgets and a hard cap, expansion assessment, owner-approval board |
| 14 | Security, compliance & failure testing | ✅ failure simulations, pip-audit and npm audit clean, tamper-evident recovery |
| 15 | Railway deployment & docs | ✅ docs/CI/Docker ready · ⏸ actual deploy awaits owner approval |

## Path to live trading (owner decisions required)
1. Run the paper loop on **real** market data for ≥ 30 days (requires the market-data adapter).
2. Strategy must pass OOS + walk-forward + Monte Carlo with costs, and ≥ 50 paper trades.
3. Owner verifies compliance and creates trade-only, IP-restricted keys.
4. Owner flips `CLAB_LIVE_TRADING_ENABLED` and `CLAB_OWNER_LIVE_TRADING_APPROVED`, enables one market, and
   sets the execution policy (per-order confirmation by default).
5. Kill-switch drill, then the smallest viable live size.
