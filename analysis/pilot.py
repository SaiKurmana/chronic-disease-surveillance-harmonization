"""Pilot: state comparisons and co-occurrence for the harmonized pilot indicators.

    python -m analysis.pilot

Inputs: data/mart (committed). Outputs in analysis/output/:
* pilot_findings.md     narrative numbers (generated)
* pilot_metrics.json    numbers reused by the site and docs
* charts/<name>.<light|dark>.json   Plotly figure specs for the static site

All statements are descriptive. State-level associations are ecological and
say nothing about individuals or causation.
"""

from __future__ import annotations

import json

import pandas as pd

from analysis import style
from analysis.common import OUT, connect, df, md_table, write_json

CHARTS = OUT / "charts"


def load(con):
    profile = df(con, "select * from mart_pilot_state_profile")
    geo = df(con, "select geo_fips, census_region from dim_geography")
    profile = profile.merge(geo, on="geo_fips", how="left")
    return profile


def wide_estimates(profile: pd.DataFrame) -> pd.DataFrame:
    return profile.pivot(index="geo_abbr", columns="indicator_id", values="estimate")


def indicator_summary(profile: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _ind, d in profile.groupby("indicator_id"):
        d = d.sort_values("estimate", ascending=False)
        med = d.estimate.median()
        has_ci = d.ci_low.notna().any()
        above = int((d.ci_low > med).sum()) if has_ci else None
        rows.append({
            "Indicator": d.indicator_name.iloc[0],
            "Source": d.source_key.iloc[0],
            "Measure": d.measure_type.iloc[0],
            "Unit": style.fmt_unit(d.unit.iloc[0]),
            "States": len(d),
            "Median": round(med, 1),
            "Lowest": f"{d.geo_abbr.iloc[-1]} {d.estimate.iloc[-1]:.1f}",
            "Highest": f"{d.geo_abbr.iloc[0]} {d.estimate.iloc[0]:.1f}",
            "Max/min ratio": round(d.estimate.max() / d.estimate.min(), 2),
            "Top-third states with CI above median": (
                f"{int(((d.tertile == 1) & (d.ci_low > med)).sum())} of "
                f"{int((d.tertile == 1).sum())}" if has_ci else "no CI published"),
            "_above": above,
        })
    return pd.DataFrame(rows)


def correlations(wide: pd.DataFrame) -> pd.DataFrame:
    return wide.corr(method="spearman").round(2)


def cooccurrence(profile: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    states = (profile.groupby(["geo_abbr", "geo_name", "census_region"], as_index=False)
              .agg(n_top=("n_top_tertile_conditions", "first"),
                   n_ind=("n_indicators_with_data", "first"),
                   top_in=("indicator_id",
                           lambda s: ", ".join(sorted(
                               s[profile.loc[s.index, "is_top_tertile"]].tolist())))))
    dist = (states.groupby("n_top").size().rename("States").reset_index()
            .rename(columns={"n_top": "Pilot indicators in top third"})
            .sort_values("Pilot indicators in top third", ascending=False))
    return states.sort_values(["n_top", "geo_abbr"], ascending=[False, True]), dist


def vision_by_diabetes(con, year: int) -> pd.DataFrame:
    """Person-level co-occurrence that VEHSS publishes: vision difficulty by diabetes status."""
    return df(con, f"""
        select measure_type as "Measure", strat_value as "Diabetes status",
               count(*) filter (where estimate is not null) as "States reporting",
               round(median(estimate), 1) as "Median of states (%)"
        from fct_indicator_estimates
        where indicator_id = 'VIS_DIFF_SEE' and source_key = 'vehss_brfss'
          and strat_category = 'diabetes_status' and geo_level = 'state' and year = {year}
        group by 1, 2 order by 1, 2""")


def save_chart(name: str, builder) -> None:
    CHARTS.mkdir(parents=True, exist_ok=True)
    for mode in ("light", "dark"):
        fig = style.apply_theme(builder(mode), mode)
        (CHARTS / f"{name}.{mode}.json").write_text(fig.to_json())


def build() -> dict:
    con = connect()
    profile = load(con)
    year = int(profile.year.iloc[0])
    wide = wide_estimates(profile)
    summ = indicator_summary(profile)
    corr = correlations(wide)
    states, dist = cooccurrence(profile)
    vis_dm = vision_by_diabetes(con, year)
    names = profile.drop_duplicates("indicator_id").set_index("indicator_id").indicator_name

    all_top = states[states.n_top == states.n_ind].geo_abbr.tolist()
    three_plus = states[states.n_top >= 3]
    region_counts = three_plus.census_region.value_counts().to_dict()

    # charts -------------------------------------------------------------
    save_chart("pilot_maps", lambda m: style.choropleth_grid(profile))
    save_chart("cooccurrence_heatmap", lambda m: style.cooccurrence_heatmap(profile))
    label = sorted(set(all_top) | set(wide.DIAB_DX_PREV.nlargest(2).index)
                   | set(wide.DIAB_DX_PREV.nsmallest(2).index))
    save_chart("diabetes_vs_ckd", lambda m: style.scatter_pair(
        wide, "DIAB_DX_PREV", "CKD_SELF_REPORT", "Diagnosed diabetes (%)",
        "Self-reported kidney disease (%)", style.CONDITION_COLORS[m]["kidney"], label))
    save_chart("diabetes_vs_vision", lambda m: style.scatter_pair(
        wide, "DIAB_DX_PREV", "VIS_DIFF_SEE", "Diagnosed diabetes (%)",
        "Blind / serious difficulty seeing (%)", style.CONDITION_COLORS[m]["vision"], label))

    pairs = pd.read_parquet(OUT / "overlap_pairs.parquet")
    dm = pairs[(pairs.indicator_id == "DIAB_DX_PREV") & (pairs.measure_type == "crude_prevalence")]
    vs = pairs[(pairs.indicator_id == "VIS_DIFF_SEE")]
    save_chart("overlap_diabetes", lambda m: style.overlap_scatter(
        dm, "CDI DIA01", "USDSS", 2020,
        (style.CONDITION_COLORS[m]["diabetes"], style.CONDITION_COLORS[m]["vision"])))
    save_chart("overlap_vision", lambda m: style.overlap_scatter(
        vs, "BRFSS Prevalence BLIND", "VEHSS ACSBL", None,
        (style.CONDITION_COLORS[m]["vision"], style.CONDITION_COLORS[m]["vision"])))

    # narrative ----------------------------------------------------------
    corr_disp = corr.rename(index=names, columns=names).reset_index().rename(
        columns={"indicator_id": "Spearman ρ (states)"})
    top_states = states[states.n_top >= 3][["geo_abbr", "geo_name", "census_region",
                                             "n_top", "top_in"]]
    top_states.columns = ["State", "Name", "Census region", "Top-third count",
                          "Indicators in top third"]
    md = [
        "# Pilot findings: state comparison and co-occurrence",
        "",
        "_Generated by `python -m analysis.pilot` from `data/mart/`. Descriptive only — "
        "state-level (ecological) associations do not describe individuals and do not imply "
        "causation. See [limitations](../../docs/limitations.md)._",
        "",
        f"**Pilot year:** {year} — the most recent year in which every pilot indicator has "
        f"state data from its primary source. **Geographies:** {profile.geo_abbr.nunique()} "
        "(50 states + DC). **Stratum:** all adults.",
        "",
        "## Pilot indicators by state",
        "",
        md_table(summ.drop(columns=["_above"])),
        "",
        "## How state rankings move together (Spearman rank correlation across states)",
        "",
        md_table(corr_disp),
        "",
        "## Co-occurrence: states in the top third on several conditions",
        "",
        md_table(dist),
        "",
        f"States in the top third on **all {profile.indicator_id.nunique()}** pilot indicators: "
        f"**{', '.join(all_top) if all_top else 'none'}**.",
        "",
        md_table(top_states),
        "",
        "Census region of states in the top third on 3+ indicators: "
        + ", ".join(f"{k} {v}" for k, v in sorted(region_counts.items(), key=lambda kv: -kv[1]))
        + ".",
        "",
        "## Person-level co-occurrence published by VEHSS",
        "",
        "VEHSS stratifies vision difficulty by diabetes status, which the harmonized model keeps "
        "as `strat_category = diabetes_status`. Median across states:",
        "",
        md_table(vis_dm),
        "",
    ]
    (OUT / "pilot_findings.md").write_text("\n".join(md))

    metrics = {
        "pilot_year": year,
        "n_states": int(profile.geo_abbr.nunique()),
        "indicators": summ.drop(columns=["_above"]).to_dict(orient="records"),
        "spearman": json.loads(corr.to_json()),
        "cooccurrence_distribution": dist.to_dict(orient="records"),
        "states_top_all": all_top,
        "states_top_3plus": three_plus.geo_abbr.tolist(),
        "region_counts_3plus": region_counts,
        "vision_by_diabetes": vis_dm.to_dict(orient="records"),
    }
    write_json("pilot_metrics.json", metrics)
    print(f"wrote {OUT / 'pilot_findings.md'} (pilot year {year})")
    return metrics


if __name__ == "__main__":
    build()
