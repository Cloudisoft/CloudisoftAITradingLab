# Security Model

## Implemented (M4 foundation, tested)
| Control | Where |
|---|---|
| Live trading off by default; 8 independent live gates + per-market live flag | `core/config.py`, `risk/engine.py::LiveGates` |
| Immutable safety policy (frozen) | `risk/policy.py` |
| Emergency kill switch. Any operator may engage, only the owner may release. | `api/routes/core.py`, `worker/lab.py` |
| Credential encryption at rest (Fernet / AES-128-CBC + HMAC). Refuses to run without a key. | `core/security.py::CredentialVault` |
| Masking of credentials for display | `CredentialVault.mask` |
| Password hashing (argon2id) | `core/security.py` |
| JWT bearer auth (HS256, 60 min) + roles owner / operator / viewer | `api/deps.py` |
| Secret redaction in structured logs | `core/logging.py` |
| Tamper-evident audit log (SHA-256 hash chain, `verify()`) | `audit.py` |
| Idempotency on orders (router + broker + DB unique) and funding (DB unique) | `execution/`, `db/models.py` |
| Input validation on every API body (pydantic, bounded numbers, regex symbols) | `domain/schemas.py`, routes |
| Withdrawal workflow: owner-only approval, 7 explicit confirmations, no "completed" without a provider reference | `profit/manager.py` |
| Frontend never receives secrets. Token kept in sessionStorage (not localStorage). | `frontend/src/api.ts` |

## Owner rules for API keys (when adapters land)
* Create **trade-only** keys. **Never enable withdrawal permission.**
* Restrict keys to the deployment's static egress IP where the provider supports it.
* Paste keys only into the platform's credential form (encrypted server-side) or Railway variables.
  **Never in chat, never in git, never in the frontend.**
* Never share broker passwords, banking passwords, PINs or OTPs with the platform or any agent.
* Rotate keys on any suspicion. Each credential row tracks `rotated_at` / `revoked`.

## Added in session 2
| Control | Where |
|---|---|
| DB-backed users, owner bootstrap from env, operator/viewer roles, min 12-char passwords | `api/security.py` |
| TOTP 2FA (secret encrypted at rest), required at login once enabled | `api/security.py`, `/api/users/me/totp` |
| Login throttling 5/min/IP, mutation rate limit 60/min/IP | `SecurityMiddleware` |
| Security headers (nosniff, DENY framing, no-referrer, no-store, HSTS) | `SecurityMiddleware` |
| Security event log (login success/failure, 2FA enabled) | `security_events` table, `/api/security/events` |
| Persisted audit trail, startup refuses a tampered chain | `db/persistence.py` |
| Feed parser rejects entity declarations (XXE / billion-laughs) and >2 MB feeds | `agents/news.py` |
| Revenue compliance guard (no promised returns, no unlicensed advice, no spam) | `governance/revenue.py` |
| Agents can't self-replicate. Hard cap of 20. Spawn only via an owner-approved proposal. | `governance/agents.py` |
| LLM spend capped per agent, refused in CRITICAL/DEAD | `ai/llm.py` |
| CI: ruff (incl. bandit rules), pytest, pip-audit, npm audit | `.github/workflows/ci.yml` |
| Backup/restore and key-rotation runbook | `docs/OPERATIONS.md` |

Results on 2026-11-20: pip-audit **no known vulnerabilities**, npm audit **0 vulnerabilities**.

## Remaining
Key-rotation UI, Redis-backed limiter for multi-replica, CSP header for the static frontend (set at nginx/Railway).

## Compliance (must be verified by the owner, not assumed)
* **India (SEBI):** retail algo trading via broker APIs is governed by SEBI's framework (broker-registered
  algos, static IP, order-rate thresholds). Verify the current circular and Zerodha's implementation before live.
* **RBI/FEMA:** residents may trade currency derivatives only in permitted INR pairs on recognised Indian exchanges.
  Offshore forex/CFD platforms are not permitted. Forex is **disabled** in the registry.
* **Crypto (India):** VDA gains taxed at a flat rate plus TDS on transfers, and FIU-IND registration rules for exchanges.
  Verify current rates and the exchange's registration status before live.
* **US equities from India:** LRS limits.
* **Prediction markets:** jurisdiction-restricted. **Disabled.**

## Reporting
Security issues: contact the repository owner privately. Do not open public issues for vulnerabilities.
