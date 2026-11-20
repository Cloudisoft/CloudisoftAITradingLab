# Development Log

## 2026-11-20 — Session 1 (Claude Code, cloud container)
**Milestones 1–4 done, and core logic for 8, 9, 11, 12 and 14 built and tested.**

- Audited the environment: the repo was empty. Linux cloud container, not the target Windows box. Broker/regulator docs blocked.
- Researched 20 repositories (license, activity, scope). Chose a native core, plus ccxt and kiteconnect as future adapters.
- Backend (Python 3.12, uv, FastAPI, SQLAlchemy 2, Alembic): config with safe defaults, credential vault,
  causal indicators, strategy DSL, backtester (next-bar fills, costs, partial fills, market hours, stops),
  walk-forward/OOS/Monte Carlo, immutable policy, risk engine (19 checks), paper broker, execution router,
  hash-chained audit, survival ledger/state machine/model router, profit manager & withdrawal workflow,
  scanner agent, 24×7 paper loop, REST API with roles, 23-table schema + migration.
- Frontend (React 19, Vite 8, Tailwind 4, Recharts): 18-section navigation. Overview, Survival Engine,
  Backtesting, Paper Trading/Portfolio and Security & Audit pages are live. The others show their milestone.
- E2E found and fixed: an empty ledger made a fresh install DEAD (ADR-5).
- E2E finding: with $5 at the default 50% position size, every signal is rejected as below the $5 minimum
  notional. Working as designed ("keep researching/paper trading").
- Tests: 83 passed (pytest). Ruff clean. Frontend build OK. Dashboard screenshots: no console errors.
- Not verified: Docker image builds (no Docker daemon in this container) and Railway deployment (not deployed).
- Alembic migration verified on SQLite and a temporary PostgreSQL 16 (23 tables).
