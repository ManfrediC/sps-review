# Stage 06 Follow-up Notes

- `8182` is currently linked to the wrong abstract in the local proceedings text. The 2026-04-27 stage-06 publish excludes it with `count_basis=source_linkage_exclusion`, `likely_sps_case_count=0`, and `count_manual_review_required=true`; recover the correct source PDF/abstract and rerun the paper from scratch before using any positive count.
- Create a dedicated later-stage deduplication script before final patient-level synthesis so overlapping patients or reused cohorts can be detected across papers and not counted multiple times.
