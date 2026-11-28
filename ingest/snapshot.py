"""Promote the latest raw pull to the committed offline snapshot (data/sample/).

    python -m ingest.snapshot

The committed snapshot lets CI, the Streamlit app and the static site build
without network access. It is a verbatim copy of real public data from
data.cdc.gov (same filters as sources.yml), never synthetic. A size guard keeps
the repository small.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from ingest.storage import RAW_DIR, SAMPLE_DIR, read_manifest

MAX_BYTES = 5 * 1024 * 1024


def promote(raw_root: Path = RAW_DIR, sample_root: Path = SAMPLE_DIR) -> dict:
    """Copy raw snapshots that are newer than the committed ones into data/sample.

    Sources skipped by ingest (unchanged upstream) have no newer raw snapshot and
    are left exactly as committed, so an unchanged week produces no diff.
    """
    raw = read_manifest(raw_root)
    committed = read_manifest(sample_root)
    updated = {}
    for key, entry in sorted(raw.items()):
        old = committed.get(key)
        if old and old.get("loaded_at", "") >= entry["loaded_at"]:
            continue  # committed snapshot is the same pull or newer
        src = raw_root / entry["file"]
        dest_dir = sample_root / key
        if dest_dir.exists():
            shutil.rmtree(dest_dir)
        dest_dir.mkdir(parents=True)
        shutil.copy2(src, dest_dir / src.name)
        updated[key] = {**entry, "file": f"{key}/{src.name}"}

    if not updated:
        print("snapshot unchanged: no source has a newer pull than the committed snapshot")
        return committed

    manifest = {**committed, **updated}
    (sample_root / "_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    total = sum(p.stat().st_size for p in sample_root.rglob("*.parquet"))
    if total > MAX_BYTES:
        raise SystemExit(f"snapshot is {total/1e6:.1f} MB (> 5 MB limit); tighten filters")
    print(
        f"snapshot promoted: {', '.join(sorted(updated))} updated "
        f"({len(manifest)} sources, {total/1e6:.2f} MB)"
    )
    return manifest


if __name__ == "__main__":
    promote()
    sys.exit(0)
