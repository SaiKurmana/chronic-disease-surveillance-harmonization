"""Chronic kidney disease domain.

* BRFSS Prevalence Data (dttw-5yxu): self-reported "ever told you have kidney
  disease" by state and stratifier (also carries BLIND for the vision overlap).
* U.S. Chronic Disease Indicators (hksd-2xuw): CKD01 incidence of treated
  end-stage kidney disease from USRDS (also carries DIA01 for diabetes).
"""

from __future__ import annotations

from pathlib import Path

from ingest.pipeline import run_domain
from ingest.storage import RAW_DIR

DOMAIN = "kidney"


def run(*, force: bool = False, root: Path = RAW_DIR) -> list[Path]:
    return run_domain(DOMAIN, force=force, root=root)


if __name__ == "__main__":
    from ingest.__main__ import main

    raise SystemExit(main(["--domain", DOMAIN]))
