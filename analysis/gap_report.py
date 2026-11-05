"""Gap & overlap report across the source systems.

    python -m analysis.gap_report

Reads only committed data (data/sample raw snapshot + data/mart marts) and writes:

* analysis/output/gap_report.md               full report (markdown)
* analysis/output/schema_comparison_matrix.md / .csv
* analysis/output/gap_metrics.json            numbers reused by the site and docs
"""

from __future__ import annotations

import pandas as pd

from analysis.common import OUT, SOURCE_ORDER, connect, df, md_table, snapshot_manifest, write_json

LABEL = {
    "usdss_state": "USDSS (b559-sbez)",
    "vehss_brfss": "VEHSS BRFSS (vkwg-yswv)",
    "brfss_prevalence": "BRFSS Prevalence (dttw-5yxu)",
    "cdi": "CDI (hksd-2xuw)",
}

# How each source physically encodes a concept: (columns, note). Columns are
# checked against the raw snapshot so this matrix cannot drift from real schemas.
C = tuple[list[str], str]
SCHEMA_CONCEPTS: list[tuple[str, dict[str, C]]] = [
    ("Indicator identifier", {
        "usdss_state": (["indicator"], "text label, no code"),
        "vehss_brfss": (["questionid", "question"], ""),
        "brfss_prevalence": (["questionid", "question"], "id changes across years"),
        "cdi": (["questionid", "question"], ""),
    }),
    ("Response / numerator definition", {
        "usdss_state": ([], "implicit in indicator"),
        "vehss_brfss": (["response"], ""),
        "brfss_prevalence": (["response"], "one row per answer"),
        "cdi": (["response"], "unused for CKD01/DIA01"),
    }),
    ("Measure type (crude / age-adjusted)", {
        "usdss_state": (["age", "unit"], "method mixed into the age column"),
        "vehss_brfss": (["data_value_type"], ""),
        "brfss_prevalence": (["data_value_type"], "crude only"),
        "cdi": (["datavaluetype"], ""),
    }),
    ("Unit", {
        "usdss_state": (["unit"], ""),
        "vehss_brfss": (["data_value_unit"], ""),
        "brfss_prevalence": (["data_value_unit"], ""),
        "cdi": (["datavalueunit"], ""),
    }),
    ("Time", {
        "usdss_state": (["year"], ""),
        "vehss_brfss": (["yearstart", "yearend"], ""),
        "brfss_prevalence": (["year"], ""),
        "cdi": (["yearstart", "yearend"], ""),
    }),
    ("Geography", {
        "usdss_state": (["state"], "USPS abbreviation only"),
        "vehss_brfss": (["locationabbr", "locationdesc", "locationid", "geographic_level"], ""),
        "brfss_prevalence": (["locationabbr", "locationdesc", "locationid"], ""),
        "cdi": (["locationabbr", "locationdesc", "locationid"], ""),
    }),
    ("Stratification layout", {
        "usdss_state": (["age", "race", "sex", "education"], "one column per stratifier"),
        "vehss_brfss": (["age", "sex", "raceethnicity", "riskfactor", "riskfactorresponse"],
                        "cross-classified cells"),
        "brfss_prevalence": (["break_out_category", "break_out"], "one stratifier per row"),
        "cdi": (["stratificationcategory1", "stratification1", "stratificationcategory2",
                 "stratification2", "stratificationcategory3", "stratification3"],
                "up to three pairs"),
    }),
    ("Point estimate", {
        "usdss_state": (["estimate"], ""),
        "vehss_brfss": (["data_value"], ""),
        "brfss_prevalence": (["data_value"], ""),
        "cdi": (["datavalue", "datavaluealt"], ""),
    }),
    ("Confidence interval", {
        "usdss_state": (["lowerlimit", "upperlimit"], ""),
        "vehss_brfss": (["low_confidence_limit", "high_confidence_limit"], ""),
        "brfss_prevalence": (["confidence_limit_low", "confidence_limit_high"], ""),
        "cdi": (["lowconfidencelimit", "highconfidencelimit"], ""),
    }),
    ("Standard error", {
        "usdss_state": (["seestimate"], ""),
        "vehss_brfss": ([], "not published"),
        "brfss_prevalence": ([], "not published"),
        "cdi": ([], "not published"),
    }),
    ("Sample size / numerator", {
        "usdss_state": ([], "not published"),
        "vehss_brfss": (["sample_size", "numerator", "weightedsample", "nonweightedsample"], ""),
        "brfss_prevalence": (["sample_size"], ""),
        "cdi": ([], "not published"),
    }),
    ("Suppression flag", {
        "usdss_state": (["estimatefootnote"], "text: Suppressed / No Data"),
        "vehss_brfss": (["data_value_footnote_symbol", "data_value_footnote"], "symbol #"),
        "brfss_prevalence": (["data_value_footnote_symbol", "data_value_footnote"],
                             "symbols *, **, ***"),
        "cdi": (["datavaluefootnotesymbol", "datavaluefootnote"], "symbols *, ****"),
    }),
    ("Underlying data source", {
        "usdss_state": (["datasource"], "encodes BRFSS method break <=2010 / >=2011"),
        "vehss_brfss": (["datasource"], ""),
        "brfss_prevalence": (["datasource"], ""),
        "cdi": (["datasource"], "BRFSS or USRDS"),
    }),
]


def _cell(spec: C) -> str:
    cols, note = spec
    text = ", ".join(f"`{c}`" for c in cols) if cols else "—"
    return f"{text} ({note})" if note else text


def check_concept_columns(con) -> list[str]:
    """Return any column named in SCHEMA_CONCEPTS that is missing from the raw data."""
    missing = []
    for key in SOURCE_ORDER:
        cols = set(df(con, f"select * from raw_{key} limit 0").columns)
        for concept, per_source in SCHEMA_CONCEPTS:
            missing += [f"{key}.{c} ({concept})" for c in per_source[key][0] if c not in cols]
    return missing


def schema_matrix(con) -> pd.DataFrame:
    rows = []
    for concept, per_source in SCHEMA_CONCEPTS:
        rows.append({"Concept": concept, **{LABEL[k]: _cell(per_source[k]) for k in SOURCE_ORDER}})
    # computed rows
    ncols = {k: len(df(con, f"select * from raw_{k} limit 0").columns) - 4 for k in SOURCE_ORDER}
    rows.append({"Concept": "Published columns (excl. provenance)",
                 **{LABEL[k]: str(ncols[k]) for k in SOURCE_ORDER}})
    return pd.DataFrame(rows)


def source_summary(con) -> pd.DataFrame:
    man = snapshot_manifest()
    mart = df(con, """
        select source_key, count(*) as mart_rows,
               count(distinct indicator_id) as indicators,
               min(year) as first_year, max(year) as last_year
        from fct_indicator_estimates group by 1""").set_index("source_key")
    src = df(con, "select * from dim_source").set_index("source_key")
    rows = []
    for k in SOURCE_ORDER:
        rows.append({
            "Source": LABEL[k],
            "Domain": src.loc[k, "domain"],
            "Raw rows (filtered pull)": int(man[k]["rows"]),
            "Harmonized rows": int(mart.loc[k, "mart_rows"]),
            "Indicators": int(mart.loc[k, "indicators"]),
            "Years": f"{int(mart.loc[k, 'first_year'])}-{int(mart.loc[k, 'last_year'])}",
            "Pulled (UTC)": man[k]["loaded_at"][:10],
        })
    return pd.DataFrame(rows)


def indicator_coverage(con) -> pd.DataFrame:
    return df(con, """
        select indicator_id as "Indicator", source_key as "Source",
               string_agg(distinct measure_type, ', ' order by measure_type) as "Measure types",
               min(year)::varchar || '-' || max(year)::varchar as "Years",
               count(distinct year) as "N years",
               count(distinct geo_fips) filter (where geo_level = 'state') as "States+DC",
               count(distinct geo_fips) filter (where geo_level = 'territory') as "Territories",
               case when bool_or(geo_level = 'national') then 'yes' else 'no' end as "National row",
               any_value(data_source) as "Data source"
        from fct_indicator_estimates
        group by 1, 2 order by 1, 2""")


def year_matrix(con) -> pd.DataFrame:
    d = df(con, """
        select indicator_id || ' / ' || source_key as series, year
        from fct_indicator_estimates where estimate is not null group by 1, 2""")
    years = list(range(int(d.year.min()), int(d.year.max()) + 1))
    out = []
    for s, g in d.groupby("series"):
        have = set(g.year)
        marks = {str(y)[-2:]: ("●" if y in have else "") for y in years}
        out.append({"Indicator / source": s, **marks})
    return pd.DataFrame(out)


def strat_coverage(con) -> pd.DataFrame:
    d = df(con, """
        select strat_category, source_key,
               string_agg(distinct strat_value, ', ' order by strat_value) as vals
        from fct_indicator_estimates group by 1, 2""")
    piv = d.pivot(index="strat_category", columns="source_key", values="vals").reindex(
        columns=SOURCE_ORDER).fillna("—")
    piv.columns = [LABEL[c] for c in piv.columns]
    order = ["overall", "sex", "age_group", "race_ethnicity", "education", "income",
             "diabetes_status", "hypertension_status", "smoking_status"]
    piv = piv.reindex([o for o in order if o in piv.index])
    return piv.reset_index().rename(columns={"strat_category": "Stratification"})


def ci_conventions(con) -> pd.DataFrame:
    return df(con, """
        select source_key as "Source", unit as "Unit",
               round(100.0 * avg((ci_low is not null and ci_high is not null)::int)
                     filter (where estimate is not null), 1) as "% with CI",
               round(100.0 * avg((standard_error is not null)::int)
                     filter (where estimate is not null), 1) as "% with SE",
               sum(ci_low_floored_flag::int) as "Negative lower CI (floored)",
               round(median(ci_high - ci_low) filter (where unit = 'percent'), 2)
                 as "Median CI width (pp)"
        from fct_indicator_estimates group by 1, 2 order by 1, 2""")


RAW_VALUE_COL = {
    "usdss_state": "estimate",
    "vehss_brfss": "data_value",
    "brfss_prevalence": "data_value",
    "cdi": "datavalue",
}


def precision(con) -> pd.DataFrame:
    """Decimal places as published (from raw strings, before any casting)."""
    parts = []
    for k, col in RAW_VALUE_COL.items():
        parts.append(f"""
            select '{k}' as source_key,
                   length(coalesce(regexp_extract({col}, '\\.(\\d+)$', 1), '')) as decimals
            from raw_{k} where {col} is not null""")
    return df(con, "with d as (" + " union all ".join(parts) + """)
        select source_key as "Source",
               mode(decimals) as "Typical decimals",
               count(*) filter (where decimals > 4) as "Values with float artifacts (>4 dp)",
               any_value(decimals) filter (where decimals > 4) as "Example artifact length"
        from d group by 1 order by 1""")


def suppression(con) -> pd.DataFrame:
    return df(con, """
        select source_key as "Source",
               count(*) as "Rows",
               round(100.0 * avg((data_status = 'suppressed')::int), 1) as "% suppressed",
               round(100.0 * avg((data_status = 'not_available')::int), 1) as "% not available",
               string_agg(distinct footnote, ' ‖ ') filter (where data_status <> 'reported')
                 as "Footnotes used for non-reported cells"
        from fct_indicator_estimates group by 1 order by 1""")


def overlap(con) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    base = """
        with p as (
          select a.indicator_id, a.measure_type, a.year,
                 a.source_key as source_a, b.source_key as source_b,
                 a.estimate as ea, b.estimate as eb,
                 a.ci_low as al, a.ci_high as ah, b.ci_low as bl, b.ci_high as bh,
                 a.data_status as sa, b.data_status as sb
          from fct_indicator_estimates a
          join fct_indicator_estimates b
            using (indicator_id, measure_type, geo_fips, year, strat_category, strat_value)
          where a.source_key < b.source_key)
    """
    summary = df(con, base + """
        select indicator_id as "Indicator", source_a as "Source A", source_b as "Source B",
               measure_type as "Measure", count(*) as "Matched cells",
               count(*) filter (where ea is not null and eb is not null) as "Both reported",
               round(avg(eb - ea), 2) as "Mean diff (B-A, pp)",
               round(avg(abs(eb - ea)), 2) as "Mean abs diff (pp)",
               round(100.0 * avg((abs(eb - ea) <= 0.5)::int), 1) as "% within 0.5 pp",
               round(corr(ea, eb), 3) as "Pearson r",
               round(100.0 * avg((al <= bh and bl <= ah)::int), 1) as "% CIs overlap",
               count(*) filter (where (sa = 'suppressed') <> (sb = 'suppressed'))
                 as "Suppression disagreements"
        from p group by 1, 2, 3, 4 order by 1, 4""")
    by_year = df(con, base + """
        select indicator_id as "Indicator", source_a || ' vs ' || source_b as "Pair",
               year::varchar as "Year",
               count(*) filter (where ea is not null and eb is not null) as "Both reported",
               round(avg(abs(eb - ea)), 2) as "Mean abs diff (pp)",
               round(100.0 * avg((abs(eb - ea) > 0.5)::int), 1) as "% differing > 0.5 pp"
        from p where ea is not null and eb is not null
        group by 1, 2, 3 order by 1, 2, 3""")
    pairs = df(con, base + """
        select indicator_id, source_a, source_b, measure_type, year, ea, eb
        from p where ea is not null and eb is not null""")
    return summary, by_year, pairs


def dropped_rows(con) -> pd.DataFrame:
    rows = [
        ("VEHSS BRFSS", "Cross-classified cells (>1 stratifier, e.g. age x sex x race)",
         df(con, """select count(*) n from raw_vehss_brfss where
            (age <> '18 years and older')::int + (sex <> 'Both sexes')::int
            + (raceethnicity <> 'All races')::int
            + (riskfactor <> 'All participants')::int > 1""").n[0]),
        ("BRFSS Prevalence", "Median-of-states rows (US / UW), not population estimates",
         df(con, """select count(*) n from raw_brfss_prevalence
            where locationdesc ilike '%(median)%'""").n[0]),
        ("CDI", "CKD01 counts (Number) excluded from the rate-based mart",
         df(con, """select count(*) n from raw_cdi where questionid = 'CKD01'
            and datavaluetype = 'Number'""").n[0]),
    ]
    return pd.DataFrame(rows, columns=["Source", "Excluded by design", "Rows"])


def build() -> dict:
    con = connect()
    missing = check_concept_columns(con)
    if missing:
        raise SystemExit(f"schema matrix references missing columns: {missing}")

    summ = source_summary(con)
    matrix = schema_matrix(con)
    cov = indicator_coverage(con)
    years = year_matrix(con)
    strata = strat_coverage(con)
    ci = ci_conventions(con)
    prec = precision(con)
    supp = suppression(con)
    ov, ov_year, ov_pairs = overlap(con)
    dropped = dropped_rows(con)

    OUT.mkdir(parents=True, exist_ok=True)
    matrix.to_csv(OUT / "schema_comparison_matrix.csv", index=False)
    (OUT / "schema_comparison_matrix.md").write_text(
        "# Schema comparison matrix\n\nHow each source physically encodes the same concepts "
        "(column names verified against the raw snapshot).\n\n" + md_table(matrix) + "\n"
    )
    ov_pairs.to_parquet(OUT / "overlap_pairs.parquet", index=False)

    md = [
        "# Gap & overlap report",
        "",
        "_Generated by `python -m analysis.gap_report` from the committed snapshot "
        "(`data/sample/`) and harmonized marts (`data/mart/`). Do not edit by hand._",
        "",
        "## 1. Sources compared",
        "",
        md_table(summ),
        "",
        "## 2. Schema comparison matrix",
        "",
        "Same concepts, four physical layouts:",
        "",
        md_table(matrix),
        "",
        "## 3. Indicator, geography and data-source coverage",
        "",
        md_table(cov),
        "",
        "## 4. Year coverage (● = at least one reported estimate)",
        "",
        md_table(years),
        "",
        "## 5. Stratification coverage (harmonized values)",
        "",
        md_table(strata),
        "",
        "## 6. Confidence-interval conventions",
        "",
        md_table(ci),
        "",
        "Published numeric precision (raw strings):",
        "",
        md_table(prec),
        "",
        "## 7. Suppression rules (as published in footnotes)",
        "",
        md_table(supp),
        "",
        "## 8. Overlap: same indicator published by two sources",
        "",
        "Cells matched on harmonized indicator, measure type, geography, year and stratum.",
        "",
        md_table(ov),
        "",
        "### By year",
        "",
        md_table(ov_year),
        "",
        "## 9. Rows excluded by design",
        "",
        md_table(dropped),
        "",
    ]
    (OUT / "gap_report.md").write_text("\n".join(md))

    metrics = {
        "source_summary": summ.to_dict(orient="records"),
        "indicator_coverage": cov.to_dict(orient="records"),
        "ci_conventions": ci.to_dict(orient="records"),
        "precision": prec.to_dict(orient="records"),
        "suppression": supp.to_dict(orient="records"),
        "overlap": ov.to_dict(orient="records"),
        "overlap_by_year": ov_year.to_dict(orient="records"),
        "dropped": dropped.to_dict(orient="records"),
    }
    write_json("gap_metrics.json", metrics)
    print(f"wrote {OUT / 'gap_report.md'}")
    return metrics


if __name__ == "__main__":
    build()
