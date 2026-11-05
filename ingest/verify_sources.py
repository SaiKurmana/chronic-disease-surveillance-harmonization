"""Re-verify every source in sources.yml: metadata reachable + a few real rows.

    python -m ingest.verify_sources

Exit code 1 if any source fails. Prints name, last update and row counts so the
registry can be audited without opening a browser.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime

from ingest.registry import load_sources
from ingest.socrata import SocrataClient, SocrataError


def main() -> int:
    client = SocrataClient(max_retries=3)
    ok = True
    for spec in load_sources():
        try:
            meta = client.metadata(spec.dataset_id)
            rows = client._get(
                f"https://{client.domain}/resource/{spec.dataset_id}.json",
                {"$limit": 3, **({"$where": spec.where} if spec.where else {})},
            )
            n = client.count(spec.dataset_id, spec.where)
            updated = datetime.fromtimestamp(meta.get("rowsUpdatedAt", 0), UTC)
            print(
                f"OK   {spec.key:18s} {spec.dataset_id}  '{meta['name']}'  "
                f"rows_updated={updated:%Y-%m-%d}  filtered_rows={n}  sample_rows={len(rows)}"
            )
            if not rows:
                ok = False
                print(f"FAIL {spec.key}: filter returned no rows")
        except SocrataError as exc:
            ok = False
            print(f"FAIL {spec.key:18s} {spec.dataset_id}  {exc}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
