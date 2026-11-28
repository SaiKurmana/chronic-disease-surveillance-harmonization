"""Fill the numbers in hand-written docs from the generated analysis output.

    python -m analysis.doc_metrics           # rewrite marked values in place
    python -m analysis.doc_metrics --check   # exit 1 if any doc is out of date

Prose in README.md and docs/limitations.md stays hand-written, but every number
taken from the data sits between invisible markers:

    <!--m:dm_2020_pct-->36.2<!--/m-->

The comments are invisible on GitHub and on the site. Each key must exist in
`compute()`: an unknown key, or a marker left in the text, fails loudly so a
refresh can never silently leave a stale number behind.
"""

from __future__ import annotations

import argparse
import json
import re
import sys

from analysis.common import OUT, ROOT

DOCS = [ROOT / "README.md", ROOT / "docs" / "limitations.md"]
MARKER = re.compile(r"<!--m:([a-z0-9_]+)-->(.*?)<!--/m-->", re.S)

_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
          "ten", "eleven", "twelve"]


def _word(n: int, cap: bool = False) -> str:
    w = _WORDS[n] if 0 <= n < len(_WORDS) else f"{n:,}"
    return w[:1].upper() + w[1:] if cap else w


def _pct(v: float) -> str:
    return f"{v:.1f}"


def _year_ranges(years: list[int]) -> str:
    """[2019, 2021, 2022, 2023] -> '2019 and 2021–2023'."""
    years = sorted(set(years))
    runs: list[list[int]] = []
    for y in years:
        if runs and y == runs[-1][-1] + 1:
            runs[-1].append(y)
        else:
            runs.append([y])
    parts = [f"{r[0]}" if len(r) == 1 else f"{r[0]}–{r[-1]}" for r in runs]
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def _one(rows: list[dict], **match) -> dict:
    hits = [r for r in rows if all(r.get(k) == v for k, v in match.items())]
    if len(hits) != 1:
        raise KeyError(f"expected one row matching {match}, found {len(hits)}")
    return hits[0]


def compute() -> dict[str, str]:
    gap = json.loads((OUT / "gap_metrics.json").read_text())
    pil = json.loads((OUT / "pilot_metrics.json").read_text())
    tests = json.loads((ROOT / "data" / "mart" / "dbt_test_results.json").read_text())
    snap = json.loads((ROOT / "data" / "sample" / "_manifest.json").read_text())

    dm = _one(gap["overlap"], Indicator="DIAB_DX_PREV", Measure="crude_prevalence")
    vs = _one(gap["overlap"], Indicator="VIS_DIFF_SEE", Measure="crude_prevalence")
    dm_years = [r for r in gap["overlap_by_year"] if r["Indicator"] == "DIAB_DX_PREV"]
    y2020 = _one(dm_years, Year="2020")
    others = [r for r in dm_years if r["Year"] != "2020"]
    other_pcts = [r["% differing > 0.5 pp"] for r in others]

    dropped = {r["Source"]: r["Rows"] for r in gap["dropped"]}
    vehss_raw = _one(gap["source_summary"], Source="VEHSS BRFSS (vkwg-yswv)")
    floored = int(sum(r["Negative lower CI (floored)"] or 0 for r in gap["ci_conventions"]))
    artifacts = _one(gap["precision"], Source="brfss_prevalence")

    sp = pil["spearman"]["DIAB_DX_PREV"]
    regions = pil["region_counts_3plus"]
    top_region, top_region_n = max(regions.items(), key=lambda kv: kv[1])
    vdm = {
        r["Diabetes status"]: r["Median of states (%)"]
        for r in pil["vision_by_diabetes"]
        if r["Measure"] == "age_adjusted_prevalence"
    }

    dates = sorted({v["loaded_at"][:10] for v in snap.values()})

    return {
        # dbt
        "n_dbt_tests": f"{sum(tests['status_counts'].values()):,}",
        # overlap
        "dm_within_half_pct": _pct(dm["% within 0.5 pp"]),
        "dm_2020_pct": _pct(y2020["% differing > 0.5 pp"]),
        "dm_other_years_min_pct": _pct(min(other_pcts)),
        "dm_other_years_max_pct": _pct(max(other_pcts)),
        "dm_other_years": _year_ranges([int(r["Year"]) for r in others]),
        "vis_within_half_pct": _pct(vs["% within 0.5 pp"]),
        # pilot
        "pilot_year": str(pil["pilot_year"]),
        "pilot_n_indicators": str(len(pil["indicators"])),
        "pilot_n_geos": str(pil["n_states"]),
        "rho_dm_ckd": f"{sp['CKD_SELF_REPORT']:.2f}",
        "rho_dm_vis": f"{sp['VIS_DIFF_SEE']:.2f}",
        "rho_dm_eskd": f"{sp['ESKD_INCIDENCE']:.2f}",
        "n_top_all_word_cap": _word(len(pil["states_top_all"]), cap=True),
        "states_top_all": ", ".join(pil["states_top_all"]),
        "n_top_3plus": str(len(pil["states_top_3plus"])),
        "top3plus_region_count": str(top_region_n),
        "top3plus_region": top_region,
        "vis_dm_yes_pct": _pct(vdm["yes"]),
        "vis_dm_no_pct": _pct(vdm["no"]),
        # data quality / exclusions
        "n_floored_ci": f"{floored:,}",
        "n_float_artifacts": f"{artifacts['Values with float artifacts (>4 dp)']:,}",
        "n_vehss_dropped": f"{dropped['VEHSS BRFSS']:,}",
        "n_vehss_raw": f"{vehss_raw['Raw rows (filtered pull)']:,}",
        "n_brfss_median_rows": f"{dropped['BRFSS Prevalence']:,}",
        "n_cdi_count_rows": f"{dropped['CDI']:,}",
        # snapshot
        "snapshot_dates": dates[0] if len(dates) == 1 else f"{dates[0]} to {dates[-1]}",
    }


def render(text: str, metrics: dict[str, str], where: str = "") -> str:
    def sub(m: re.Match) -> str:
        key = m.group(1)
        if key not in metrics:
            raise KeyError(f"{where}: unknown metric marker '{key}'")
        return f"<!--m:{key}-->{metrics[key]}<!--/m-->"

    return MARKER.sub(sub, text)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="fail if any doc is out of date")
    args = ap.parse_args(argv)
    metrics = compute()
    stale = []
    for path in DOCS:
        old = path.read_text()
        new = render(old, metrics, where=str(path.relative_to(ROOT)))
        if new != old:
            stale.append(str(path.relative_to(ROOT)))
            if not args.check:
                path.write_text(new)
    if args.check and stale:
        print("out of date (run `python -m analysis.doc_metrics`): " + ", ".join(stale))
        return 1
    print(("updated: " + ", ".join(stale)) if stale else "docs already match the analysis output")
    return 0


if __name__ == "__main__":
    sys.exit(main())
