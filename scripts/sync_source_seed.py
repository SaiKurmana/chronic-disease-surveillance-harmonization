"""Generate transform/seeds/seed_source_registry.csv from sources.yml.

sources.yml is the single source of truth for provenance; the seed lets dbt
join provenance onto every row. tests/test_registry_sync.py fails if they drift.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from ingest.registry import load_sources

REPO_ROOT = Path(__file__).resolve().parents[1]
SEED = REPO_ROOT / "transform" / "seeds" / "seed_source_registry.csv"
SYSTEM_LABELS = {
    "usdss_state": "USDSS",
    "vehss_brfss": "VEHSS",
    "brfss_prevalence": "BRFSS Prevalence & Trends",
    "cdi": "CDI",
}
FIELDS = [
    "source_key",
    "source_system",
    "domain",
    "dataset_name",
    "dataset_id",
    "url",
    "publisher",
    "access_date",
    "license",
    "filter",
]


def render() -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS, lineterminator="\n")
    w.writeheader()
    for s in load_sources():
        w.writerow(
            {
                "source_key": s.key,
                "source_system": SYSTEM_LABELS.get(s.key, s.extra.get("system", s.key)),
                "domain": s.domain,
                "dataset_name": s.name,
                "dataset_id": s.dataset_id,
                "url": s.url,
                "publisher": s.publisher,
                "access_date": str(s.extra.get("access_date", "")),
                "license": s.extra.get("license") or "",
                "filter": s.where or "",
            }
        )
    return buf.getvalue()


def main() -> None:
    SEED.write_text(render())
    print(f"wrote {SEED.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
