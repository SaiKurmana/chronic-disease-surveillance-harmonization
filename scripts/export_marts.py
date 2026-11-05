"""Export dbt marts + test results from the local DuckDB warehouse to data/mart/.

data/mart/ is committed so the Streamlit app and static site run fully offline.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE = REPO_ROOT / "data" / "warehouse.duckdb"
MART_DIR = REPO_ROOT / "data" / "mart"
RUN_RESULTS = REPO_ROOT / "transform" / "target" / "run_results.json"
MANIFEST = REPO_ROOT / "transform" / "target" / "manifest.json"

TABLES = [
    "fct_indicator_estimates",
    "dim_indicator",
    "dim_geography",
    "dim_stratification",
    "dim_source",
    "mart_pilot_state_profile",
]
CROSSWALKS = [
    "seeds.seed_indicator_crosswalk",
    "seeds.seed_stratification_crosswalk",
    "seeds.seed_data_source_crosswalk",
]


def export_tables(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    MART_DIR.mkdir(parents=True, exist_ok=True)
    counts = {}
    for t in TABLES + CROSSWALKS:
        name = t.split(".")[-1]
        out = MART_DIR / f"{name}.parquet"
        order = (
            " order by source_key, indicator_id, measure_type, geo_fips, year, strat_category,"
            " strat_value"
            if name == "fct_indicator_estimates"
            else " order by all"
        )
        con.execute(
            f"copy (select * from {t}{order}) to '{out}' (format parquet, compression zstd)"
        )
        counts[name] = con.execute(f"select count(*) from {t}").fetchone()[0]
    return counts


def summarize_tests() -> dict:
    """Condense dbt run_results.json into a small, committed test report."""
    if not RUN_RESULTS.exists():
        return {}
    rr = json.loads(RUN_RESULTS.read_text())
    nodes = json.loads(MANIFEST.read_text())["nodes"] if MANIFEST.exists() else {}
    tests = []
    for r in rr["results"]:
        uid = r["unique_id"]
        if not uid.startswith("test."):
            continue
        node = nodes.get(uid, {})
        meta = node.get("test_metadata") or {}
        attached = node.get("attached_node") or ""
        tests.append(
            {
                "name": node.get("name", uid.split(".")[2]),
                "test_type": meta.get("name", "singular"),
                "model": attached.split(".")[-1] if attached else "",
                "column": node.get("column_name") or "",
                "status": r["status"],
                "failures": r.get("failures"),
                "severity": (node.get("config") or {}).get("severity", "ERROR"),
                "message": r.get("message"),
            }
        )
    status_counts: dict[str, int] = {}
    for t in tests:
        status_counts[t["status"]] = status_counts.get(t["status"], 0) + 1
    return {
        "generated_at": rr["metadata"]["generated_at"],
        "dbt_version": rr["metadata"]["dbt_version"],
        "status_counts": status_counts,
        "tests": sorted(tests, key=lambda t: (t["status"] == "pass", t["model"], t["name"])),
    }


def main() -> None:
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    counts = export_tables(con)
    summary = summarize_tests()
    if summary:
        (MART_DIR / "dbt_test_results.json").write_text(json.dumps(summary, indent=2) + "\n")
    snap = REPO_ROOT / "data" / "sample" / "_manifest.json"
    meta = {
        "exported_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "row_counts": counts,
        "raw_snapshot": json.loads(snap.read_text()) if snap.exists() else {},
    }
    (MART_DIR / "_export_meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    size = sum(p.stat().st_size for p in MART_DIR.glob("*.parquet"))
    print(f"exported {len(counts)} tables to {MART_DIR.relative_to(REPO_ROOT)} ({size/1e6:.2f} MB)")


if __name__ == "__main__":
    main()
