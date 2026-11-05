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

from ingest.storage import RAW_DIR, read_manifest

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DIR = REPO_ROOT / "data" / "sample"
MAX_BYTES = 5 * 1024 * 1024


def promote(raw_root: Path = RAW_DIR, sample_root: Path = SAMPLE_DIR) -> dict:
    manifest = read_manifest(raw_root)
    if not manifest:
        raise SystemExit("no raw snapshots found; run `make ingest` first")
    out_manifest = {}
    for key, entry in sorted(manifest.items()):
        src = raw_root / entry["file"]
        dest_dir = sample_root / key
        if dest_dir.exists():
            shutil.rmtree(dest_dir)
        dest_dir.mkdir(parents=True)
        shutil.copy2(src, dest_dir / src.name)
        out_manifest[key] = {**entry, "file": f"{key}/{src.name}"}
    (sample_root / "_manifest.json").write_text(
        json.dumps(out_manifest, indent=2, sort_keys=True) + "\n"
    )
    total = sum(p.stat().st_size for p in sample_root.rglob("*.parquet"))
    if total > MAX_BYTES:
        raise SystemExit(f"snapshot is {total/1e6:.1f} MB (> 5 MB limit); tighten filters")
    print(f"snapshot promoted: {len(out_manifest)} sources, {total/1e6:.2f} MB")
    return out_manifest


if __name__ == "__main__":
    promote()
    sys.exit(0)
