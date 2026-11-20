# Implementation Roadmap

| # | Milestone | Status |
|---|---|---|
| 1 | Environment & project audit | ✅ (cloud container; Windows checklist provided) |
| 2 | Repository research & compatibility | ✅ licenses/activity verified; stars/advisories TODO |
| 3 | Architecture, schema, security model | ✅ |
| 4 | Backend & frontend foundations | ✅ FastAPI, Alembic, React dashboard, Docker/Railway config |
| 5 | Auth, database, account management | 🟡 JWT + roles + vault done. DB-backed users, persistence, 2FA next. |
| 6 | Market data & scanner | 🟡 scanner + data-quality done. Real provider blocked on docs. |
| 7 | AI quant research modules | ⏳ News/Sentiment/Fundamental/LLM researcher via model router |
| 8 | Strategy generation & backtesting | 🟡 DSL, templates, engine, walk-forward, Monte Carlo done. NL→DSL generator, visual builder next. |
| 9 | Risk management & paper trading | 🟡 risk engine + paper broker + 24×7 paper loop done. Persistence pending. |
| 10 | Broker connections & portfolio | ⛔ blocked: official docs unreachable here, keys needed |
| 11 | Wallet & Funds, withdrawal approvals | 🟡 approval workflow done. UI + provider history pending. |
| 12 | Profit Manager & Survival Engine | 🟡 logic + dashboard done. Reports, notifications pending. |
| 13 | Self-improvement & expansion proposals | ⏳ |
| 14 | Security, compliance & failure testing | 🟡 failure sims for outage, kill switch, budget exhaustion, duplicates done |
| 15 | Railway deployment & docs | 🟡 Dockerfiles, compose, railway.json written. Not deployed (needs owner's Railway approval). |

## Path to live trading (owner decisions required)
1. Run the paper loop on **real** market data for ≥ 30 days (requires the market-data adapter).
2. Strategy must pass OOS + walk-forward + Monte Carlo with costs, and ≥ 50 paper trades.
3. Owner verifies compliance and creates trade-only, IP-restricted keys.
4. Owner flips `CLAB_LIVE_TRADING_ENABLED` and `CLAB_OWNER_LIVE_TRADING_APPROVED`, enables one market, and
   sets the execution policy (per-order confirmation by default).
5. Kill-switch drill, then the smallest viable live size.
