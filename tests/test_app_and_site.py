"""Smoke tests for the serving layer (offline)."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DISCLAIMER = (
    "Independent portfolio project. Not affiliated with, endorsed by, or produced for the "
    "CDC. Uses only publicly available data."
)


def test_disclaimer_in_readme():
    assert DISCLAIMER in (ROOT / "README.md").read_text()


def test_streamlit_app_runs_offline_without_exceptions():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=120)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("Harmonization Lab" in t.value for t in at.title)
    assert any(DISCLAIMER in c.value for c in at.sidebar.caption), "disclaimer missing from sidebar"


def test_marts_have_provenance_on_every_row():
    import duckdb

    fct = (ROOT / "data" / "mart" / "fct_indicator_estimates.parquet").as_posix()
    nulls = duckdb.sql(
        f"select count(*) from read_parquet('{fct}') "
        "where dataset_id is null or source_url is null or loaded_at is null"
    ).fetchone()[0]
    assert nulls == 0


@pytest.mark.skipif(
    not (ROOT / "transform" / "target" / "catalog.json").exists(),
    reason="dbt docs not generated (run `make docs`)",
)
def test_site_builds(tmp_path, monkeypatch):
    from site_builder import build

    monkeypatch.setattr(build, "OUT", tmp_path / "_site")
    build.main()
    for page in (tmp_path / "_site").glob("*.html"):
        footer = page.read_text().split("<footer>", 1)[-1]
        assert DISCLAIMER in footer, f"disclaimer missing from footer of {page.name}"
        assert f'href="{build.APP_HREF}"' in footer, f"dashboard link missing from {page.name}"
    index = (tmp_path / "_site" / "index.html").read_text()
    assert f'href="{build.APP_HREF}"' in index.split("<footer>", 1)[0], "hero dashboard link"
    assert (tmp_path / "_site" / "dbt-docs" / "index.html").exists()
    for page in ("gap-report.html", "findings.html", "limitations.html", "sop.html"):
        assert (tmp_path / "_site" / page).exists(), page
