# Railway Deployment (paper mode)

> Not yet deployed. Deploying creates a paid, always-on service, so it needs the owner's go-ahead.
> Railway's docs were unreachable from the build environment. Check plan pricing and UI steps on
> railway.com before you start.

## What runs
| Service | Source | Notes |
|---|---|---|
| `api` | `backend/Dockerfile` (`railway.json`) | FastAPI + the 24×7 **paper** loop in-process. Runs `alembic upgrade head` on start. **Exactly 1 replica**: the paper loop, rate limiter and kill switch are in-process. |
| `frontend` | `frontend/Dockerfile` | Static nginx. Build arg `VITE_API_URL=https://<api domain>`. |
| PostgreSQL | Railway Postgres plugin | Snapshot + audit + ledger tables. Enable backups. |

## Steps
1. Create a Railway project from the GitHub repo.
2. Add PostgreSQL. In `api` variables set `CLAB_DATABASE_URL` to the Postgres URL with the driver prefix
   changed to `postgresql+asyncpg://`.
3. Set variables on `api` (Railway → Variables, **never** committed):
   | Variable | Value |
   |---|---|
   | `CLAB_ENVIRONMENT` | `production` |
   | `CLAB_JWT_SECRET` | `python -c "import secrets;print(secrets.token_urlsafe(48))"` |
   | `CLAB_CREDENTIAL_ENCRYPTION_KEY` | `python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"` |
   | `CLAB_OWNER_EMAIL` / `CLAB_OWNER_PASSWORD_HASH` | owner login (argon2 hash, see `.env.example`) |
   | `CLAB_CORS_ORIGINS` | `["https://<frontend domain>"]` |
   | `CLAB_LOG_JSON` | `true` |
   | `CLAB_PAPER_STARTING_BALANCE_USD` | e.g. `5` |
   | `CLAB_OWNER_WEBHOOK_URL` | optional HTTPS webhook for alerts |
   | `CLAB_NEWS_FEEDS` | optional JSON list of permitted RSS URLs |
   | `ANTHROPIC_API_KEY` | optional. Without it, agents run rule-based at $0 inference cost. |
   | `CLAB_LIVE_TRADING_ENABLED` / `CLAB_OWNER_LIVE_TRADING_APPROVED` | **leave `false`** |
4. Deploy `api`, then `frontend` with `VITE_API_URL`.
5. Verify: `GET /health` → ok. `GET /api/system/status` → `mode: paper`, `live_trading_allowed: false`.
6. Sign in, enable 2FA (Settings), and record the operating budget and real hosting cost in the
   Survival Engine ledger (`POST /api/survival/ledger`), so runway and survival state reflect reality.

## Cost reality
Record the real monthly Railway bill as `hosting_cost` (e.g. weekly). The survival engine will
then report runway honestly. With $5 of trading capital, the platform can't pay its own hosting
from trading. That needs owner funding or verified external revenue.
