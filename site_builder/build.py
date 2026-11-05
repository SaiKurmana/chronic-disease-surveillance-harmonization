"""Build the static GitHub Pages site into _site/.

    python -m site_builder.build      (or: make site)

Inputs are all committed or generated locally: analysis/output (reports, chart
specs, metrics), docs/*.md, data/mart (test results, export metadata) and dbt
docs in transform/target. No network access is needed to build; the published
pages load plotly.js and mermaid from public CDNs.
"""

from __future__ import annotations

import html
import json
import re
import shutil
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "_site"
ASSETS = Path(__file__).resolve().parent / "assets"
ANALYSIS = ROOT / "analysis" / "output"
DOCS = ROOT / "docs"
MART = ROOT / "data" / "mart"
DBT_TARGET = ROOT / "transform" / "target"
TOPOJSON = ROOT / "app" / "static" / "topojson" / "usa_110m.json"

REPO_URL = "https://github.com/SaiKurmana/chronic-disease-surveillance-harmonization"
PAGES_URL = "https://saikurmana.github.io/chronic-disease-surveillance-harmonization/"
# Hosted dashboard (Streamlit Community Cloud). Empty string falls back to the README quickstart.
APP_URL = "https://cdsh-lab.streamlit.app/"
APP_HREF = APP_URL or f"{REPO_URL}#quickstart"
PLOTLY_JS = "https://cdnjs.cloudflare.com/ajax/libs/plotly.js/3.1.1/plotly.min.js"
MERMAID_JS = "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"
DISCLAIMER = ("Independent portfolio project. Not affiliated with, endorsed by, or produced "
              "for the CDC. Uses only publicly available data.")
AUTHOR = "Sai Kurmana, MPH, MS, CPHIMS"

NAV = [
    ("index.html", "Overview"),
    ("findings.html", "Findings"),
    ("gap-report.html", "Gap report"),
    ("harmonization-report.html", "Recommendations"),
    ("data-quality.html", "Quality"),
    ("architecture.html", "Architecture"),
    ("docs.html", "Docs"),
    ("dbt-docs/index.html", "dbt docs"),
]

# markdown source -> page, used to rewrite cross-links between documents
MD_PAGES = {
    "analysis/output/pilot_findings.md": "findings.html",
    "analysis/output/gap_report.md": "gap-report.html",
    "analysis/output/schema_comparison_matrix.md": "gap-report.html#2-schema-comparison-matrix",
    "docs/harmonization_report.md": "harmonization-report.html",
    "docs/architecture.md": "architecture.html",
    "docs/SOP_onboarding_a_new_source.md": "sop.html",
    "docs/data_dictionary.md": "data-dictionary.html",
    "docs/limitations.md": "limitations.html",
}


# --------------------------------------------------------------- rendering
def page(title: str, body: str, current: str, description: str = "",
         charts: bool = False, mermaid: bool = False) -> str:
    nav = "".join(
        f'<a href="{href}"{" aria-current=page" if href == current else ""}>{label}</a>'
        for href, label in NAV
    )
    scripts = []
    if charts:
        scripts.append(f'<script src="{PLOTLY_JS}" charset="utf-8" defer></script>')
    if mermaid:
        scripts.append(f'<script src="{MERMAID_JS}" defer></script>')
    scripts.append('<script src="assets/site.js" defer></script>')
    desc = html.escape(description or "Harmonizing public diabetes, vision and kidney "
                       "surveillance data into one tested indicator model.")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} · Surveillance Harmonization Lab</title>
<meta name="description" content="{desc}">
<meta name="color-scheme" content="light dark">
<link rel="stylesheet" href="assets/style.css">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='%231c5cab'/%3E%3Cpath d='M7 17h5l2-6 4 12 2-6h5' stroke='white' stroke-width='2.4' fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E">
{''.join(scripts)}
</head>
<body>
<header class="site-header"><div class="wrap">
  <a class="brand" href="index.html">Harmonization Lab</a>
  <nav class="nav" aria-label="Primary">{nav}</nav>
  <button class="theme-toggle" type="button">Theme</button>
</div></header>
<main class="wrap">
{body}
</main>
<footer><div class="wrap">
  <p class="disclaimer">{DISCLAIMER}</p>
  <p>Author: {AUTHOR} · <a href="{REPO_URL}">Source code</a> ·
     <a href="{APP_HREF}">{"Dashboard" if APP_URL else "Run the dashboard"}</a> ·
     Data: <a href="https://data.cdc.gov">data.cdc.gov</a> (public, aggregate, de-identified)</p>
</div></footer>
</body>
</html>
"""


def rewrite_links(text: str, src_rel: str) -> str:
    base = Path(src_rel).parent

    def repl(m: re.Match) -> str:
        href = m.group(1)
        if href.startswith(("http://", "https://", "#", "mailto:")):
            return m.group(0)
        path, _, frag = href.partition("#")
        target = (base / path).as_posix()
        # normalise ../
        parts: list[str] = []
        for p in target.split("/"):
            if p == "..":
                if parts:
                    parts.pop()
            elif p not in ("", "."):
                parts.append(p)
        norm = "/".join(parts)
        if norm in MD_PAGES:
            new = MD_PAGES[norm]
            if frag and "#" not in new:
                new += "#" + frag
        else:
            new = f"{REPO_URL}/blob/main/{norm}" + (f"#{frag}" if frag else "")
        return f'href="{new}"'

    return re.sub(r'href="([^"]+)"', repl, text)


def md_to_html(text: str, src_rel: str) -> str:
    out = markdown.markdown(
        text, extensions=["tables", "fenced_code", "toc", "sane_lists", "footnotes"],
        extension_configs={"toc": {"permalink": False}},
    )
    out = re.sub(
        r'<pre><code class="language-mermaid">(.*?)</code></pre>',
        lambda m: f'<pre class="mermaid">{m.group(1)}</pre>', out, flags=re.S)
    out = out.replace("<table>", '<div class="table-wrap"><table>').replace(
        "</table>", "</table></div>")
    return rewrite_links(out, src_rel)


def chart(name: str, title: str, caption: str = "", height: int = 420) -> str:
    cap = f'<p class="caption">{caption}</p>' if caption else ""
    return (f'<div class="card chart-card"><h3>{title}</h3>{cap}'
            f'<div class="chart" data-chart="{name}" style="min-height:{height}px" '
            f'role="img" aria-label="{html.escape(title)}"></div></div>')


def md_page(src: Path, out_name: str, title: str, wide: bool = False,
            pre: str = "", post: str = "", charts: bool = False) -> None:
    rel = src.relative_to(ROOT).as_posix()
    text = src.read_text()
    body = (f'<article class="prose{" wide" if wide else ""}">{pre}{md_to_html(text, rel)}'
            f'{post}</article>')
    write(out_name, page(title, body, out_name, charts=charts, mermaid="```mermaid" in text))


def write(name: str, content: str) -> None:
    p = OUT / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


# ------------------------------------------------------------------- pages
def index_page() -> None:
    gap = json.loads((ANALYSIS / "gap_metrics.json").read_text())
    pil = json.loads((ANALYSIS / "pilot_metrics.json").read_text())
    meta = json.loads((MART / "_export_meta.json").read_text())
    tests = json.loads((MART / "dbt_test_results.json").read_text())
    rows = meta["row_counts"]["fct_indicator_estimates"]
    tc = tests["status_counts"]
    n_tests = sum(tc.values())
    dm = next(r for r in gap["overlap"]
              if r["Indicator"] == "DIAB_DX_PREV" and r["Measure"] == "crude_prevalence")
    by_year = {(r["Indicator"], r["Year"]): r for r in gap["overlap_by_year"]}
    y2020 = by_year[("DIAB_DX_PREV", "2020")]
    sp = pil["spearman"]
    snap_date = min(v["loaded_at"][:10] for v in meta["raw_snapshot"].values())
    sources = gap["source_summary"]
    src_rows = "".join(
        f"<tr><td>{html.escape(s['Source'])}</td><td>{s['Domain']}</td>"
        f"<td>{s['Years']}</td><td>{s['Harmonized rows']:,}</td></tr>" for s in sources)
    arch = (DOCS / "architecture.md").read_text()
    flow = re.search(r"```mermaid\n(flowchart.*?)```", arch, re.S).group(1)

    body = f"""
<section class="hero">
  <p class="eyebrow">Public-health data engineering portfolio</p>
  <h1>Chronic Disease Surveillance Harmonization Lab</h1>
  <p class="lede">Surveillance systems for related chronic conditions are built in silos. They
  publish overlapping data in different shapes. This lab takes three domains, maps four public
  CDC datasets onto <strong>one tested indicator model</strong>, and compares what they say.</p>
  <ul class="chips">
    <li class="chip"><span class="dot diabetes"></span>Diabetes · USDSS, CDI</li>
    <li class="chip"><span class="dot vision"></span>Vision &amp; eye health · VEHSS, BRFSS</li>
    <li class="chip"><span class="dot kidney"></span>Kidney disease · BRFSS, CDI (USRDS)</li>
  </ul>
  <div class="cta">
    <a class="btn primary" href="findings.html">See the pilot findings</a>
    <a class="btn" href="gap-report.html">Gap &amp; overlap report</a>
    <a class="btn" href="{APP_HREF}">{"Interactive dashboard" if APP_URL else "Run the dashboard"}</a>
    <a class="btn" href="{REPO_URL}">Code on GitHub</a>
  </div>
</section>

<section>
  <div class="grid cols-4">
    <div class="card tile"><div class="label">Public datasets harmonized</div>
      <div class="value">{len(sources)}</div><div class="note">3 condition domains</div></div>
    <div class="card tile"><div class="label">Harmonized estimates</div>
      <div class="value">{rows:,}</div><div class="note">long format, provenance on every row</div></div>
    <div class="card tile"><div class="label">dbt data tests</div>
      <div class="value">{tc.get('pass', 0)}/{n_tests}</div>
      <div class="note">pass · {tc.get('warn', 0)} intentional warning</div></div>
    <div class="card tile"><div class="label">Data snapshot</div>
      <div class="value">{snap_date}</div><div class="note">refreshed weekly via PR</div></div>
  </div>
</section>

<section>
  <h2>The problem</h2>
  <p class="sub">Diabetes, vision loss and kidney disease are closely linked clinically. Their
  surveillance data are still published by separate systems, each with its own table layout,
  codes, age bands, interval conventions and suppression rules. Comparing them, or even
  noticing that two systems publish the same number, takes manual work every time.</p>
  <div class="grid cols-3">
    <div class="card"><h3>Four shapes, one model</h3><p>USDSS keeps one column per stratifier
      and hides "crude vs age-adjusted" in the age column. VEHSS publishes cross-classified cells.
      BRFSS uses break-out pairs. CDI uses up to three stratification pairs. Each is reshaped
      into one long format.</p></div>
    <div class="card"><h3>Mappings as data</h3><p>Indicator, stratification, data-source and
      geography crosswalks are reviewed CSV seeds. A custom dbt test fails the build when an
      upstream value is not mapped, and names the value to add.</p></div>
    <div class="card"><h3>Trust, then serve</h3><p>Keys, ranges, CI brackets, referential
      integrity and cross-source agreement are tested on every build. The dashboard and this
      site read only the tested marts, and every number links back to its source dataset.</p></div>
  </div>
</section>

<section>
  <h2>Architecture</h2>
  <p class="sub">Ingest → transform → serve. Lightweight and file-based: Python, DuckDB, dbt,
  Streamlit, GitHub Actions. <a href="architecture.html">Details</a>.</p>
  <pre class="mermaid">{html.escape(flow)}</pre>
</section>

<section>
  <h2>Key findings</h2>
  <p class="sub">Descriptive comparisons of published estimates. They are not causal and not
  individual-level. Read the <a href="limitations.html">limitations</a>.</p>
  <div class="grid cols-3">
    <div class="card tile"><div class="label">States in the top third on all 4 pilot indicators ({pil['pilot_year']})</div>
      <div class="value">{len(pil['states_top_all'])}</div>
      <div class="note">{', '.join(pil['states_top_all'])}</div></div>
    <div class="card tile"><div class="label">Rank correlation, diabetes × self-reported kidney disease</div>
      <div class="value">ρ = {sp['DIAB_DX_PREV']['CKD_SELF_REPORT']:.2f}</div>
      <div class="note">across 50 states + DC</div></div>
    <div class="card tile"><div class="label">CDI vs USDSS diabetes cells differing &gt; 0.5 pp in 2020</div>
      <div class="value">{y2020['% differing > 0.5 pp']}%</div>
      <div class="note">vs {dm['% within 0.5 pp']}% within 0.5 pp overall. Cause not
      determined from these data; <a href="limitations.html#overlapping-sources-do-not-always-agree">see limitations</a>.</div></div>
  </div>
  <div class="grid" style="margin-top:16px">
    {chart('pilot_maps', f"Pilot indicators by state, {pil['pilot_year']}",
           "Each map has its own scale. Hover for value and rank.", 680)}
  </div>
  <div class="grid cols-2" style="margin-top:16px">
    {chart('cooccurrence_heatmap', 'Where conditions co-occur at the state level',
           'States ordered by number of pilot indicators in the top third.', 900)}
    <div class="grid">
      {chart('diabetes_vs_ckd', 'Diabetes vs self-reported kidney disease',
             'One point per state. Ecological association only.')}
      {chart('overlap_diabetes', 'Same indicator, two systems: CDI vs USDSS',
             'All matched diabetes cells; 2020 highlighted.')}
    </div>
  </div>
</section>

<section>
  <h2>Data sources</h2>
  <p class="sub">All public, aggregate and de-identified, from data.cdc.gov. Full registry in
  <a href="{REPO_URL}/blob/main/sources.yml"><code>sources.yml</code></a>.</p>
  <div class="table-wrap"><table>
    <thead><tr><th>Dataset</th><th>Domain</th><th>Years</th><th>Harmonized rows</th></tr></thead>
    <tbody>{src_rows}</tbody></table></div>
  <p class="callout">{DISCLAIMER}</p>
</section>
"""
    write("index.html", page("Overview", body, "index.html", charts=True, mermaid=True))


def findings_page() -> None:
    post = (
        '<h2 id="charts">Charts</h2><div class="grid">'
        + chart("pilot_maps", "Pilot indicators by state", "Each map has its own scale.", 680)
        + '</div><div class="grid cols-2" style="margin-top:16px">'
        + chart("cooccurrence_heatmap", "Top-third co-occurrence", "", 900)
        + '<div class="grid">'
        + chart("diabetes_vs_ckd", "Diabetes vs self-reported kidney disease")
        + chart("diabetes_vs_vision", "Diabetes vs vision difficulty")
        + "</div></div>"
    )
    md_page(ANALYSIS / "pilot_findings.md", "findings.html", "Pilot findings",
            wide=True, post=post, charts=True)


def gap_page() -> None:
    post = (
        '<h2 id="overlap-charts">Overlap charts</h2><div class="grid cols-2">'
        + chart("overlap_diabetes", "Diagnosed diabetes: CDI vs USDSS (crude)",
                "Matched state/year/stratum cells. 2020 highlighted.")
        + chart("overlap_vision", "Vision difficulty: BRFSS Prevalence vs VEHSS (crude)",
                "Same BRFSS question published by two systems.")
        + "</div>"
    )
    md_page(ANALYSIS / "gap_report.md", "gap-report.html", "Gap & overlap report",
            wide=True, post=post, charts=True)


def data_quality_page() -> None:
    tr = json.loads((MART / "dbt_test_results.json").read_text())
    tc = tr["status_counts"]
    rows = "".join(
        f"<tr><td class='status-{t['status']}'>{t['status']}</td><td><code>{html.escape(t['name'])}</code></td>"
        f"<td>{html.escape(t['test_type'])}</td><td>{html.escape(t['model'])}</td>"
        f"<td>{html.escape(t['column'])}</td><td>{t['failures'] if t['failures'] is not None else ''}</td></tr>"
        for t in tr["tests"])
    body = f"""
<article class="prose wide">
<h1>Data quality</h1>
<p>Results of the last <code>dbt build</code> (dbt {tr['dbt_version']}, run
{tr['generated_at'][:19].replace('T', ' ')} UTC). The build runs every model and test in
dependency order; an error-severity failure stops the models downstream of it.</p>
<div class="grid cols-4">
  <div class="card tile"><div class="label">Tests</div><div class="value">{sum(tc.values())}</div></div>
  <div class="card tile"><div class="label">Pass</div><div class="value">{tc.get('pass', 0)}</div></div>
  <div class="card tile"><div class="label">Warn</div><div class="value">{tc.get('warn', 0)}</div>
    <div class="note">cross-source agreement check (by design)</div></div>
  <div class="card tile"><div class="label">Fail / error</div><div class="value">{tc.get('fail', 0) + tc.get('error', 0)}</div></div>
</div>
<p>The warning comes from <code>assert_overlap_sources_agree</code>. It lists cells where two
systems publish the same indicator but differ by more than 1 percentage point; see the
<a href="gap-report.html#8-overlap-same-indicator-published-by-two-sources">overlap section of
the gap report</a>.</p>
<div class="table-wrap"><table>
<thead><tr><th>Status</th><th>Test</th><th>Type</th><th>Model</th><th>Column</th><th>Failing rows</th></tr></thead>
<tbody>{rows}</tbody></table></div>
</article>"""
    write("data-quality.html", page("Data quality", body, "data-quality.html"))


def docs_index() -> None:
    items = [
        ("harmonization-report.html", "Harmonization report", "Findings and recommendations for harmonizing the systems."),
        ("architecture.html", "Architecture", "Ingest → transform → serve, data model, quality gates, CI/CD."),
        ("sop.html", "SOP: onboarding a new source", "Step-by-step: register, stage, crosswalk, test, document."),
        ("data-dictionary.html", "Data dictionary", "Every model and column, generated from dbt."),
        ("limitations.html", "Limitations", "Survey and registry caveats, comparability, appropriate use."),
        ("dbt-docs/index.html", "dbt docs", "Interactive lineage graph and model documentation."),
    ]
    cards = "".join(f'<a class="card" href="{h}" style="text-decoration:none"><h3>{t}</h3><p>{d}</p></a>'
                    for h, t, d in items)
    body = f'<section><h1>Documentation</h1><div class="grid cols-3">{cards}</div></section>'
    write("docs.html", page("Docs", body, "docs.html"))


def copy_assets() -> None:
    shutil.copytree(ASSETS, OUT / "assets", dirs_exist_ok=True)
    shutil.copytree(ANALYSIS / "charts", OUT / "assets" / "charts", dirs_exist_ok=True)
    (OUT / "assets" / "topojson").mkdir(parents=True, exist_ok=True)
    shutil.copy2(TOPOJSON, OUT / "assets" / "topojson" / TOPOJSON.name)
    (OUT / ".nojekyll").write_text("")


def copy_dbt_docs() -> None:
    dest = OUT / "dbt-docs"
    dest.mkdir(parents=True, exist_ok=True)
    needed = ["index.html", "manifest.json", "catalog.json"]
    missing = [f for f in needed if not (DBT_TARGET / f).exists()]
    if missing:
        raise SystemExit(f"dbt docs artifacts missing ({missing}); run `make docs` first")
    for f in needed:
        shutil.copy2(DBT_TARGET / f, dest / f)


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    copy_assets()
    copy_dbt_docs()
    index_page()
    findings_page()
    gap_page()
    md_page(DOCS / "harmonization_report.md", "harmonization-report.html",
            "Harmonization report", wide=True)
    md_page(DOCS / "architecture.md", "architecture.html", "Architecture")
    md_page(DOCS / "SOP_onboarding_a_new_source.md", "sop.html", "SOP: onboarding a new source")
    md_page(DOCS / "data_dictionary.md", "data-dictionary.html", "Data dictionary", wide=True)
    md_page(DOCS / "limitations.md", "limitations.html", "Limitations")
    data_quality_page()
    docs_index()
    n = len(list(OUT.rglob("*.html")))
    print(f"built {n} pages into {OUT}/")


if __name__ == "__main__":
    main()
