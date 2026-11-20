# Operations Runbook

## Emergency kill switch
* Dashboard → Security & Audit → **ENGAGE** (any operator), or `POST /api/system/kill-switch {"engaged": true}`.
* Effect: the risk engine rejects every new order. Monitoring continues. The state persists across restarts.
* Only the owner can release it. Also settable at boot with `CLAB_KILL_SWITCH_ENGAGED=true`.

## Survival DEAD → recovery
1. Investigate (Reports, Survival Engine history, Trade Reviewer).
2. Add operating funds if you decide to (`owner_funding_operations` ledger entry). This is never automatic.
3. `POST /api/survival/recover` (owner). Nothing revives itself.

## Backups & restore (PostgreSQL)
```bash
pg_dump --format=custom "$DATABASE_URL" > clab-$(date +%F).dump
pg_restore --clean --if-exists -d "$DATABASE_URL" clab-YYYY-MM-DD.dump
```
On startup the app restores the `system_state` snapshot and **verifies the audit hash chain**. A
tampered chain aborts startup (`RecoveryError`) rather than continuing on corrupted records.
Normalised `audit_logs`, `survival_ledger` and `survival_state_history` rows give an independent trail.

## Key rotation
* `CLAB_JWT_SECRET`: rotate, then redeploy. All sessions are invalidated.
* `CLAB_CREDENTIAL_ENCRYPTION_KEY`: re-encrypt stored credentials before switching keys (no broker
  credentials are stored yet, since connections are deferred).
* Anthropic API key: rotate in the Anthropic Console, then update the variable.

## Code changes by AI agents
Agents may file a `code_change` proposal that must reference a git branch/PR. Changes ship only through
a reviewed PR with passing CI (`.github/workflows/ci.yml`). Rollback = revert the commit and redeploy.
Agents can't modify the immutable safety policy, approval rules, withdrawal restrictions or the risk engine at runtime.

## Health
`/health` (liveness), `/health/ready` (ticks + last error), `/api/notifications` (owner alerts).
