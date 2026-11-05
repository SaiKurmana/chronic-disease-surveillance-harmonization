# Limitations and appropriate use

This project shows a data-engineering and harmonization *method*. Its outputs
are descriptive summaries of published estimates. They are not new statistical
estimates and should not be used for clinical, policy or funding decisions
without going back to the original sources and their documentation.

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
* **Crude vs age-adjusted.** States differ in age structure. Use age-adjusted
  measures to compare states where they exist. The pilot uses **crude** prevalence
  because self-reported kidney disease is published crude-only in the source used;
  part of the state-to-state pattern therefore reflects age structure.
* **Different stratification definitions.** Age bands differ (USDSS 18–44/45–64/
  65–74/75+, VEHSS 18–39/40–64/65+, BRFSS 10-year bands, CDI 18–44/45–64/65+).
  Only **65+** is shared by most sources, and USDSS splits it in two for
  diagnosed diabetes. Race and ethnicity groupings also differ (for example USDSS
  combines Asian and Pacific Islander; VEHSS "Asian" does not specify Hispanic
  ethnicity). The model keeps non-equivalent groups as separate values instead of
  forcing them together.
* **Cross-classified cells dropped.** VEHSS publishes age × sex × race cells. The
  harmonized model keeps one stratifier per row, so those cells (counted in the gap
  report) are not in the mart.

## Overlapping sources do not always agree

Where two systems publish the same BRFSS-based indicator, estimates are very close
in most years. The gap report shows an exception: **diagnosed diabetes for 2020
differs between CDI and USDSS in about a third of matched cells**. The published
datasets do not explain why. Possible reasons include different survey-year
handling or weighting for 2020, but this project has not confirmed the cause.
Treat 2020 diabetes comparisons across sources with caution and check the
publishers' methods notes.

## Suppression and missing data

Each source suppresses unstable estimates with its own rule (for example,
denominator under 50 or relative standard error over 30%). Suppressed cells are
kept with `estimate = null` and `suppressed_flag = true`. Missing cells are
therefore **not random**: small states and small subgroups are missing more often.
Rankings and medians are computed only over reported values.

## Confidence intervals

* Intervals are used **as published**. Some VEHSS lower limits are negative
  (symmetric intervals for rare outcomes in small groups). The harmonized `ci_low`
  is floored at 0 and `ci_low_floored_flag` marks the change, while
  `ci_low_published` keeps the original.
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

## Not an official product

Independent portfolio project. Not affiliated with, endorsed by, or produced for the
CDC. Uses only publicly available data.
