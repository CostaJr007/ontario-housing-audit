# HAF outcome-audit feasibility

Research snapshot: November 20, 2026. This note records source feasibility and later ingestion findings; it does not turn metropolitan statistics into municipal outcomes.

## Verified dashboard ingestion

The public CMHC `HAFReportFilter` endpoint supplied both Ontario intake tables: **61 communities**, including **50 municipalities** and **11 Indigenous governments retained outside the municipal layer**. Among 48 municipalities with a published percentage, **32 were below forecast and 16 at/above**. Two terminated agreements are excluded from that denominator.

[PNG](haf_ontario_map.png) · [Interactive map](haf_ontario_map.html) · [Detailed findings](haf_map_findings.md)

The reference period is CMHC's annual reviews **up to March 2026**: second reviews of 2023-intake agreements and first reviews of 2024-intake agreements. It is not a common January–September 2026 reporting window.

## Corrections to the initial brief

| Initial claim | Required distinction |
|---|---|
| US$4.4 billion distributed | Use Canadian dollars. Budget authority, signed funding, advances and actual spending differ. |
| 241 local governments received money | Official sources reported 241 signed agreements. Active cohorts change with cancellations; the March 2026 report identifies 238 current agreements. Signed agreements do not prove cash receipt. |
| Growth above 1.1% | Application material also requires a minimum 10% increase in projected annual average growth; this is relative growth, not ten percentage points. Agreement versions and approved exceptions matter. |
| Accelerating permits | Permitted housing units, permit-document counts and processing time are different indicators. |
| 2026 outcome comparison | The inspected StatCan release covers September 2026, published November 12; compare January–September in both years. |
| BFF originated in Bill 17 | BFF launched August 21, 2023. Bill 17 is 2025 legislation, not the origin of BFF's 80% threshold. |

Sources: [HAF large/urban stream](https://www.cmhc-schl.gc.ca/professionals/project-funding-and-mortgage-financing/funding-programs/all-funding-programs/housing-accelerator-fund/housing-accelerator-fund-large-urban), [241 agreements](https://housing-infrastructure.canada.ca/pd-dp/parl/2025/06/cow/cow-b-eng.html), [March 2026 report](https://housing-infrastructure.canada.ca/housing-logement/ptch-csd/reports-rapports/prog-nhs-mar-2026-mar-snl-eng.html), [application highlight sheet](https://assets.cmhc-schl.gc.ca/sites/cmhc/professional/project-funding-and-mortgage-financing/funding-programs/all-funding-programs/housing-accelerator-fund/haf-highlight-sheet-en.pdf), [BFF launch](https://news.ontario.ca/en/release/1003397/to-build-more-homes-ontario-launching-building-faster-fund-and-expanding-strong-mayor-powers), [Bill 17](https://www.ontario.ca/laws/statute/s25009).

## StatCan source test

WDS `getCubeMetadata` was called with `[{"productId":34100292}]`. Table **34-10-0292-01**, Building permits by type of structure and work, covered January 2018–September 2026 in the snapshot. Its geography dimension had **66 members**: Canada, provinces/territories, CMAs, CAs and CMA parts, without a published CSD dimension.

Toronto's code **535** refers to its metropolitan area. Oakville and Mississauga were not individual geographic members. Variables distinguish permit value, created/lost/demolished units and permit-document counts. Only metadata were archived at this stage, not municipal outcome estimates.

Snapshot: `data/raw/statcan/34100292_metadata.json`; coverage: `data/processed/statcan_permits_coverage.json`. The manifest includes POST method/body, retrieval time and SHA-256. [WDS documentation](https://www.statcan.gc.ca/en/developers/wds/user-guide) · [Table](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3410029201)

This limitation does not establish that no municipal extract exists elsewhere. It prevents an automatic municipal interpretation of the inspected regional table.

## Different questions need different calculations

**Observed growth:** compare net residential units permitted in matching municipal geography and January–September windows. Report absolute and relative changes; a zero base makes percentage change undefined. Verify whether the series is already net before subtracting demolitions twice.

**Agreement progress:** divide eligible permitted units by the forecast for the agreement's reporting period, which may follow the signing anniversary. Do not distribute a three-year target evenly by month without a contractual forecast.

Application growth parameters based on projected stock and baselines are not proved by a simple 2025-to-2026 increase. Observed changes also do not identify causal funding effects.

## Future expansion

Keep agreement cohorts, intake, dates, approved amounts and advances separate. Municipal reports can validate eligible net units and period targets; the regional StatCan series provides context. Publish coverage denominators, retain missing values and preserve Indigenous governments outside the municipal boundary layer.

Relevant independent context: [Parliamentary Budget Officer, July 2025 HAF update](https://www.pbo-dpb.ca/en/additional-analyses--analyses-complementaires/BLOG-2526-005--an-update-housing-accelerator-fund--point-fonds-accelerer-construction-logements). It is not used as a 2026 municipal-performance count.
