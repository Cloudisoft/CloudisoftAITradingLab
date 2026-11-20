"""Entry point: ``python -m cloudisoft_lab.worker.paper_loop`` — 24x7 PAPER trading only."""

from __future__ import annotations

import asyncio

from cloudisoft_lab.core.config import get_settings
from cloudisoft_lab.core.logging import configure_logging
from cloudisoft_lab.worker.factory import build_lab


def main() -> None:
    s = get_settings()
    configure_logging(s.log_level, s.log_json)
    asyncio.run(build_lab(s).run_forever())


if __name__ == "__main__":
    main()
