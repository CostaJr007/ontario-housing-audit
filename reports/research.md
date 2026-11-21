# Initial research — November 20, 2026

Historical research note, translated into English. Current outputs are described in [README](../README.md), the [2025 funding evidence](bff_2025_findings.md) and the [residential/funding comparison](residential_bff_2025_findings.md).

## Reproduced baseline

The complete official CSVs establish that **15 of the 50 individually targeted municipalities reached 100% in 2024**. The revised 2023 file gives 20. The BFF funding threshold is **80%**, so these full-target counts are not funding-eligibility counts. In 2024, 25 municipalities reached 80%.

The original reference post suggested a useful format: a concrete denominator, explicit criteria, a map and reproducible code. The analysis must retain the distinction between official housing progress and conventional construction starts.

| Item | Verified result or implication |
|---|---|
| Ontario catalogue | Complete English municipal CSVs for 2023/2024; no 2025 CSV in that dataset at the research snapshot |
| Provincial 2024 progress | 94,908 / 125,000 = 75.9264%, including the non-target aggregate |
| Reviewed 2024 starts | Official tracker: 73,617, or 58.8936% of the provincial target |
| Additional components | 14,381 ARUs; 2,278 LTC beds; 2,807 student beds; 1,825 retirement-home suites |
| Definition effect | 17.0328 percentage points provincially; this does not identify municipal reclassifications |
| Revisions | Reviewed annual figures can differ from original CMHC editions; preserve the data vintage |
| GeoHub | 685 raw features include islands/parts; dissolved municipal coverage is 414, not 685 governments |
| Names | Removing administrative prefixes is insufficient for ambiguous Hamilton names; final linkage uses MUNID |

Provincial components are an identified transcription of the official tracker, stored in `data/reference/tracker_composition_2024.json`. Tests reconcile them to the independently downloaded municipal CSV total.

## Subsequent work

The project now ingests the CMHC December 2025 municipal construction workbook and reconstructs selected 2025 BFF evidence from HTML, PDF and reviewed official records. Missing CSVs did not prevent the analysis; they required explicit source and coverage controls.

Original 2025 briefing claims came from [reported FOI material](https://globalnews.ca/news/12051237/ontario-housing-target-progress-2025/). The project does not convert those claims into a complete independently reproduced municipal table.

## Interpretation controls

1. Permits, starts and completions are different measures. Starts do not establish delivered homes or occupied family housing.
2. Independent ARUs are legitimate homes. Institutional beds and suites have different units of measurement.
3. The tracker identifies student beds and retirement suites as new categories from 2024.
4. Toronto CMA is not the City of Toronto. Municipal mapping requires compatible CSD or equivalent geography.
5. Compare equal time windows; do not sum seasonally adjusted annual rates or compare partial 2026 totals directly with a complete 2025 year.
6. Missing targets or data are not zero construction. Unorganized areas need not have municipal polygons.
7. Observed construction does not isolate the causal effect of municipal policy or funding.
8. Current GeoHub boundaries are not reconstructed historical boundaries. No area measurements are performed.

## Sources and reproducibility

- [Catalogue](https://data.ontario.ca/dataset/ontario-s-housing-supply-progress) and [metadata API](https://data.ontario.ca/api/3/action/package_show?id=ontario-s-housing-supply-progress).
- [Official tracker, components and revisions](https://www.ontario.ca/page/tracking-housing-supply-progress).
- [CMHC monthly data](https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research/housing-data/data-tables/housing-market-data/monthly-housing-starts-construction-data-tables) and [revised starts](https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research/housing-data/data-tables/housing-market-data/revised-housing-starts).
- [GeoHub municipal boundaries](https://geohub.lio.gov.on.ca/datasets/municipal-boundary-lower-and-single-tier), [official map service](https://ws.lioservices.lrc.gov.on.ca/arcgis2/rest/services/LIO_OPEN_DATA/LIO_Open03/MapServer/14) and [ArcGIS item](https://www.arcgis.com/sharing/rest/content/items/64fb702e16204c3e88b528d9759f1174?f=json).

Source URLs, dates and hashes are retained in `data/raw/manifest.json`. The project does not require changes to the user's IDE configuration or acp.json.
