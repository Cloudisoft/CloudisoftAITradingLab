# Database Schema

SQLAlchemy 2 models: `backend/src/cloudisoft_lab/db/models.py`. Migration: `backend/migrations/versions/*_initial_schema.py`
(applied and verified on SQLite; PostgreSQL via Docker/Railway). Money columns are `NUMERIC(28,10)`. All tables carry
`id` (uuid hex) and `created_at`. Financial rows are never hard-deleted.

| Table | Purpose | Key constraints |
|---|---|---|
| users | owner/operator/viewer, argon2 hash, encrypted TOTP secret | email unique |
| accounts | provider account per user, mode paper/live | |
| broker_connections | status, verified permission flags | |
| encrypted_credentials | Fernet ciphertext, masked hint, rotation/revocation | |
| instruments | provider symbol + filters JSON | (provider, symbol) unique |
| market_data_refs | pointer to stored candle files | |
| strategies / strategy_versions | strategy + immutable versions with content fingerprint, author, change note | (strategy_id, version) unique |
| backtests | dataset, assumptions, metrics, kind (in_sample/oos/walk_forward/monte_carlo) | |
| orders | `client_order_id` idempotency key, mode, origin, risk decision link | client_order_id unique |
| trades | fills | |
| positions | per account/symbol | (account_id, symbol) unique |
| portfolio_snapshots | equity / cash / realised / unrealised, origin | |
| funding_transactions | deposits & withdrawals, provider ref, owner approval link | idempotency_key unique |
| survival_ledger | all ledger entries incl. operating expenses | index (kind, at) |
| inference_costs | per agent/model token usage & cost | |
| survival_state_history | transitions + snapshot | |
| agents / agent_tasks | isolated budget, scope, approver. Task history & cost. | name unique |
| risk_decisions | every check result | |
| owner_approvals | live trading / withdrawal / expansion / risk-limit approvals with confirmations | |
| security_events | auth failures, kill switch, key events | |
| audit_logs | hash-chained events | seq PK, hash unique |

**Current gap:** the running `Lab` keeps state in memory. Wiring repositories so the ledger, orders and audit
persist to these tables is the first task of M5 (TODO.md).
