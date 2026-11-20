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

## Not yet implemented (tracked in TODO.md)
TOTP 2FA, DB-backed users, rate limiting, CSRF review for cookie mode, security headers, persisted audit
sink, backup/restore runbook, dependency scanning in CI, key-rotation UI.

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
