"""Diabetes domain: USDSS state burden indicators (b559-sbez).

The CDI diabetes indicator (DIA01) used as a cross-source overlap check is
pulled by the kidney module, because CDI is registered once (key cdi)
and both CDI indicators are fetched in a single filtered request.
"""

from __future__ import annotations

from pathlib import Path

from ingest.pipeline import run_domain
from ingest.storage import RAW_DIR

DOMAIN = "diabetes"


def run(*, force: bool = False, root: Path = RAW_DIR) -> list[Path]:
    return run_domain(DOMAIN, force=force, root=root)


if __name__ == "__main__":
    from ingest.__main__ import main

    raise SystemExit(main(["--domain", DOMAIN]))
