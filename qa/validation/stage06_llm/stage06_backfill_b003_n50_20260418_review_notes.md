# Stage 06 b003 Review Notes

- Combined QA CSV: `qa\validation\stage06_llm\stage06_backfill_b003_n50_20260418_combined.csv`
- Inspection pack: `qa\validation\stage06_llm\stage06_backfill_b003_n50_20260418_inspection.md`
- Per-paper comments: `qa\validation\stage06_llm\stage06_backfill_b003_n50_20260418_review_comments.csv`

## Outcome

- Reviewed papers: 50
- `llm_bounded_alternative`: 2
- `llm_candidate_exact`: 37
- `manual_review_override`: 11

## Model-Based Triage

- Likely clean on first pass: 464, 468, 474, 477, 485, 489, 493, 496, 497, 500, 502, 506, 510, 514, 517, 518, 522, 531, 534, 535, 537, 541, 544, 547, 552, 554, 565, 566, 571
- Likely user review candidates: 505, 512, 524, 526, 536, 551, 555, 568

## Resolved Manual Overrides

- `456 -> 2`: The extracted count was 2, and it is the likelier count because the paper reports two SPS subjects with separate PET findings for Subject 1 and Subject 2. The provenance-overlap flag may still matter for reuse, but the extractable SPS-spectrum count itself is 2.
- `460 -> 1`: The extracted count was 1, and it is the likelier count because this is a single-patient case report linking acute ataxia, Graves' disease, and SPS in one woman.
- `461 -> 1`: The extracted count was 1, and it is the likelier count because this is a single-case report. Even though the discussion questions SPS as the true cause, only one putative SPS-spectrum patient is described.
- `472 -> 20`: The extracted counts were 20 and 0. The likelier count is 20, because the abstract explicitly states that sera were derived from 20 well-characterised SPS patients and 20 controls; 0 only reflects an over-conservative lab-context fallback.
- `473 -> 1`: The extracted count was 1, and it is the likelier count because this is a single original PERM case report in an 81-year-old patient.
- `488 -> 5`: The extracted counts were 5 and 1. The likelier count is 5, because the paper explicitly studies serum and CSF from five SPS patients; the competing 1 is a table-row parsing artefact rather than the cohort denominator.
- `491 -> 22`: The extracted counts were 61, 22, and 4. The likelier extractable SPS-spectrum count is 22, because the paper reports 61 high-GAD patients overall, of whom 22 had SPS; the competing 4 is a narrower table suffix subgroup rather than the full SPS cohort.
- `499 -> 127`: The extracted counts were 621, 116, and 11. The likelier extractable SPS-spectrum count is 127, because the paper compares two SPS groups within the suspected referral cohort: 116 GAD-antibody-positive patients plus 11 amphiphysin-antibody-positive patients.
- `545 -> 7`: The extracted counts were 7 and 4. The likelier count is 7, because the study reports seven hGADAb-positive original patients overall, while 4 refers to a narrower subgroup.
- `548 -> 10`: The extracted counts were 10 and 0. The likelier count is 10, because the paper explicitly reports paired serum/CSF samples from ten SPS patients; 0 only reflects an over-conservative specimen-only fallback.
- `559 -> 3`: The extracted counts were 3 and 1. The likelier count is 3, because the paper explicitly describes three new GlyR-antibody patients with SPS-spectrum phenotypes; 1 reflects only a single-case signal within the larger case series.

## Priority Review Candidates

- `505`: Pipeline output: 1. Extracted counts seen: 1 (single_case_text_signal; source_single_case_default). GPT decision: candidate_exact; medium. Model rationale: The abstract explicitly states that the paper reports a single patient with stiff-three limbs syndrome, which is within the SPS spectrum. Although this supports a count of 1, the evidence pack flags original-cohort provenance uncertainty and the preferred text excerpt is contaminated by unrelated content, so human review is still warranted.
- `512`: Pipeline output: 1. Extracted counts seen: 1 (case_report_marker_single_case; source_single_case_default). GPT decision: candidate_exact; medium. Model rationale: This is a single-patient case report with explicit wording that the authors report one 41-year-old man with stiff-person syndrome. Although the diagnosis appears supported by the case description and anti-GAD positivity, the challenge flag indicates SPS-status uncertainty, so the safest resolution is the 1-case candidate with manual review retained.
- `524`: Pipeline output: 1. Extracted counts seen: 1 (single_case_text_signal; source_single_case_default). GPT decision: candidate_exact; medium. Model rationale: This paper reports a single original SPS-spectrum patient in a case report format. However, the text also states that this patient was previously reported as 'patient SPS 3 in the original reports,' so the extractable count is best taken as 1 with manual review required for provenance overlap.
- `526`: Pipeline output: 1. Extracted counts seen: 1 (source_single_case_default), 0 (no_reliable_count_signal). GPT decision: candidate_exact; medium. Model rationale: The paper explicitly describes one original patient presented as having features of stiff person syndrome, within a single-case report format. However, because the title and text indicate this is a mimic due to SCA1 rather than confirmed SPS-spectrum disease, and provenance uncertainty signals are present, the safest choice is the 1-case candidate with manual review retained.
- `536`: Pipeline output: 1. Extracted counts seen: 0 (lab_context_no_extractable_count), 1 (case_report_marker_single_case). GPT decision: candidate_exact; medium. Model rationale: The paper explicitly describes original longitudinal laboratory characterization in a single SPS patient: both the title and abstract state 'a patient with stiff-person syndrome' / 'the patient with SPS' followed over 46 months. This supports 1 unique extractable SPS-spectrum case, but manual review remains appropriate because provenance uncertainty flags are present and the study is highly lab-focused.
- `551`: Pipeline output: 1. Extracted counts seen: 1 (source_single_case_default), 0 (no_reliable_count_signal). GPT decision: candidate_exact; medium. Model rationale: The full text explicitly presents 'the following is a case description' and then describes one 51-year-old man with a neurologist diagnosis of stiff-man syndrome. This supports a single original SPS-spectrum patient, but confidence remains medium because the report is framed as a consultation letter and the diagnosis is reported via the treating neurologist rather than extensively re-established in the article.
- `555`: Pipeline output: 1. Extracted counts seen: 1 (case_report_marker_single_case; source_single_case_default; diagnosis_specific_patient_case_count). GPT decision: candidate_exact; medium. Model rationale: This paper is a single-patient case report with explicit diagnosis-supported wording for one woman found to have stiff-person syndrome. Candidate cand03 is the safest exact match because it is tied to the explicit SPS-specific patient count and already preserves manual review due to provenance uncertainty signals.
- `568`: Pipeline output: 1. Extracted counts seen: 1 (case_report_marker_single_case; source_single_case_default). GPT decision: candidate_exact; medium. Model rationale: The paper is framed as a single-patient case report and the full text explicitly describes clinical and postmortem findings from one SPS patient with diagnostic support. Because the evidence pack flags possible prior description/provenance uncertainty, the safest choice is the 1-case candidate with manual review retained.

## Assistant QA Notes

- Reviewed overrides have already been folded into the combined QA CSV and these notes.
- Populate the paired review-comments CSV during manual batch QA for the remaining review candidates.