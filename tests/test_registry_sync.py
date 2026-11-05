"""Guards that keep sources.yml, seeds and committed data consistent."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from ingest.registry import load_sources
from scripts.sync_source_seed import SEED, render

ROOT = Path(__file__).resolve().parents[1]
SEEDS = ROOT / "transform" / "seeds"


def read_csv(name: str) -> list[dict[str, str]]:
    with open(SEEDS / name, newline="") as f:
        return list(csv.DictReader(f))


def test_source_registry_seed_matches_sources_yml():
    assert SEED.read_text() == render(), "run: python -m scripts.sync_source_seed"


def test_crosswalk_sources_are_registered():
    keys = {s.key for s in load_sources()}
    for seed in (
        "seed_indicator_crosswalk.csv",
        "seed_stratification_crosswalk.csv",
        "seed_data_source_crosswalk.csv",
    ):
        assert {r["source_key"] for r in read_csv(seed)} <= keys, seed


def test_every_registered_source_has_a_committed_snapshot():
    manifest = json.loads((ROOT / "data" / "sample" / "_manifest.json").read_text())
    for s in load_sources():
        assert s.key in manifest, s.key
        assert manifest[s.key]["dataset_id"] == s.dataset_id
        assert (ROOT / "data" / "sample" / manifest[s.key]["file"]).exists()


def test_committed_data_is_small():
    total = sum(p.stat().st_size for p in (ROOT / "data").rglob("*.parquet")
                if "raw" not in p.parts)
    assert total < 5 * 1024 * 1024, f"committed parquet is {total/1e6:.1f} MB"


def test_state_fips_are_two_digit_and_unique():
    rows = read_csv("seed_geography.csv")
    fips = [r["geo_fips"] for r in rows]
    assert all(len(f) == 2 and f.isdigit() for f in fips)
    assert len(fips) == len(set(fips))
    assert sum(r["geo_level"] == "state" for r in rows) == 51  # 50 states + DC
