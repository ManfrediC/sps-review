# LangExtract Pilot 10 Gold And PDF Audit

Generated: 2026-05-29

## Scope

This report audits the 10 Gemini-generated LangExtract bootstrap examples in:

- `qa/validation/langextract_example_bootstrap/pilot_10/field_candidates.jsonl`
- `qa/validation/langextract_example_bootstrap/pilot_10/field_review.csv`
- `qa/validation/langextract_example_bootstrap/pilot_10/selected_rows.csv`

The comparison sources were:

- Manual gold standard: `examples/datasheet_examples_MC_Case_Report_Form.csv`
- Stage 07 target-view text: `qa/validation/stage07_single_case_codex_gold/.../target_views/{paper_id}/p1.json`
- Original PDFs: `data/pdf_original/*.pdf`, linked through `data/references/pdf_source_registry.csv`
- Page-indexed PDF text: `data/extraction_json/text/{paper_id}.json`

The original PDFs were present and text-extractable for all 10 records. I used direct `pypdf` extraction to verify that the PDF files are readable, and the existing page-indexed PDF text JSONs for page-level source passages. This is a text-level PDF audit, not a visual image/OCR audit.

## Assessment Definitions

- **Ready as-is** means the generated row preserves the gold value and has a source span that the validator accepted.
- **Repairable** means the gold value appears supported by the PDF, but the generated evidence is not yet suitable for a LangExtract example because the span is stitched, paraphrased, missing supporting snippets, affected by line-break or ligature differences, or otherwise not an exact reusable source span.
- **Adjudicate / do not promote** means the row exposes a probable gold/PDF conflict, a model value change, an unsupported absence-coded value, or a clinical inference that is too indirect to use as a training example without human correction.

The important distinction is that a clinically reasonable value is not automatically a good LangExtract example. LangExtract examples need exact, reviewable source text.

## Overall Findings

The 10-case pilot is useful as a review pack, but none of the 10 full examples should be promoted as a complete example without edits. There are usable individual rows, but every paper has either technical span failures, inferred fields that need exact supporting snippets, or at least one gold/PDF adjudication issue.

Across all 269 generated field rows:

| Metric | Count |
|---|---:|
| Total field rows | 269 |
| Model value exactly preserved the spreadsheet value | 268 |
| Model changed the spreadsheet value | 1 |
| `exact_quote` rows | 124 |
| `inferred_from_text` rows | 129 |
| `not_found` rows | 16 |
| Empty `extraction_text` rows | 37 |
| Validator `passed` rows | 45 |

Validator status distribution:

| Validator status | Count |
|---|---:|
| `passed` | 45 |
| `quote_not_found` | 80 |
| `inference_anchor_not_found` | 100 |
| `inference_snippet_not_found` | 23 |
| `inference_missing_supporting_snippets` | 4 |
| `needs_review` | 15 |
| `manual_value_changed` | 1 |
| `not_found_supports_manual_value_conflict` | 1 |

The dominant failure is not that Gemini changed gold values. The dominant failure is that Gemini often supplied evidence that is clinically relevant but not a valid exact source span. It also sometimes stitched non-contiguous passages with ellipses, relied on absence as evidence, or exposed a likely mismatch between the manual gold value and the PDF.

## Exact Source Span Plan

I added a field-level span workpack that covers every gold value:

- `qa/validation/langextract_example_bootstrap/pilot_10/gold_source_span_plan.csv`
- `qa/validation/langextract_example_bootstrap/pilot_10/gold_source_span_plan_long.csv`

The field-level CSV has one row per gold field. The long CSV has one row per proposed source span, which is easier to inspect manually. Every proposed span is an exact substring of the Stage 07 target-view text that LangExtract will receive.

| Span plan metric | Count |
|---|---:|
| Gold field rows covered | 269 |
| Proposed source spans | 432 |
| Rows with at least one source span | 269 |
| Rows whose proposed spans exactly match Stage 07 text offsets | 269 |

Coverage quality:

| Coverage class | Count | Meaning |
|---|---:|---|
| `direct_exact_span_ready` | 45 | The generated row already had an exact accepted span. |
| `covered_by_repaired_exact_source_text` | 209 | The gold value is covered by repaired exact source text and needs human span review before promotion. |
| `needs_human_adjudication` | 8 | The value is covered by source text, but the coding judgement needs review. |
| `derived_value_needs_coding_rule` | 3 | The value is derived from source text, not literally stated. |
| `context_or_absence_only_not_direct_extraction` | 4 | The source gives only contextual or absence evidence, not a direct extraction. |

LangExtract recommendation:

| Recommendation | Count |
|---|---:|
| `candidate_for_promotion_after_spot_check` | 45 |
| `candidate_after_span_review` | 209 |
| `review_before_promoting` | 8 |
| `review_before_promoting_derived_value` | 3 |
| `do_not_promote_as_standard_langextract_example` | 4 |

The all-gold draft example file now splits overlapping or duplicate spans into
77 LangExtract-compatible example payloads from the 10 source documents. Strict
LangExtract prompt alignment was run with fuzzy matching disabled and lesser
matches disallowed: 432 extractions, 0 alignment issues, and 0 attribute type
errors.

For LangExtract best practice, the `extraction_text` should be the shortest exact original text that supports the field. The spreadsheet value should be kept as an attribute when it is a coded, normalised, semicolon-delimited, or derived value. If a value needs multiple non-contiguous pieces of original text, the long CSV proposes multiple exact spans rather than forcing a stitched quote.

## Source PDF Inventory

| ID | Study | PDF path | PDF pages |
|---:|---|---|---:|
| 75 | Kuhn 1995 | `data/pdf_original/75_Kuhn-1995-Stiff-man syndrome_ case report.pdf` | 4 |
| 92 | Dropcho 1996 | `data/pdf_original/92_Dropcho-1996-Antiamphiphysin antibodies with s.pdf` | 9 |
| 155 | Hummel 1998 | `data/pdf_original/155_Hummel-1998-Humoral and cellular immune parame.pdf` | 5 |
| 162 | Hirsch 1998 | `data/pdf_original/162_Hirsch Severe insulin resistance in a patient with type 1 diabetes and stiff-man syndrome treated with insulin lispro.pdf` | 6 |
| 187 | Khanlou 1999 | `data/pdf_original/187_Khanlou Long-term Remission of Refractory Stiff-Man Syndrome After Treatment With Intravenous Immunoglobulin.pdf` | 2 |
| 197 | Butler 2000 | `data/pdf_original/197_Butler Autoimmunity to Gephyrin in Stiff-Man Syndrome.pdf` | 6 |
| 395 | Tanaka 2005 | `data/pdf_original/395_Tanaka Stiff Man Syndrome With Thymoma.pdf` | 3 |
| 427 | LaSpada 2006 | `data/pdf_original/427_157-03-09_La_Spada.pdf` | 3 |
| 439 | Gutmann 2006 | `data/pdf_original/439_4270-Article Text-15286-1-10-20200722.pdf` | 3 |
| 512 | O'Sullivan 2009 | `data/pdf_original/512_O'Sullivan et al. - 2009 - A case of stiff-person syndrome, type 1 diabetes, .pdf` | 3 |

## Paper-Level Summary

| ID | Fields | Strictly passed | Main verdict |
|---:|---:|---:|---|
| 75 | 21 | 1 | Not correct as a full example. Many values are clinically plausible; onset timing remains ambiguous, and the startle trigger value has been corrected to remove noise. |
| 92 | 27 | 0 | Not correct as-is. Good Patient 3 source material, but no field passed technically; `age_description` is now corrected to 67 and CMUA still needs policy review. |
| 155 | 22 | 4 | Not correct as-is. Several core fields are repairable; antibody status is now corrected to `GAD;islet_cell` and immunotherapy to `steroids`. |
| 162 | 28 | 3 | Not correct as-is. Demographics pass; `onset_to_established` is now `NA`, while multiple titre fields remain derived rather than exact PDF text. |
| 187 | 18 | 6 | Best of the first half, but still not complete. Most values are supported; `MRI_normal=0` is supported because the codebook defines `0 = normal`. |
| 197 | 33 | 3 | Not correct as-is. Several source-supported rows need span repair; `time_to_diagnosis` is now corrected to 0.17 years. |
| 395 | 28 | 10 | Useful but not correct as full example. Many exact biomedical rows pass, and `age_description` is now corrected to 57. |
| 427 | 33 | 4 | Clinically rich but technically poor. Most inferred rows have empty extraction text and need exact snippet reconstruction. |
| 439 | 28 | 2 | Not correct as-is. The PDF supports many values, but OCR hyphenation breaks spans and `immunotherapy=none` is not a positive extractable fact. |
| 512 | 31 | 12 | Stronger than most, but still incomplete. Several rows pass; mRS and some inferred treatment/autoimmunity rows need repair or adjudication. |

## Detailed Audit By Example

### ID 75 - Kuhn 1995

Verdict: **not correct as a full example; partially repairable.**

Strictly ready as-is:

- `age_description`

Repairable fields where the gold value appears broadly supported but the example evidence needs exact span repair:

- `sex`, `ethnicity`
- `first_manifestation`, `spasms_distribution_onset`, `spasms_distribution_onset_multiple`
- `other_symptoms_onset`, `spasms_distribution_established`, `excessive_startle_established`
- `antibody_status`, `CSF_antibody`, `CMUA`
- `sympt_treatment`, `sympt_treatment_detail`, `sympt_treatment_effect`
- `autoimmunity`, `autoimmunity_specify`

Adjudicate / do not promote:

- `age_onset`, `time_to_diagnosis`, and `onset_to_established`: the paper contains multiple duration anchors. The abstract says a "two-year history"; the case narrative says similar symptoms over the "preceding year"; the medical record says symptoms "for about three years". The generated reasoning uses only the one-year anchor, so it is too fragile for a training example unless the gold rule is explicitly documented.
- Resolved correction: `excessive_startle_established_multipleother` is now `tactile;speaking`. The PDF says the episodes were triggered by opening the door, speaking, and tactile stimuli, "but not by loud noises."

Key PDF evidence checked:

- Page 1: "A 39-year-old black woman..."
- Page 1: "two-year history of right leg spasms and low back pain..."
- Page 2: "similar but less intense low back pains and severe right leg spasms over the preceding year."
- Page 2: "history of low back pain with spasms and right lower-extremity spasms for about three years."
- Page 2: "triggered by external stimuli ... opening the door, speaking, and tactile stimuli, but not by loud noises."
- Page 2: lumbar puncture for anti-GAD antibodies with a later positive result.

### ID 92 - Dropcho 1996, Patient 3

Verdict: **not correct as-is; source-rich but technically unusable without repair.**

Strictly ready as-is:

- None.

Repairable fields where the PDF appears to support the gold value but the generated span is not valid as an exact example:

- `age_onset`, `first_manifestation`, `first_manifestation_multiple`
- `stiffness_distribution_onset`, `other_symptoms_onset`
- `timecourse_onset`, `timecourse_subsequent`, `onset_to_established`
- `stiffness_distribution_established`, `stiffness_distribution_established_multiple`
- `other_symptoms_established`, `antibody_status`, `antibody_tests`, `antibody_testsystem`
- `CSF_status`, `tu_screening`, `tu_screening_abnormal`
- `immunotherapy`, `immuntherapy_detail`, `immunotherapy_effect`
- `sympt_treatment`, `sympt_treatment_detail`, `other_treatment`
- `autoimmunity_specify`, `notes`

Adjudicate / do not promote:

- Resolved correction: `age_description` is now `67`, matching the PDF statement that Patient 3 was a 67-year-old man in September 1993.
- `CMUA=0`: this is an absence-coded value. The source describes polyneuropathy and other neurophysiology, but not a positive extractable statement of absent CMUA. It should not be used as an example unless the absence rule is separately reviewed.

Key PDF evidence checked:

- Page 2: "Patient 3. In September 1993, a 67-year-old man developed confusion, symmetrical stiffness and myoclonus of both legs, and numbness of both feet."
- Page 2: over the next 6 weeks, rigidity spread to abdominal and thoracic muscles including diaphragm; respiratory difficulty developed.
- Page 2: "He was maintained on pancuronium, ventilatory support, and heavy sedation..."
- Page 2: subcarinal mass biopsy showed SCLC; intravenous IgG, prednisone, and cisplatin plus etoposide were given.
- Page 4: Patient 3's antibody titre fell by November 1994, when he was in complete remission from SCLC and had made a partial neurological recovery.

### ID 155 - Hummel 1998

Verdict: **not correct as-is; several strong rows, with the key gold conflicts now corrected.**

Strictly ready as-is:

- `age_description`
- `first_manifestation_multiple`
- `diagnostic_criteria`
- `stiffness_distribution_established`

Repairable fields:

- `sex`
- `included_diagnosis`
- `spasms_distribution_established`, `spasms_distribution_established_other`
- `excessive_startle_established`
- `CSF_status`, `CSF_antibody`, `CSF_antibody_titre`
- `CMUA`
- `immuntherapy_detail`
- `sympt_treatment`, `sympt_treatment_detail`, `sympt_treatment_effect`
- `autoimmunity_specify`, `notes`

Adjudicate / do not promote:

- `first_manifestation=multiple`: the paired field `first_manifestation_multiple=stiffness` only names stiffness. The PDF supports rigidity/stiffness, but the "multiple" summary value needs review.
- Resolved correction: `antibody_status` is now `GAD;islet_cell`. The source supports GAD and islet cell antibodies, while IA-2 antibodies were undetectable.
- Resolved correction: `immunotherapy` is now `steroids`. Prednisolone is supported; direct page-by-page PDF search found no IVIG/immunoglobulin treatment reference for this paper.

Key PDF evidence checked:

- Page 1 abstract: immune reactivity to GAD and IA-2 was studied.
- Page 1 abstract: raised GAD antibodies were detected; antibodies to IA-2 were undetectable; weak T-cell responses to GAD and IA-2 were seen.
- Page 2: 51-year-old man fulfilled Lorish criteria.
- Page 2: CSF cell count and protein were normal; GAD antibodies were not measured in CSF.
- Page 3: prednisolone regimen appears in the treatment figure/text.

### ID 162 - Hirsch 1998

Verdict: **not correct as-is; demographics are good, many derived fields are not example-safe.**

Strictly ready as-is:

- `age_description`
- `sex`
- `ethnicity`

Repairable fields:

- `first_manifestation`, `included_diagnosis`, `early_symptoms`
- `other_symptoms_onset`, `diagnosis_onset`
- `stiffness_distribution_established`, `stiffness_distribution_established_multiple`
- `other_symptoms_established`
- `antibody_status`, `antibody_units`, `antibody_tests`
- `CSF_antibody`
- `CMUA`
- `MRI_normal`
- `immunotherapy`
- `sympt_treatment`, `sympt_treatment_detail`, `sympt_treatment_effect`
- `autoimmunity`, `autoimmunity_specify`

Adjudicate / do not promote:

- `time_to_diagnosis=2.5`: Gemini correctly marked this as not found. The PDF does not provide a clean direct time-to-diagnosis statement matching 2.5.
- `stiffness_distribution_onset=axial`: the patient history is broader and does not clearly isolate axial onset.
- Resolved correction: `onset_to_established` is now `NA`. The PDF's "28 months" refers to glycaemic control after insulin lispro, not to SPS onset-to-established interval.
- `antibody_titre=3.513888889` and `CSF_antibody_titre=0.388888889`: the PDF gives titres as 1:5000 and 1:500. The decimal values are transformations, not extractable source text.
- `immunotherapy=none`: this may be true as an absence-coded gold value for SPS immunotherapy, but absence is not a positive extractable example.

Key PDF evidence checked:

- Page 1: "The patient is a 33-year-old Caucasian woman..."
- Page 3: summer 1994 abdominal pain, thought to be pancreatitis.
- Page 4: GAD65 serum end-point titre 1:5000 and CSF GAD65 end-point titre 1:500.
- Page 4: dramatic response to oral diazepam; EMG read as normal but confounded by diazepam and baclofen.
- Page 2: antimicrosomal antibodies positive at 1:40, supporting Hashimoto's thyroiditis.

### ID 187 - Khanlou 1999

Verdict: **mostly clinically supported, but not ready as a complete LangExtract example.**

Strictly ready as-is:

- `age_description`
- `sex`
- `time_to_diagnosis`
- `spasms_distribution_established`
- `spasms_distribution_established_multiple`
- `immunotherapy`

Repairable fields:

- `included_diagnosis`
- `stiffness_distribution_established`, `stiffness_distribution_established_multiple`
- `excessive_startle_established`, `excessive_startle_established_multipleother`
- `antibody_status`
- `CMUA`
- `immuntherapy_detail`, `immunotherapy_effect`
- `sympt_treatment`, `sympt_treatment_detail`

Additional coding note:

- `MRI_normal=0`: the source says magnetic resonance imaging of the head and spinal cord was normal. This supports the gold value because the column dictionary defines `0 = normal` and `1 = abnormal`.

Key PDF evidence checked:

- Page 1: "A 43-year-old man" with a 9-year history.
- Page 1: findings include back rigidity/stiffness, lordosis, difficulty ambulating, frequent spasms affecting both legs and neck.
- Page 1: MRI of head and spinal cord was normal.
- Page 1: serum anti-GAD antibody assay was positive.
- Page 1-2: diazepam and baclofen had limited benefit; IVIg led to complete resolution and durable remission.

### ID 197 - Butler 2000

Verdict: **not correct as-is; multiple adjudication flags.**

Strictly ready as-is:

- `age_description`
- `sex`
- `tu_screening_abnormal`

Repairable fields:

- `age_onset`
- `first_manifestation`, `first_manifestation_multiple`
- `included_diagnosis`
- `early_symptoms`, `overview_established`
- `stiffness_distribution_onset`, `stiffness_distribution_onset_multiple`
- `spasms_distribution_onset`
- `stiffness_distribution_established`, `stiffness_distribution_established_other`
- `spasms_distribution_established`
- `excessive_startle_established`, `excessive_startle_established_multipleother`
- `other_symptoms_established`
- `antibody_status`, `antibody_status_other`, `antibody_tests`, `antibody_testsystem`
- `CSF_status`, `CSF_antibody`
- `tu_screening`
- `sympt_treatment`, `sympt_treatment_effect`
- `other_treatment`

Adjudicate / do not promote:

- Resolved correction: `time_to_diagnosis` is now `0.17`, based on the PDF's 2-month history.
- `spasms_distribution_onset_multiple=axial;bulbar`: the source mentions face and both legs for cramps/spasms. Bulbar/face is supported; axial is not clearly supported by the cited source passage.
- `spasms_distribution_established=gerneralised`: the gold value itself contains a spelling error, and the generated evidence does not cleanly establish generalised spasms.
- `CMUA=1`: the PDF describes low-firing frequency of normal units at rest, but the candidate did not find a clear CMUA statement.
- `MRI_normal=0`: the PDF explicitly says brain, cervical, and lumbar MRIs were normal. This supports the gold value under the column dictionary coding of `0 = normal`.
- `sympt_treatment_detail`: this is the only value-change row in the pilot. The gold says "Both the stiffness spasms lessened..." while Gemini changed the value to "Both the stiffness spasms lessened..." with spacing normalisation in `model_spreadsheet_value`, and the source itself says "Both the stiffness and spasms lessened markedly..." The source likely exposes a gold typo, but the candidate cannot be promoted because it did not preserve the gold value exactly.

Key PDF evidence checked:

- Page 2: "A 58-year-old male... admitted in June of 1998 with a 2 month history..."
- Page 2: progressive gait disturbance, dysarthria, dysphagia due to muscle stiffness and spasms.
- Page 2: brain, cervical, and lumbar MRIs were normal.
- Page 2: CSF and serum contained high-titre autoantibodies directed against gephyrin.
- Page 2: oral diazepam 20 mg/day; stiffness and spasms lessened markedly; walking and speech improved.
- Page 2: mediastinal tumour was undifferentiated carcinoma of undetermined origin.

### ID 395 - Tanaka 2005

Verdict: **partly strong, but not correct as full example because of age and ethnicity issues.**

Strictly ready as-is:

- `sex`
- `included_diagnosis`
- `stiffness_distribution_onset`
- `excessive_startle_established`
- `antibody_status`
- `antibody_titre`
- `antibody_units`
- `immunotherapy`
- `sympt_treatment`
- `sympt_treatment_detail`

Repairable fields:

- `age_onset`
- `first_manifestation`
- `early_symptoms`, `overview_established`
- `timecourse_onset`, `timecourse_subsequent`
- `onset_to_established`
- `stiffness_distribution_established`, `stiffness_distribution_established_multiple`
- `spasms_distribution_established`
- `other_symptoms_established`
- `course_treatment`
- `antibody_tests`
- `exteroceptive_refl`
- `tu_screening`, `tu_screening_abnormal`

Adjudicate / do not promote:

- Resolved correction: `age_description` is now `57`, matching the PDF's repeated 57-year-old case description.
- `ethnicity=E_asia`: the PDF gives Japanese institutional context but does not state patient ethnicity. This is an inferred demographic category, not a text-grounded extraction.
- `onset_to_established=2`: the source describes symptoms beginning in the upper limbs and deteriorating into trunk/lower-limb stiffness 1 month after onset, then recurrence 1 month after surgery. The gold value may be defensible under a separate coding rule, but the candidate evidence does not make the rule clear.

Key PDF evidence checked:

- Page 1: "We treated a 57-year-old woman..."
- Page 1: symptoms began as tightness in upper limbs and deteriorated into trunk/lower-limb stiffness 1 month after onset.
- Page 1: serum anti-GAD antibody 16,800 U/mL.
- Page 2: chest CT showed anterior mediastinal tumour considered thymoma; pathology was lymphocytic type, WHO B1.
- Page 2: severe bulbar symptoms with ptosis/dysphagia; symptoms relieved after intravenous immunoglobulin.

### ID 427 - LaSpada 2006

Verdict: **clinically useful source, but generated example is technically poor.**

Strictly ready as-is:

- `age_description`
- `other_symptoms_onset`
- `antibody_titre`
- `antibody_units`

Repairable fields:

- Most remaining fields are likely repairable because the PDF contains relevant evidence, but Gemini frequently left `extraction_text` empty and put long evidence in `supporting_snippets_json`. The current validator flags 21 rows as `inference_snippet_not_found`, largely because snippets contain PDF ligatures, line-break artefacts, or are not exact contiguous spans.

Repairable fields include:

- `sex`, `age_onset`
- `first_manifestation`, `first_manifestation_multiple`
- `included_diagnosis`, `included_diagnosis_specify`
- `early_symptoms`
- `stiffness_distribution_onset`, `stiffness_distribution_onset_multiple`
- `spasms_distribution_onset`, `spasms_distribution_onset_multiple`
- `timecourse_subsequent`
- `excessive_startle_established`, `excessive_startle_established_multipleother`
- `antibody_status`, `antibody_status_other`, `antibody_tests`
- `CSF_status`, `CMUA`, `MRI_normal`
- `immunotherapy`, `immuntherapy_detail`, `immunotherapy_effect`
- `sympt_treatment`, `sympt_treatment_detail`, `sympt_treatment_effect`
- `autoimmunity`, `autoimmunity_specify`, `notes`

Adjudicate / do not promote:

- No single gold value stood out as clearly contradicted in the same way as IDs 75, 155, 197, 395, or 439. The reason this example fails is technical: it is not currently a LangExtract-ready example because most rows do not carry exact extractable spans.

Key PDF evidence checked:

- Page 1: 49-year-old housewife observed in September 2002.
- Page 1: two months of dorsiflexion weakness of the left foot and painful contraction involving abdominal/paravertebral muscles and proximal left lower limb.
- Page 1: left foot drop.
- Page 2: 10 mg oral diazepam three times daily led to no significant improvement.
- Page 2: total dose 2 g/kg IVIG over 5 days; dorsiflexion improved and conduction block resolved.
- Page 3: monthly IVIG plus diazepam, cyclosporine, baclofen, and sodium valproate reduced painful contractures.

### ID 439 - Gutmann 2006

Verdict: **not correct as-is; many spans need repair and at least one absence-coded field should not be promoted.**

Strictly ready as-is:

- `age_description`
- `sex`

Repairable fields:

- `age_onset`
- `first_manifestation`, `first_manifestation_multiple`
- `included_diagnosis`
- `early_symptoms`
- `stiffness_distribution_onset`, `stiffness_distribution_onset_multiple`
- `other_symptoms_onset`, `other_symptoms_onset_auto`
- `timecourse_onset`, `timecourse_subsequent`
- `stiffness_distribution_established`
- `other_symptoms_established`
- `antibody_status`, `antibody_tests`
- `CSF_status`
- `tu_screening`, `tu_screening_abnormal`
- `sympt_treatment`, `sympt_treatment_effect`
- `other_treatment`
- `autoimmunity`, `autoimmunity_specify`, `notes`

Adjudicate / do not promote:

- `immunotherapy=none`: this is an absence-coded field. The model marked `not_found` but also set `supports_manual_value=TRUE`, creating an internal conflict. It should not become a positive training example.
- `MRI_normal=0`: the source says lumbar puncture, cerebral angio-CT, and MRI were all normal. This supports the gold value under the column dictionary coding of `0 = normal`.
- `autoimmunity` and `autoimmunity_specify`: the candidate links these to gonarthritis and heterotopic ossification. That may be a coding decision, but it is not a clean direct autoimmune diagnosis in the source.

Key PDF evidence checked:

- Page 1: "A 55 year-old woman..."
- Page 1: three-day history of back pain and trunk stiffness.
- Page 1: progression to leg stiffness, dysphagia, respiratory insufficiency, intubation, and ventilation.
- Page 1: lumbar puncture, cerebral angio-CT, and MRI were all normal; anti-GM1 and anti-GAD were negative.
- Page 2: later CT-guided biopsy revealed classical nodular sclerosis Hodgkin lymphoma.
- Page 2: ABVD polychemotherapy for 8 cycles.

### ID 512 - O'Sullivan 2009

Verdict: **stronger than most, but not complete; several inferred rows need repair.**

Strictly ready as-is:

- `age_description`
- `sex`
- `first_manifestation_multiple`
- `included_diagnosis`
- `stiffness_distribution_onset`
- `other_symptoms_onset`
- `antibody_status_other`
- `antibody_titre`
- `antibody_units`
- `CSF_antibody`
- `CSF_antibody_titre`
- `sympt_treatment_detail`

Repairable fields:

- `age_onset`
- `first_manifestation`
- `timecourse_subsequent`, `onset_to_established`
- `stiffness_distribution_established`
- `spasms_distribution_established`
- `course_treatment`
- `antibody_status`, `antibody_tests`
- `CSF_status`
- `MRI_normal`
- `immunotherapy`, `immunotherapy_effect`
- `sympt_treatment`, `sympt_treatment_effect`
- `autoimmunity`, `autoimmunity_specify`
- `notes`

Adjudicate / do not promote:

- `established_mRS=5`: I found no mRS score in the PDF text. This is an inferred disability score and should not be used as a LangExtract example unless the coding rule and evidence are explicit.
- `MRI_normal=0`: the candidate cites "MRI scans of the brain and spinal cord were normal." This supports the gold value under the column dictionary coding of `0 = normal`.

Key PDF evidence checked:

- Page 1: 41-year-old man with fall and 4-week history of lower back stiffness and bilateral leg weakness.
- Page 1: serum anti-GAD positive at 105 U/ml.
- Page 2: CSF was acellular with normal protein but anti-GAD antibodies strongly positive at 61 U/ml.
- Page 2: diazepam infusion, plasmapheresis, and later IVIg to good clinical effect.
- Page 2: mycophenylate as immunomodulatory agent; symptoms improved greatly and he returned to work.

## Cross-Example Issues

### 1. Evidence spans are often not LangExtract-ready

Many rows use clinically sensible text but fail as examples because the evidence is not a contiguous exact span. Common problems:

- Multi-sentence stitched evidence in a single `extraction_text`.
- Ellipses joining non-contiguous passages.
- PDF line-break and hyphenation artefacts.
- Ligatures such as `fi`/`fl` represented differently across text layers.
- Inferred rows with no `supporting_snippets`.
- Empty `extraction_text` with long snippets instead.

These rows may still be useful for human review, but they should not be promoted without exact span repair.

### 2. Absence-coded values are poor examples

Rows such as `CMUA=0`, `immunotherapy=none`, and `established_mRS=5` are not straightforward text extractions. Some require absence-of-evidence or clinical scoring. These should either be excluded from LangExtract examples or represented only after an explicit, reviewed coding policy is added.

### 3. Discrepancy answers have been implemented

The seven pilot discrepancies documented in `langextract_pilot10_gold_pdf_discrepancies.md` have been applied to the manually reviewed case-report CSV, the span plans, and the regenerated all-gold LangExtract examples:

- ID 75: `excessive_startle_established_multipleother` is now `tactile;speaking`.
- ID 92: `age_description` is now `67`.
- ID 155: `antibody_status` is now `GAD;islet_cell`; `immunotherapy` is now `steroids`.
- ID 162: `onset_to_established` is now `NA`.
- ID 197: `time_to_diagnosis` is now `0.17`.
- ID 395: `age_description` is now `57`.

Remaining high-priority adjudication examples:

- ID 75: onset duration still has 1-year, 2-year, and 3-year anchors.
- ID 162: decimal titre values are derived from ratios.
- ID 197: `sympt_treatment_detail` exposes a likely typo in the manual gold text.

### 4. Prompting and validation should separate two questions

The current review pack mixes:

1. Is the gold value clinically supported by the article?
2. Is the generated evidence a valid exact LangExtract example?

Those are different gates. A future review sheet should have separate columns, for example:

- `gold_supported_by_pdf`
- `gold_needs_adjudication`
- `span_exact_in_stage07_text`
- `span_exact_in_pdf_text`
- `example_ready_for_langextract`

## Recommended Next Step

Do not promote `draft_langextract_examples.json` yet. Instead:

1. Use `gold_source_span_plan.csv` as the review worklist; it covers all 269 gold values.
2. Accept the 45 `direct_exact_span_ready` rows after a spot check.
3. Review the 199 `covered_by_repaired_exact_source_text` rows and replace the original model evidence with the proposed exact spans.
4. Adjudicate the 25 non-standard rows before promotion: conflicts, derived values, context-only values, and values needing a coding decision.
5. Re-run the promotion step only after `review_status=accepted` is set on rows that are both gold-correct and span-correct.

My judgement is that the pilot was successful as a stress test of the bootstrapping workflow, but not as a final example set. It surfaced exactly the problems the human review layer needs to catch before LangExtract training examples become canonical.

## Commands And Checks Used

Representative local checks:

```powershell
Import-Csv qa\validation\langextract_example_bootstrap\pilot_10\field_review.csv |
  Group-Object validator_status |
  Sort-Object Name |
  Select-Object Name,Count
```

```powershell
Import-Csv data\references\pdf_source_registry.csv |
  Where-Object { @('75','92','155','162','187','197','395','427','439','512') -contains $_.covidence_id } |
  Select-Object covidence_id,study,title,pdf_path_relative,download_status
```

```powershell
.\.venv\Scripts\python.exe -c "import pypdf; print(pypdf.__version__)"
```

Direct PDF text extraction was also run over all 10 source PDFs to confirm page counts and text readability.
