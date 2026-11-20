# Cloudisoft AI Trading Lab — backend

```bash
uv sync
uv run pytest            # 83 tests
uv run ruff check src tests
uv run alembic upgrade head
uv run uvicorn cloudisoft_lab.api.app:app --reload   # API + 24x7 PAPER loop, docs at /docs
```
