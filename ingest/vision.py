"""Vision & eye health domain: VEHSS BRFSS summary table (vkwg-yswv).

The BRFSS Prevalence BLIND question used as an overlap check is pulled with the
kidney module's BRFSS request (key brfss_prevalence).
"""

from __future__ import annotations

from pathlib import Path

from ingest.pipeline import run_domain
from ingest.storage import RAW_DIR, SAMPLE_DIR

DOMAIN = "vision"


def run(
    *, force: bool = False, root: Path = RAW_DIR, baseline: Path | None = SAMPLE_DIR
) -> list[Path]:
    return run_domain(DOMAIN, force=force, root=root, baseline=baseline)


if __name__ == "__main__":
    from ingest.__main__ import main

    raise SystemExit(main(["--domain", DOMAIN]))
