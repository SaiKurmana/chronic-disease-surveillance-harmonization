# Limitations and appropriate use

This project shows a data-engineering and harmonization *method*. Its outputs
are descriptive summaries of published estimates. They are not new statistical
estimates and should not be used for clinical, policy or funding decisions
without going back to the original sources and their documentation.

## Reviewer quick reference

Three handling decisions affect what the outputs show. Each is explained in full
below. Counts are from the 2026-11-05 snapshot; the current counts are always in
[`analysis/output/gap_report.md`](../analysis/output/gap_report.md) (sections 6 and 9).

| Decision | What it means | Count (2026-11-05 snapshot) | Where to check |
|---|---|---|---|
| **Pilot uses crude rates** | The cross-condition pilot compares *crude* (not age-adjusted) prevalence, because self-reported kidney disease is published crude-only. ESKD incidence is the source's adjusted rate. Part of each state's position reflects its age structure. | 4 pilot indicators, 51 geographies, 2022 | `mart_pilot_state_profile`, [Crude vs age-adjusted](#methods-differ-across-sources) |
| **VEHSS lower CIs floored at 0** | Some published VEHSS lower 95% limits are below 0%. `ci_low` is set to 0, `ci_low_floored_flag = true`, and the published value is kept in `ci_low_published`. | 18 rows | `fct_indicator_estimates.ci_low_floored_flag`, gap report §6 |
| **Cross-classified rows dropped** | VEHSS cells with more than one stratifier (e.g. age × sex × race) are excluded, because the model keeps one stratifier per row. | 28,450 of 45,483 VEHSS rows | `int_vehss__estimates.n_strat_dims > 1`, gap report §9 |

Also excluded by design: BRFSS "median of states" rows (56; not population
estimates) and CDI ESKD counts (208; the mart holds rates only).

## Data are survey and registry estimates, not counts of people

* **BRFSS-based indicators** (diagnosed diabetes, self-reported kidney disease,
  vision difficulty) come from a weighted telephone survey of non-institutionalized
  adults. They are **self-reported**, subject to sampling error, non-response and
  recall bias, and exclude people in institutions such as nursing homes.
* **Self-reported kidney disease under-counts CKD.** Most people with chronic kidney
  disease are unaware of it, so "ever told you have kidney disease" measures
  diagnosed and recalled disease, not CKD prevalence from laboratory data.
* **Treated end-stage kidney disease (USRDS via CDI)** is registry-based and counts
  people starting dialysis or receiving a transplant. It is a rate per million
  adjusted for age, sex, race and ethnicity, and has **no published confidence
  intervals** in CDI. It cannot be compared on the same scale as survey percentages.
* **Vision difficulty** is a single functional-limitation question ("blind or serious
  difficulty seeing, even when wearing glasses"). It is not a measure of clinically
  examined visual acuity or of specific eye diseases.

## Methods differ across sources

* **BRFSS method change in 2011.** USDSS labels estimates up to 2010 and from 2011
  separately because BRFSS added cell-phone respondents and changed weighting
  (raking). Trends across 2010–2011 are not comparable; the model keeps the
  distinction in `data_source_raw` and `seed_data_source_crosswalk.method_note`.
* **Question changes.** The BRFSS kidney question id changes (CHCKIDNY 2011–2017,
  CHCKDNY1 2018, CHCKDNY2 2019+). The harmonized indicator joins them; check
  source documentation before reading small changes across those years as trends.
* **Crude vs age-adjusted (pilot caveat).** States differ in age structure. Use
  age-adjusted measures to compare states where they exist. The co-occurrence pilot
  uses **crude** prevalence for diabetes, kidney disease and vision difficulty,
  because self-reported kidney disease is published crude-only in the source used.
  Age structure can therefore push the same states up on all three crude
  measures, which can make them appear together in the top third more often than
  age-adjusted measures would. ESKD incidence is the source's rate adjusted for age, sex, race
  and ethnicity, so it is on a different basis from the other three.
* **Different stratification definitions.** Age bands differ (USDSS 18–44/45–64/
  65–74/75+, VEHSS 18–39/40–64/65+, BRFSS 10-year bands, CDI 18–44/45–64/65+).
  Only **65+** is shared by most sources, and USDSS splits it in two for
  diagnosed diabetes. Race and ethnicity groupings also differ (for example USDSS
  combines Asian and Pacific Islander; VEHSS "Asian" does not specify Hispanic
  ethnicity). The model keeps non-equivalent groups as separate values instead of
  forcing them together.
* **Cross-classified rows dropped.** VEHSS publishes cells that combine stratifiers
  (for example age × sex, or age × sex × race). The harmonized model keeps one
  stratifier per row, so the 28,450 VEHSS rows with more than one non-total
  stratifier (of 45,483 pulled) are not in the mart. They remain in the raw snapshot.
  Vision difficulty for, say, women aged 65+ is therefore not available in the
  harmonized model, even though VEHSS publishes it.

## Overlapping sources do not always agree

Where two systems publish the same BRFSS-based indicator, estimates are very close
in most years. The gap report shows one exception. For diagnosed diabetes in
**2020**, 36.2% of cells matched between CDI and USDSS differ by more than 0.5
percentage points, compared with 2.7–4.0% in 2019 and 2021–2023.

**The cause is not determined from these data.** Neither dataset documents why its
2020 values differ from the other's.

*Possible context only:* CDC's *Comparability of Data, BRFSS 2020* (August 2021)
documents that BRFSS data collection changed in 2020. It reports that the
shelter-in-place shift beginning in March 2020 "produced different results across
the states"; that collection "was interrupted in some areas for a short time";
that many states did not collect all 12 monthly samples; and that 32 states, DC and
Puerto Rico continued 2020 data collection into early 2021. That document describes
the survey, not how USDSS or CDI processed 2020 data, so it does not explain the
difference between the two published series. Treat 2020 diabetes comparisons
across sources with caution.

## Suppression and missing data

Each source suppresses unstable estimates with its own rule (for example,
denominator under 50 or relative standard error over 30%). Suppressed cells are
kept with `estimate = null` and `suppressed_flag = true`. Missing cells are
therefore **not random**: small states and small subgroups are missing more often.
Rankings and medians are computed only over reported values.

## Confidence intervals

* Intervals are used **as published**, with one adjustment. **18 VEHSS lower limits
  are below 0%** (snapshot of 2026-11-05). These intervals are symmetric around the
  estimate, which can cross zero for rare outcomes in small groups (most are
  race/ethnicity strata). For these rows the harmonized `ci_low` is floored at 0,
  `ci_low_floored_flag` is true, and `ci_low_published` keeps the original value.
  No other bound or estimate is changed.
* State ranks and tertiles in the pilot are **point-estimate ranks**. Neighbouring
  states often have overlapping intervals and may not differ meaningfully. The
  pilot table reports how many top-third states have a lower limit above the
  median of states.
* Overlap of two 95% intervals is a conservative visual check, not a formal test.

## No causal or individual-level claims

State-level correlations (for example between diabetes and kidney disease
prevalence) are **ecological**. They describe how states rank together, not
whether the same people have both conditions, and they are not evidence that one
condition causes another. The only person-level co-occurrence shown is what VEHSS
publishes directly (vision difficulty among adults with and without diabetes),
and that comparison is also descriptive and unadjusted for other factors.

## Scope and timeliness

* Data are a snapshot taken on the pull date recorded in `data/sample/_manifest.json`.
  Upstream datasets are revised. The weekly refresh workflow proposes updates as pull
  requests.
* Only state, territory and national levels are included. County estimates (for
  example CDC PLACES or VEHSS modeled estimates) are out of scope for this pilot.
* The CDC Chronic Kidney Disease Surveillance System website was unavailable
  (HTTP 503) when this project was built, and its data are not published on the
  Socrata portal. Kidney indicators therefore come from BRFSS Prevalence and CDI.

## References

* Centers for Disease Control and Prevention. *Behavioral Risk Factor Surveillance
  System: Comparability of Data, BRFSS 2020.* August 2021.
  <https://www.cdc.gov/brfss/annual_data/2020/pdf/compare-2020-508.pdf>
  (section A, "2020 Data Anomalies and Deviations from the Sampling Frame").
* Data sources: see [`sources.yml`](../sources.yml) and the README.

## Not an official product

Independent portfolio project. Not affiliated with, endorsed by, or produced for the
CDC. Uses only publicly available data.
