"""Load dataset specs from sources.yml (single source of truth for provenance)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCES_FILE = REPO_ROOT / "sources.yml"


@dataclass(frozen=True)
class DatasetSpec:
    key: str
    domain: str
    name: str
    dataset_id: str
    url: str
    publisher: str
    where: str | None = None
    also_used_by: tuple[str, ...] = field(default_factory=tuple)
    extra: dict[str, Any] = field(default_factory=dict, compare=False, hash=False)


def load_sources(path: Path = SOURCES_FILE) -> list[DatasetSpec]:
    raw = yaml.safe_load(path.read_text())
    specs = []
    known = {"key", "domain", "name", "dataset_id", "url", "publisher", "where", "also_used_by"}
    for s in raw["sources"]:
        specs.append(
            DatasetSpec(
                key=s["key"],
                domain=s["domain"],
                name=s["name"],
                dataset_id=s["dataset_id"],
                url=s["url"],
                publisher=s["publisher"],
                where=s.get("where"),
                also_used_by=tuple(s.get("also_used_by") or ()),
                extra={k: v for k, v in s.items() if k not in known},
            )
        )
    return specs


def get_source(key: str, path: Path = SOURCES_FILE) -> DatasetSpec:
    for spec in load_sources(path):
        if spec.key == key:
            return spec
    raise KeyError(f"unknown source key: {key}")
