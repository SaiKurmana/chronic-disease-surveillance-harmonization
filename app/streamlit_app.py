"""Chronic Disease Surveillance Harmonization Lab — Streamlit dashboard.

Runs fully offline from the committed marts in data/mart/ (no network calls).

    streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analysis import style  # noqa: E402

MART = ROOT / "data" / "mart"
OUT = ROOT / "analysis" / "output"
DISCLAIMER = (
    "Independent portfolio project. Not affiliated with, endorsed by, or produced for the "
    "CDC. Uses only publicly available data."
)
# Served by Streamlit static serving (.streamlit/config.toml) so maps need no CDN.
PLOTLY_CONFIG = {"displaylogo": False, "topojsonURL": "app/static/topojson/"}

st.set_page_config(page_title="Surveillance Harmonization Lab", page_icon="🩺", layout="wide")


# --------------------------------------------------------------------- data
@st.cache_resource
def con() -> duckdb.DuckDBPyConnection:
    c = duckdb.connect()
    for p in MART.glob("*.parquet"):
        c.execute(f"create view {p.stem} as select * from read_parquet('{p.as_posix()}')")
    return c


@st.cache_data
def q(sql: str, params: tuple = ()) -> pd.DataFrame:
    return con().execute(sql, list(params)).df()


@st.cache_data
def meta() -> dict:
    p = MART / "_export_meta.json"
    return json.loads(p.read_text()) if p.exists() else {}


@st.cache_data
def test_results() -> dict:
    p = MART / "dbt_test_results.json"
    return json.loads(p.read_text()) if p.exists() else {}


def mode() -> str:
    try:
        return "dark" if st.context.theme.type == "dark" else "light"
    except Exception:  # older Streamlit
        return "light"


def show(fig: go.Figure, key: str) -> None:
    st.plotly_chart(style.apply_theme(fig, mode()), use_container_width=True,
                    config=PLOTLY_CONFIG, key=key)


PROVENANCE_COLS = [
    "estimate_id", "geo_name", "year", "strat_category", "strat_value", "estimate",
    "ci_low", "ci_high", "data_status", "source_system", "dataset_id", "source_url",
    "source_indicator_code", "source_measure", "raw_strat_category", "raw_strat_value",
    "data_source", "data_source_raw", "footnote", "ci_low_published", "loaded_at",
]


def provenance(frame: pd.DataFrame, label: str = "Source & provenance for these numbers") -> None:
    with st.expander(label):
        if frame.empty:
            st.caption("No rows.")
            return
        src = frame[["source_system", "dataset_id", "source_url"]].drop_duplicates()
        for r in src.itertuples():
            st.markdown(f"- **{r.source_system}** — data.cdc.gov dataset "
                        f"[`{r.dataset_id}`]({r.source_url})")
        loaded = pd.to_datetime(frame.loaded_at).max()
        st.caption(f"Raw snapshot pulled {loaded:%Y-%m-%d %H:%M} UTC. Each row below is one "
                   "harmonized estimate with the source's original codes and footnotes.")
        cols = [c for c in PROVENANCE_COLS if c in frame.columns]
        st.dataframe(frame[cols], hide_index=True, use_container_width=True,
                     column_config={"source_url": st.column_config.LinkColumn("source_url")})


# ------------------------------------------------------------------ sidebar
m = meta()
with st.sidebar:
    st.markdown("### Surveillance Harmonization Lab")
    st.caption("Diabetes · Vision & eye health · Chronic kidney disease")
    snap = m.get("raw_snapshot", {})
    if snap:
        st.markdown("**Data snapshot**")
        for k, v in sorted(snap.items()):
            st.caption(f"`{k}` · {v['dataset_id']} · pulled {v['loaded_at'][:10]}")
    st.divider()
    st.caption(DISCLAIMER)
    st.caption("Author: Sai Kurmana, MPH, MS, CPHIMS")

st.title("Chronic Disease Surveillance Harmonization Lab")
st.caption("Three surveillance domains, four public CDC datasets, one harmonized indicator model. "
           + DISCLAIMER)

tab_explore, tab_pilot, tab_overlap, tab_dq, tab_about = st.tabs(
    ["Explore indicators", "Co-occurrence pilot", "Source overlap", "Data quality",
     "Sources & methods"])

# ------------------------------------------------------------------ explore
with tab_explore:
    inds = q("select * from dim_indicator order by condition, indicator_id")
    c1, c2, c3, c4 = st.columns([2.2, 1.4, 1.4, 1])
    names_c = inds.indicator_name + "  ·  " + inds.condition
    ind_label = dict(zip(inds.indicator_id, names_c, strict=True))
    ind = c1.selectbox("Indicator", inds.indicator_id, format_func=ind_label.get)
    irow = inds.set_index("indicator_id").loc[ind]
    srcs = q("select distinct source_key, source_system from fct_indicator_estimates "
             "where indicator_id = ? order by source_key", (ind,))
    src_opts = srcs.source_key.tolist()
    primary = irow.primary_source_key
    src_default = src_opts.index(primary) if primary in src_opts else 0
    src = c2.selectbox("Source", src_opts, index=src_default,
                       format_func=dict(zip(srcs.source_key, srcs.source_system, strict=True)).get,
                       help="Primary source is selected by default; others are overlap sources.")
    mts = q("select distinct measure_type from fct_indicator_estimates where indicator_id = ? "
            "and source_key = ? order by 1", (ind, src)).measure_type.tolist()
    mt_default = mts.index(irow.pilot_measure_type) if irow.pilot_measure_type in mts else 0
    mt = c3.selectbox("Measure", mts, index=mt_default)
    yrs = q("select distinct year from fct_indicator_estimates where indicator_id = ? and "
            "source_key = ? and measure_type = ? and geo_level = 'state' and estimate is not null "
            "order by 1 desc", (ind, src, mt)).year.tolist()
    yr = c4.selectbox("Year", yrs)

    st.caption(irow.description)
    state = q("""select * from fct_indicator_estimates
                 where indicator_id = ? and source_key = ? and measure_type = ? and year = ?
                   and strat_category = 'overall' and geo_level = 'state'""",
              (ind, src, mt, yr))
    unit = state.unit.iloc[0] if not state.empty else ""
    rep = state[state.estimate.notna()]
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Median of states", f"{rep.estimate.median():.1f} {style.fmt_unit(unit)}"
              if not rep.empty else "—")
    k2.metric("States + DC reporting", f"{len(rep)} / 51")
    k3.metric("Range", f"{rep.estimate.min():.1f} – {rep.estimate.max():.1f}"
              if not rep.empty else "—")
    k4.metric("Suppressed cells", int(state.suppressed_flag.sum()))

    left, right = st.columns([3, 2])
    with left:
        st.markdown(f"**{irow.indicator_name}, {yr}** — {mt.replace('_', ' ')}, "
                    f"{style.fmt_unit(unit)}")
        fig = go.Figure(go.Choropleth(
            locations=state.geo_abbr, z=state.estimate, locationmode="USA-states",
            colorscale=style.SEQ_SCALE, marker_line_width=0.6,
            colorbar=dict(thickness=10, outlinewidth=0, title=style.fmt_unit(unit)),
            customdata=state[["geo_name", "ci_low", "ci_high", "data_status"]].values,
            hovertemplate="<b>%{customdata[0]}</b><br>%{z:.1f} (95% CI %{customdata[1]:.1f}–"
                          "%{customdata[2]:.1f})<br>%{customdata[3]}<extra></extra>",
        ))
        fig.update_geos(scope="usa", projection_type="albers usa", showframe=False)
        fig.update_layout(height=430, margin=dict(l=0, r=0, t=10, b=0))
        show(fig, "map")
        st.caption("Gray = no estimate (suppressed or not collected). Hover for CI and status.")

    with right:
        geos = q("select distinct geo_fips, geo_name, geo_level from fct_indicator_estimates "
                 "where indicator_id = ? and source_key = ? and year = ? "
                 "order by geo_level = 'national' desc, geo_name", (ind, src, yr))
        g = st.selectbox("Geography for stratified view", geos.geo_fips,
                         format_func=dict(zip(geos.geo_fips, geos.geo_name, strict=True)).get)
        cats = q("""select distinct strat_category from fct_indicator_estimates
                    where indicator_id = ? and source_key = ? and measure_type = ? and year = ?
                      and geo_fips = ? and strat_category <> 'overall'""",
                 (ind, src, mt, yr, g)).strat_category.tolist()
        if cats:
            cat = st.radio("Stratify by", sorted(cats), horizontal=True)
            strat = q("""select f.*, s.strat_label, s.sort_order
                         from fct_indicator_estimates f
                         join dim_stratification s using (strat_category, strat_value)
                         where indicator_id = ? and source_key = ? and measure_type = ?
                           and year = ? and geo_fips = ? and strat_category in (?, 'overall')
                         order by s.sort_order""", (ind, src, mt, yr, g, cat))
            sd = strat[strat.estimate.notna()]
            color = style.CONDITION_COLORS[mode()][irow.condition]
            bar = go.Figure(go.Bar(
                y=sd.strat_label, x=sd.estimate, orientation="h",
                marker=dict(color=color, cornerradius=4),
                error_x=dict(type="data", symmetric=False,
                             array=(sd.ci_high - sd.estimate).fillna(0),
                             arrayminus=(sd.estimate - sd.ci_low).fillna(0),
                             thickness=1.2, width=4, color="#898781"),
                hovertemplate="%{y}: %{x:.1f}<extra></extra>",
            ))
            bar.update_yaxes(autorange="reversed")
            bar.update_layout(height=max(260, 42 * len(sd) + 80), xaxis_title=style.fmt_unit(unit),
                              margin=dict(l=8, r=16, t=10, b=40), bargap=0.35)
            show(bar, "strat")
            missing = strat[strat.estimate.isna()]
            if not missing.empty:
                st.caption("Not shown (suppressed / not available): "
                           + ", ".join(missing.strat_label))
            st.caption("Error bars: 95% confidence interval as published by the source.")
        else:
            strat = pd.DataFrame()
            st.info("This source publishes no stratified estimates for this selection.")

    provenance(pd.concat([state, strat]) if not strat.empty else state)

# -------------------------------------------------------------------- pilot
with tab_pilot:
    prof = q("select * from mart_pilot_state_profile")
    yr_p = int(prof.year.iloc[0])
    st.markdown(f"#### Which states rank high on several conditions? ({yr_p})")
    st.caption("Primary source for each pilot indicator, all adults, 50 states + DC, latest year "
               "shared by all pilot indicators. Tertiles are ranks — overlapping CIs mean "
               "neighbouring states may not differ meaningfully. Descriptive only; no causal "
               "claims.")
    a, b = st.columns([1, 1])
    with a:
        show(style.cooccurrence_heatmap(prof), "heat")
    with b:
        dist = (prof.groupby("geo_abbr").n_top_tertile_conditions.first()
                .value_counts().sort_index(ascending=False))
        st.markdown("**States by number of pilot indicators in the top third**")
        st.dataframe(dist.rename("States").rename_axis("Indicators in top third").reset_index(),
                     hide_index=True)
        wide = prof.pivot(index="geo_abbr", columns="indicator_id", values="estimate")
        st.markdown("**Spearman rank correlation across states**")
        corr = wide.corr(method="spearman").round(2)
        st.dataframe(corr.rename(index=style.SHORT_NAME, columns=style.SHORT_NAME))
    show(style.choropleth_grid(prof), "grid")
    provenance(prof.assign(source_system=prof.source_key,
                           source_url="https://data.cdc.gov/d/" + prof.dataset_id,
                           loaded_at=pd.Timestamp(m.get("exported_at", "now"))),
               "Pilot rows")

# ------------------------------------------------------------------ overlap
with tab_overlap:
    st.markdown("#### Where two systems publish the same indicator, do they agree?")
    gm_path = OUT / "gap_metrics.json"
    if gm_path.exists():
        gm = json.loads(gm_path.read_text())
        st.dataframe(pd.DataFrame(gm["overlap"]), hide_index=True, use_container_width=True)
        st.markdown("**Agreement by year**")
        st.dataframe(pd.DataFrame(gm["overlap_by_year"]), hide_index=True,
                     use_container_width=True)
    pairs_p = OUT / "overlap_pairs.parquet"
    if pairs_p.exists():
        pairs = pd.read_parquet(pairs_p)
        cm = style.CONDITION_COLORS[mode()]
        a, b = st.columns(2)
        with a:
            st.markdown("**Diagnosed diabetes: CDI vs USDSS (crude, all matched cells)**")
            d = pairs[(pairs.indicator_id == "DIAB_DX_PREV")
                      & (pairs.measure_type == "crude_prevalence")]
            show(style.overlap_scatter(d, "CDI DIA01", "USDSS", 2020,
                                       (cm["diabetes"], cm["vision"])), "ov1")
        with b:
            st.markdown("**Vision difficulty: BRFSS Prevalence vs VEHSS (crude)**")
            d = pairs[pairs.indicator_id == "VIS_DIFF_SEE"]
            show(style.overlap_scatter(d, "BRFSS BLIND", "VEHSS ACSBL", None,
                                       (cm["vision"], cm["vision"])), "ov2")

# ------------------------------------------------------------- data quality
with tab_dq:
    tr = test_results()
    st.markdown("#### dbt test results")
    if tr:
        counts = tr.get("status_counts", {})
        c = st.columns(4)
        c[0].metric("Tests run", sum(counts.values()))
        c[1].metric("Pass", counts.get("pass", 0))
        c[2].metric("Warn", counts.get("warn", 0))
        c[3].metric("Fail / error", counts.get("fail", 0) + counts.get("error", 0))
        st.caption(f"dbt {tr.get('dbt_version')} · run at {tr.get('generated_at', '')[:19]} UTC")
        tdf = pd.DataFrame(tr["tests"])
        status = st.multiselect("Status", sorted(tdf.status.unique()),
                                default=sorted(tdf.status.unique()))
        st.dataframe(tdf[tdf.status.isin(status)], hide_index=True, use_container_width=True)
    else:
        st.warning("No dbt test results found. Run `make transform`.")
    st.markdown("#### Harmonized table profile")
    st.dataframe(q("""select source_system, indicator_id, count(*) as rows,
                             sum((data_status = 'reported')::int) as reported,
                             sum(suppressed_flag::int) as suppressed,
                             sum((data_status = 'not_available')::int) as not_available,
                             sum(ci_low_floored_flag::int) as ci_floored,
                             min(year) as first_year, max(year) as last_year
                      from fct_indicator_estimates group by all order by 1, 2"""),
                 hide_index=True, use_container_width=True)

# ------------------------------------------------------------------- about
with tab_about:
    st.markdown("#### Sources (all public, aggregate, de-identified)")
    st.dataframe(q("select * from dim_source"), hide_index=True, use_container_width=True,
                 column_config={"url": st.column_config.LinkColumn("url")})
    st.markdown("#### Crosswalks")
    c1, c2 = st.columns(2)
    c1.markdown("Indicator crosswalk")
    c1.dataframe(q("select * from seed_indicator_crosswalk"), hide_index=True)
    c2.markdown("Stratification crosswalk")
    c2.dataframe(q("select * from seed_stratification_crosswalk"), hide_index=True)
    st.markdown(
        "Estimates come from different surveillance systems with different designs. "
        "Survey estimates (BRFSS) are self-reported and weighted; ESKD incidence is "
        "registry-based (USRDS). Compare within a measure type and unit; read overlapping "
        "confidence intervals as 'no clear difference'. See `docs/limitations.md`."
    )
