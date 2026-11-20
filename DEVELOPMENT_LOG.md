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

## 2026-11-20: Session 2 (owner: "leave connecting assets for now but complete everything")
**Milestones 5–15 completed, except broker/exchange connections (deferred) and the actual Railway deploy (needs approval).**

- **M5:** DB-backed users (owner bootstrap from env), operator/viewer roles, TOTP 2FA, login throttling (5/min/IP),
  mutation rate limit (60/min/IP), security headers, security-event table. Crash-safe persistence: full snapshot plus
  normalised audit/ledger/state-history rows, restored on startup with audit-chain verification. Alembic migration 2.
- **M6:** CSV historical-data upload with validation and labelling, a replay provider (`CLAB_MARKET_DATA_SOURCE=csv_replay`), owner-maintained holiday calendars.
- **M7:** `LLMGateway`: Claude via the official SDK with structured outputs (`beta.messages.parse`), server-side
  refusal fallback, model tier set by survival state, per-agent budgets with a worst-case pre-check, every call written to the ledger.
  Rule-based fallbacks when no key is set. News (RSS/Atom, XXE-guarded), sentiment, fundamentals, portfolio, trade reviewer.
- **M8:** NL→strategy (LLM with a flat schema, or a deterministic parser), visual builder, versioned store with rollback,
  comparison on out-of-sample metrics, promotion via owner proposal only.
- **M11–12:** Wallet & Funds service and UI. Withdrawal flow: request → owner checks 7 confirmations → simulated settlement →
  no "completed" without a reference. Profit Manager policy UI. Daily/monthly reports (Markdown). Owner webhook notifications.
  Revenue-opportunity desk with compliance guards. Only owner-recorded receipts with a payment reference count as revenue.
- **M13:** Improvement researcher (variants accepted only on an out-of-sample walk-forward gain), proposal board (owner-only
  decisions, explicit apply), agent registry (isolated budgets, task logs, hard cap of 20, spawn only from an approved proposal),
  expansion assessment (requires PROFITABLE, reserve, runway impact, payback).
- **M14:** Failure simulations: missing data, outage then recovery, volatility shock, CRITICAL state, failed withdrawal,
  replay exhaustion, tampered audit, DB restart. pip-audit: no known vulns. npm audit: 0.
- **M15:** CI workflow, Railway guide, operations runbook.
- **Bugs found by E2E/tests and fixed:** (1) simulated paper fees flipped a fresh install to DEAD; (2) synthetic data
  used `hash()` (randomised per process), which made a test flaky. Now crc32. (3) The header "Sign in" button label clashed
  with the form button. (4) Lists didn't refresh after actions.
- Tests: **119 passed** (3 consecutive runs). Ruff clean. Frontend: tsc + oxlint (3 cosmetic warnings) + build OK, code-split.
  Browser E2E: all 18 pages signed in, NL generation, news analysis, withdrawal approval. No console errors. No horizontal
  scroll at 390 px.

## 2026-11-20: Session 3 (deployment and beginner-friendly app)
- Deployed to Railway (project `cloudisoft-ai-trading-lab`: api, frontend, Postgres). Paper mode, live trading off.
- Production bootstrap: DB-held JWT secret and encryption key when not configured, a first-run owner setup code
  printed only in the server log (persisted until used), sealed plaintext owner password option.
- Security fix: validation errors no longer echo submitted values (a password had been reflected back).
- 2FA: QR code generated in the browser.
- **New simple app** (default view), in the style of consumer trading apps but an original design: Home (balance,
  bot sentence, watchlist, recent activity), Markets, Coin (TradingView Lightweight Charts candlesticks 1H/4H/1D with
  volume, plain-English "What the AI sees", your holding), one-tap Buy/Sell sheet with live safety-check preview,
  Orders, Bot (pause/resume, how it decides), More (sign in, add practice money, Pro tools, glossary).
  The previous 18 screens remain as "Pro tools".
- Backend: `/api/markets`, `/api/markets/{symbol}?tf=`, `/api/trade/preview`, `/api/trade` (same risk engine as the
  bot), `/api/bot` (plain-English status + on/off), `/api/activity`; `explain.py` translates indicators and risk
  reasons into plain language. Simulated prices now use realistic levels/volatility and current dates.
- E2E (desktop 1360px + iPhone 13): sign in → open Bitcoin → buy $20 → confirmation; all tabs; no console errors;
  no horizontal scroll. Bugs found and fixed: overflowing balance chart on phones, negative-money formatting,
  wrapped watchlist label, January-2025 chart dates, overly volatile simulated prices.
- Tests: 127 passed.
