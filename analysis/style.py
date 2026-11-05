"""Shared visual tokens + Plotly figure builders (used by the site and the app).

Palette: the validated reference palette (first three categorical slots pass the
all-pairs colorblind checks in light and dark; one sequential blue ramp for
magnitude). Figures are built theme-neutral; `apply_theme` sets surfaces/ink.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

CONDITION_COLORS = {
    "light": {"diabetes": "#2a78d6", "vision": "#eb6834", "kidney": "#1baf7a"},
    "dark": {"diabetes": "#3987e5", "vision": "#d95926", "kidney": "#199e70"},
}
SEQ_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
SEQ_SCALE = [[i / (len(SEQ_BLUE) - 1), c] for i, c in enumerate(SEQ_BLUE)]
TERTILE_COLORS = {1: "#1c5cab", 2: "#6da7ec", 3: "#cde2fb"}  # top = darkest

THEMES = {
    "light": {
        "surface": "#fcfcfb", "ink": "#0b0b0b", "ink2": "#52514e", "muted": "#898781",
        "grid": "#e1e0d9", "axis": "#c3c2b7", "land": "#f0efec", "border": "#fcfcfb",
    },
    "dark": {
        "surface": "#1a1a19", "ink": "#f0efec", "ink2": "#c3c2b7", "muted": "#898781",
        "grid": "#2c2c2a", "axis": "#383835", "land": "#383835", "border": "#1a1a19",
    },
}
FONT = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'

SHORT_NAME = {
    "DIAB_DX_PREV": "Diabetes",
    "DIAB_NEW_INC": "New diabetes",
    "VIS_DIFF_SEE": "Vision difficulty",
    "CKD_SELF_REPORT": "Kidney disease (self-report)",
    "ESKD_INCIDENCE": "ESKD incidence",
}

UNIT_LABEL = {"percent": "%", "per_1000": "per 1,000", "per_1000000": "per 1,000,000"}


def apply_theme(fig: go.Figure, mode: str = "light") -> go.Figure:
    t = THEMES[mode]
    fig.update_layout(
        paper_bgcolor=t["surface"],
        plot_bgcolor=t["surface"],
        font=dict(family=FONT, color=t["ink2"], size=13),
        legend=dict(font=dict(color=t["ink2"])),
        hoverlabel=dict(font=dict(family=FONT)),
    )
    if fig.layout.title.text:  # styling an absent title makes some renderers print "undefined"
        fig.update_layout(title_font=dict(color=t["ink"], size=15))
    fig.update_xaxes(gridcolor=t["grid"], linecolor=t["axis"], zerolinecolor=t["axis"],
                     tickfont=dict(color=t["muted"]), title_font=dict(color=t["ink2"]))
    fig.update_yaxes(gridcolor=t["grid"], linecolor=t["axis"], zerolinecolor=t["axis"],
                     tickfont=dict(color=t["muted"]), title_font=dict(color=t["ink2"]))
    fig.update_geos(bgcolor=t["surface"], lakecolor=t["surface"], landcolor=t["land"],
                    subunitcolor=t["border"], showlakes=False)
    fig.update_traces(selector=dict(type="choropleth"),
                      marker_line_color=t["border"], marker_line_width=0.6)
    fig.update_annotations(font=dict(color=t["ink"]))
    return fig


def fmt_unit(unit: str) -> str:
    return UNIT_LABEL.get(unit, unit)


def choropleth_grid(profile: pd.DataFrame) -> go.Figure:
    """Small multiples: one US map per pilot indicator (own sequential scale each)."""
    inds = (profile[["indicator_id", "indicator_name", "unit", "condition"]]
            .drop_duplicates().sort_values(["condition", "indicator_id"]))
    n = len(inds)
    cols = 2
    rows = (n + cols - 1) // cols
    titles = [f"{r.indicator_name} ({fmt_unit(r.unit)})" for r in inds.itertuples()]
    fig = make_subplots(rows=rows, cols=cols, subplot_titles=titles,
                        specs=[[{"type": "geo"}] * cols for _ in range(rows)],
                        vertical_spacing=0.08, horizontal_spacing=0.02)
    for i, r in enumerate(inds.itertuples()):
        d = profile[profile.indicator_id == r.indicator_id]
        row, col = i // cols + 1, i % cols + 1
        geo_key = "geo" if i == 0 else f"geo{i + 1}"
        fig.add_trace(go.Choropleth(
            locations=d.geo_abbr, z=d.estimate, locationmode="USA-states",
            colorscale=SEQ_SCALE, showscale=True,
            colorbar=dict(len=0.38 if rows > 1 else 0.8, thickness=10,
                          x=0.47 if col == 1 else 0.99,
                          y=1 - (row - 0.5) / rows, outlinewidth=0),
            customdata=d[["geo_name", "state_rank", "n_states"]].values,
            hovertemplate="<b>%{customdata[0]}</b><br>%{z:.1f} " + fmt_unit(r.unit)
                          + "<br>rank %{customdata[1]} of %{customdata[2]}<extra></extra>",
            geo=geo_key,
        ), row=row, col=col)
    fig.update_geos(scope="usa", projection_type="albers usa", showframe=False,
                    showcoastlines=False)
    fig.update_layout(height=330 * rows, margin=dict(l=0, r=0, t=40, b=0))
    return fig


def cooccurrence_heatmap(profile: pd.DataFrame) -> go.Figure:
    """States x pilot indicators, colored by tertile (ordinal ramp, top = darkest)."""
    p = profile.copy()
    order = (p.groupby("geo_abbr")
             .agg(n=("n_top_tertile_conditions", "first"), s=("tertile", "sum"))
             .sort_values(["n", "s"], ascending=[False, True]).index.tolist())
    inds = p[["indicator_id", "indicator_name"]].drop_duplicates().sort_values("indicator_id")
    xlabels = [SHORT_NAME.get(i, n) for i, n in zip(inds.indicator_id, inds.indicator_name,
                                                      strict=True)]
    z = (p.pivot(index="geo_abbr", columns="indicator_id", values="tertile")
         .reindex(index=order, columns=inds.indicator_id))
    est = (p.pivot(index="geo_abbr", columns="indicator_id", values="estimate")
           .reindex(index=order, columns=inds.indicator_id))
    labels = {1: "Top third", 2: "Middle third", 3: "Bottom third"}
    text = z.map(lambda v: labels.get(v, "") if pd.notna(v) else "")
    scale = [[0, TERTILE_COLORS[1]], [0.33, TERTILE_COLORS[1]], [0.34, TERTILE_COLORS[2]],
             [0.66, TERTILE_COLORS[2]], [0.67, TERTILE_COLORS[3]], [1, TERTILE_COLORS[3]]]
    fig = go.Figure(go.Heatmap(
        z=z.values, x=xlabels, y=order, zmin=1, zmax=3,
        colorscale=scale, xgap=2, ygap=2, showscale=False,
        customdata=est.values, text=text.values,
        hovertemplate="<b>%{y}</b> · %{x}<br>%{text} (%{customdata:.1f})<extra></extra>",
    ))
    for k, name in labels.items():  # legend swatches (identity is never color-alone)
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", name=name,
                                 marker=dict(size=12, symbol="square", color=TERTILE_COLORS[k])))
    fig.update_yaxes(autorange="reversed", tickfont=dict(size=10), showgrid=False)
    fig.update_xaxes(side="top", showgrid=False, tickangle=0)
    fig.update_layout(height=max(420, 16 * len(order) + 110), plot_bgcolor="rgba(0,0,0,0)",
                      legend=dict(orientation="h", y=-0.02, yanchor="top", x=0),
                      margin=dict(l=40, r=8, t=40, b=40))
    return fig


def scatter_pair(wide: pd.DataFrame, x: str, y: str, xlab: str, ylab: str,
                 color: str, label_states: list[str]) -> go.Figure:
    """State-level scatter of two indicators (descriptive association only)."""
    fig = go.Figure(go.Scatter(
        x=wide[x], y=wide[y], mode="markers+text",
        text=[s if s in label_states else "" for s in wide.index],
        textposition="top center", textfont=dict(size=11),
        marker=dict(size=9, color=color, line=dict(width=1.5, color="rgba(255,255,255,0.9)")),
        customdata=wide.index,
        hovertemplate="<b>%{customdata}</b><br>" + xlab + ": %{x:.1f}<br>" + ylab
                      + ": %{y:.1f}<extra></extra>",
    ))
    fig.update_layout(xaxis_title=xlab, yaxis_title=ylab, height=420, showlegend=False)
    return fig


def overlap_scatter(pairs: pd.DataFrame, title_a: str, title_b: str,
                    highlight_year: int | None, colors: tuple[str, str]) -> go.Figure:
    """Source A vs source B for matched cells, 1:1 reference line."""
    fig = go.Figure()
    groups = [("Other years", pairs[pairs.year != highlight_year], colors[0])]
    if highlight_year is not None:
        groups.append((str(highlight_year), pairs[pairs.year == highlight_year], colors[1]))
    for name, d, c in groups:
        if d.empty:
            continue
        fig.add_trace(go.Scatter(
            x=d.ea, y=d.eb, mode="markers", name=name,
            marker=dict(size=6, color=c, opacity=0.65),
            hovertemplate=title_a + ": %{x:.2f}<br>" + title_b + ": %{y:.2f}<extra>"
                          + name + "</extra>",
        ))
    lo = float(min(pairs.ea.min(), pairs.eb.min()))
    hi = float(max(pairs.ea.max(), pairs.eb.max()))
    fig.add_trace(go.Scatter(x=[lo, hi], y=[lo, hi], mode="lines", name="1:1",
                             line=dict(width=1, color="#898781"), hoverinfo="skip"))
    fig.update_layout(xaxis_title=f"{title_a} (%)", yaxis_title=f"{title_b} (%)", height=420,
                      legend=dict(orientation="h", y=1.08, x=0))
    return fig
