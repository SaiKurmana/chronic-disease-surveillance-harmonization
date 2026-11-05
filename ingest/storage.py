"""Raw-zone storage: timestamped parquet snapshots + a JSON load manifest.

Layout::

    data/raw/<key>/<key>__<YYYYMMDDTHHMMSSZ>.parquet
    data/raw/_manifest.json

Each parquet carries provenance columns (_source_key, _dataset_id,
_loaded_at, _source_rows_updated_at) so every downstream number can be traced
back to a specific pull.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "data" / "raw"


def utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def filter_hash(where: str | None) -> str:
    return hashlib.sha256((where or "").encode()).hexdigest()[:12]


def manifest_path(root: Path = RAW_DIR) -> Path:
    return root / "_manifest.json"


def read_manifest(root: Path = RAW_DIR) -> dict[str, Any]:
    p = manifest_path(root)
    if p.exists():
        return json.loads(p.read_text())
    return {}


def write_manifest(manifest: dict[str, Any], root: Path = RAW_DIR) -> None:
    root.mkdir(parents=True, exist_ok=True)
    manifest_path(root).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def is_current(
    key: str, rows_updated_at: int | None, where: str | None, root: Path = RAW_DIR
) -> bool:
    """True when the latest snapshot already reflects this source version + filter."""
    entry = read_manifest(root).get(key)
    if not entry or rows_updated_at is None:
        return False
    snapshot = root / entry["file"]
    return (
        snapshot.exists()
        and entry.get("source_rows_updated_at") == rows_updated_at
        and entry.get("filter_hash") == filter_hash(where)
    )


def write_snapshot(
    key: str,
    rows: list[dict[str, Any]],
    *,
    dataset_id: str,
    where: str | None,
    rows_updated_at: int | None,
    root: Path = RAW_DIR,
    loaded_at: datetime | None = None,
    columns: list[str] | None = None,
) -> Path:
    """Write one snapshot. ``columns`` (from Socrata metadata) guarantees a stable
    schema: SODA omits keys whose value is null, so an all-null column would
    otherwise silently disappear from the parquet file."""
    loaded_at = loaded_at or utc_now()
    df = pd.DataFrame.from_records(rows)
    for col in columns or []:
        if col not in df.columns:
            df[col] = None
    if columns:
        df = df[[*columns, *[c for c in df.columns if c not in columns]]]
    # Socrata returns nested dicts for point columns; keep raw zone flat + typed as text
    for col in df.columns:
        if df[col].map(lambda v: isinstance(v, (dict, list))).any():
            df[col] = df[col].map(lambda v: json.dumps(v) if isinstance(v, (dict, list)) else v)
    df = df.astype("string")
    df["_source_key"] = key
    df["_dataset_id"] = dataset_id
    df["_loaded_at"] = pd.Timestamp(loaded_at)
    df["_source_rows_updated_at"] = rows_updated_at

    ts = loaded_at.strftime("%Y%m%dT%H%M%SZ")
    out_dir = root / key
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{key}__{ts}.parquet"
    df.to_parquet(out, index=False, compression="zstd")

    manifest = read_manifest(root)
    manifest[key] = {
        "dataset_id": dataset_id,
        "file": str(out.relative_to(root)),
        "loaded_at": loaded_at.isoformat(),
        "rows": int(len(df)),
        "source_rows_updated_at": rows_updated_at,
        "filter": where,
        "filter_hash": filter_hash(where),
    }
    write_manifest(manifest, root)
    log.info("%s: wrote %d rows -> %s", key, len(df), out)
    return out


def prune_snapshots(key: str, keep: int = 3, root: Path = RAW_DIR) -> None:
    """Keep the N most recent snapshots for a source (raw zone is gitignored)."""
    files = sorted((root / key).glob(f"{key}__*.parquet"))
    for old in files[:-keep]:
        old.unlink()
        log.info("pruned %s", old)
