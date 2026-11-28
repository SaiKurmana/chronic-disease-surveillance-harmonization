"""Numbers in hand-written docs must match the generated analysis output."""

from __future__ import annotations

import pytest

from analysis import doc_metrics


def test_docs_match_analysis_output():
    assert doc_metrics.main(["--check"]) == 0, "run: python -m analysis.doc_metrics"


def test_every_marker_key_is_known_and_used():
    metrics = doc_metrics.compute()
    used = set()
    for path in doc_metrics.DOCS:
        used |= {m.group(1) for m in doc_metrics.MARKER.finditer(path.read_text())}
    assert used <= set(metrics), sorted(used - set(metrics))
    assert used, "no metric markers found"


def test_unknown_marker_fails_loudly():
    with pytest.raises(KeyError):
        doc_metrics.render("x <!--m:not_a_metric-->1<!--/m--> y", {"a": "1"})


def test_render_replaces_only_marked_values():
    out = doc_metrics.render("36.2 and <!--m:a-->36.2<!--/m-->", {"a": "37.9"})
    assert out == "36.2 and <!--m:a-->37.9<!--/m-->"


@pytest.mark.parametrize(
    "years, expected",
    [
        ([2019, 2021, 2022, 2023], "2019 and 2021–2023"),
        ([2019], "2019"),
        ([2019, 2020, 2021], "2019–2021"),
        ([2015, 2017, 2019], "2015, 2017 and 2019"),
    ],
)
def test_year_ranges(years, expected):
    assert doc_metrics._year_ranges(years) == expected
