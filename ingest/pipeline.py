"""Shared ingest routine used by each domain module."""

from __future__ import annotations

import logging
from pathlib import Path

from ingest.registry import DatasetSpec, load_sources
from ingest.socrata import SocrataClient
from ingest.storage import RAW_DIR, is_current, prune_snapshots, write_snapshot

log = logging.getLogger(__name__)


def ingest_spec(
    spec: DatasetSpec,
    client: SocrataClient | None = None,
    *,
    force: bool = False,
    root: Path = RAW_DIR,
) -> Path | None:
    """Pull one dataset. Skips (idempotent) when the upstream version is unchanged."""
    client = client or SocrataClient()
    meta = client.metadata(spec.dataset_id)
    rows_updated_at = meta.get("rowsUpdatedAt")
    log.info(
        "%s (%s) '%s' rowsUpdatedAt=%s",
        spec.key,
        spec.dataset_id,
        meta.get("name"),
        rows_updated_at,
    )
    if not force and is_current(spec.key, rows_updated_at, spec.where, root):
        log.info("%s: up to date, skipping (use --force to re-pull)", spec.key)
        return None
    expected = client.count(spec.dataset_id, spec.where)
    rows = client.fetch_all(spec.dataset_id, where=spec.where)
    if len(rows) != expected:
        raise RuntimeError(
            f"{spec.key}: row count mismatch (expected {expected}, got {len(rows)})"
        )
    out = write_snapshot(
        spec.key,
        rows,
        dataset_id=spec.dataset_id,
        where=spec.where,
        rows_updated_at=rows_updated_at,
        root=root,
        columns=[
            c["fieldName"] for c in meta.get("columns", []) if not c["fieldName"].startswith(":")
        ],
    )
    prune_snapshots(spec.key, root=root)
    return out


def specs_for_domain(domain: str) -> list[DatasetSpec]:
    return [s for s in load_sources() if s.domain == domain]


def run_domain(domain: str, *, force: bool = False, root: Path = RAW_DIR) -> list[Path]:
    client = SocrataClient()
    written = []
    for spec in specs_for_domain(domain):
        out = ingest_spec(spec, client, force=force, root=root)
        if out:
            written.append(out)
    return written
