# Funding research: volumes, requirements and allocations

Research snapshot: November 20, 2026. These historical cases compare provincial and federal criteria. Current BFF funding evidence is in [bff_2025_findings.md](bff_2025_findings.md); broader HAF permit performance is in [haf_map_findings.md](haf_map_findings.md).

## Program distinction

| Program | Relevant requirements | Evidence needed |
|---|---|---|
| Provincial BFF | At least 80% of annual official housing progress; bonuses and infrastructure-use conditions | Annual target/counts, confirmed allocation and separate payment evidence |
| Federal/CMHC HAF | Agreed reforms, action-plan commitments and permitted-unit targets | Agreement version, reporting period, reviews and documented decisions |
| Federal CHIF direct-delivery stream | February 2025 guide v1.3 includes four units as-of-right for provincial municipalities of 30,000+, and development-charge conditions for municipalities/regions of 300,000+, with approved alternatives | Population, applicable edition, project and accepted exceptions; the BFF CSV is insufficient |

Sources: [BFF tracker](https://www.ontario.ca/page/tracking-housing-supply-progress), [CMHC HAF explanation](https://www.cmhc-schl.gc.ca/media-newsroom/news-releases/2026/tracking-progress-housing-accelerator-fund), [CHIF guide](https://housing-infrastructure.canada.ca/housing-logement/chif-fcil/chif-applicant-guide-demandeur-fcil-eng.html).

CHIF requirements have not been applied to municipalities in this project. HAF's four-unit issue was central to the two cases below; it is not presented as the entirety of every agreement's requirements.

## Two selected contrasts

| Municipality | 2024 annual target | Official progress | Recalculated % | Provincial BFF award announced in 2025 | Historical HAF event in 2024 |
|---|---:|---:|---:|---:|---|
| Windsor | 1,083 | 2,306 | 212.93% | C$5.2 million | Application denied |
| Oakville | 2,750 | 3,679 | 133.78% | C$13.2 million | Participation ended in May |

The awards total **C$18.4 million**. They are selected documented cases, not a count of every Ontario municipality in this situation. Official announcements do not establish cash reconciliation.

**Windsor:** [provincial award announcement, August 12, 2025](https://news.ontario.ca/en/release/1006299/ontario-rewards-windsor-with-52-million-through-the-building-faster-fund). [Municipal report CM 9/2024](https://www.citywindsor.ca/documents/city-hall/city-council-meetings/Council%202024/07-22-2024/Consolidated%20Agenda.pdf), PDF page 53, item 7.7, describes the citywide federal four-unit condition versus Windsor's area-specific proposal. Council received denial correspondence on February 12, 2024; this is not necessarily the decision date.

**Oakville:** [provincial award announcement, September 24, 2025](https://news.ontario.ca/en/release/1006520/ontario_rewards_oakville_with_132nbspmillion_through_the_building_faster_fund). The [municipal September 2025 White Paper](https://www.oakville.ca/getmedia/c9396413-a287-42f8-b649-b5e568e5a454/planning-housing-planning-act-tools-development-affordable-housing.pdf), PDF page 15, section 2.1.3 and footnote 1, records participation ending in May 2024 and council opposition to permissions involving four units per lot and density near Sheridan College.

Official PDFs are archived in `data/raw/funding/`. An alternative Oakville eScribe download was blocked, so the accessible municipal White Paper is the primary case source.

## Other documented events

CMHC [announced reductions on January 16, 2026](https://www.cmhc-schl.gc.ca/media-newsroom/news-releases/2026/updates-housing-accelerator-fund-agreements): **C$10 million for Toronto and C$7.4 million for Vaughan**. The release does not identify each unmet obligation, so reductions are not automatically attributed to fourplexes. Their C$17.4 million total stays separate from Windsor/Oakville's BFF awards.

CMHC [cancelled Tecumseh's agreement on January 30, 2026](https://www.cmhc-schl.gc.ca/media-newsroom/news-releases/2026/update-housing-accelerator-fund-agreement-tecumseh), after identifying non-compliance in 2025. Tecumseh is outside the 50-municipality provincial table; its provincial fields remain unknown.

## Interpretation and reproducibility

The original 100% map measures full-target achievement. BFF's numeric funding threshold is **80%**, reached by **25/50 municipalities in 2024**. Meeting that threshold is not an audited allocation or payment decision.

High provincial housing progress does not establish approval or continued participation in a federal reform-based program. Preserve the distinct dates: the two main HAF events occurred in 2024; provincial awards for 2024 performance were announced in 2025. Do not net different programs or treat application denial as a quantified monetary cut.

`src.compare_funding` joins official provincial counts to reviewed case facts and keeps requested, reduced and announced amounts separate. `src.plot_funding` renders the two-case figure. Reviewed source locators and dates are in `data/reference/funding_cases.json`; tests verify coverage, thresholds and financial categories.

[Calculated case comparison](funding_comparison.md) · [Editorial figure](funding_contrast.png)
