"""Shared helpers: load committed marts/raw snapshot with DuckDB, render markdown."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MART = ROOT / "data" / "mart"
SAMPLE = ROOT / "data" / "sample"
OUT = ROOT / "analysis" / "output"

SOURCE_ORDER = ["usdss_state", "vehss_brfss", "brfss_prevalence", "cdi"]

# The exported fact table omits `estimate_id` (a 64-bit md5 prefix over the grain,
# ~1 MB of incompressible hex) and readers recompute it with the exact expression
# used in transform/models/marts/fct_indicator_estimates.sql.
# tests/test_app_and_site.py checks the two stay identical.
FCT = "fct_indicator_estimates"
ESTIMATE_ID_SQL = (
    "left(md5(concat_ws('|', source_key, indicator_id, measure_type, geo_fips, year, "
    "strat_category, strat_value)), 16)"
)


def mart_view_sql(path: Path) -> str:
    """CREATE VIEW statement for one exported mart file (restores estimate_id)."""
    src = f"read_parquet('{path.as_posix()}')"
    if path.stem == FCT:
        return (
            f"create or replace view {FCT} as "
            f"select {ESTIMATE_ID_SQL} as estimate_id, * from {src}"
        )
    return f"create or replace view {path.stem} as select * from {src}"


def connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    for p in MART.glob("*.parquet"):
        con.execute(mart_view_sql(p))
    for key in SOURCE_ORDER:
        con.execute(
            f"create or replace view raw_{key} as select * from "
            f"read_parquet('{SAMPLE / key}/*.parquet', union_by_name=true) "
            f"qualify _loaded_at = max(_loaded_at) over ()"
        )
    return con


def df(con: duckdb.DuckDBPyConnection, sql: str) -> pd.DataFrame:
    return con.execute(sql).df()


def md_table(frame: pd.DataFrame) -> str:
    """Dependency-free GitHub markdown table."""
    def fmt(v):
        if v is None or (not isinstance(v, (str, list, dict)) and pd.isna(v)):
            return ""
        if hasattr(v, "item"):  # numpy scalar -> python
            v = v.item()
        if isinstance(v, float):
            return f"{v:,.3f}".rstrip("0").rstrip(".")
        if isinstance(v, int):
            return f"{v:,}"
        return str(v).replace("|", "\\|").replace("\n", " ")

    cols = [str(c) for c in frame.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for row in frame.itertuples(index=False):
        lines.append("| " + " | ".join(fmt(v) for v in row) + " |")
    return "\n".join(lines)


def write_json(name: str, obj) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / name
    p.write_text(json.dumps(obj, indent=2, default=str) + "\n")
    return p


def snapshot_manifest() -> dict:
    return json.loads((SAMPLE / "_manifest.json").read_text())
