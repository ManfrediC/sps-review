# LangExtract OpenAI Pilot 10 Gold/PDF Discrepancy Evidence

Date: 2026-05-29

This note lists the OpenAI pilot fields where the manual gold value is
contradicted by the source/PDF, only partly supported, or not a directly
extractable positive fact. Exact spans are from the Stage 07 target-view JSONs,
which are the source texts used to build LangExtract examples. I also checked
the original PDFs for the high-impact conflicts and PDF-extraction concerns.

Related files:

- Span plan: `qa/validation/langextract_example_bootstrap/openai_pilot_10/gold_source_span_plan.csv`
- Long span plan: `qa/validation/langextract_example_bootstrap/openai_pilot_10/gold_source_span_plan_long.csv`
- OpenAI audit report: `doc/reports/langextract_openai_pilot10_gold_pdf_audit.md`
- LangExtract JSON: `examples/langextract_bootstrap/draft_langextract_examples_openai_pilot10_all_gold.json`

## Source Conflicts Or Partial Support

These rows should not be promoted as standard LangExtract examples unless the
manual gold value is corrected or a human reviewer adjudicates the coding rule.

| ID | Field | Manual gold | Exact source/PDF evidence | Audit decision |
|---|---|---|---|---|
| 537 | `antibody_status` | `GAD` | Stage 07 chars 3124-3204: `paraneoplastic panel which included anti-GAD antibodies; the result was negative`. Liteparse recovered the same PDF evidence; `pypdf` extracted too little text from this PDF to find it. | Contradicted. The patient appears anti-GAD negative, not GAD positive. |
| 537 | `other_treatment` | `resection and chemotherapy of thymoma with complete resolution of neurological symptoms` | Stage 07 chars 2129-2173: `an initial surgical treat- ment was deferred`; chars 2223-2253: `four-drug-regimen chemotherapy`; chars 3590-3638: `complete radiographic resolution of his thymoma`. | Partly supported. Chemotherapy and radiographic resolution are supported; resection is not supported by the audited source span. |
| 554 | `age_description` | `32` | Stage 07 chars 18-56: `A 41-year-old female patient presented`. | Contradicted. Source age is 41. |
| 554 | `age_onset` | `30` | Stage 07 chars 18-56: `A 41-year-old female patient presented`; chars 282-344: `beginning 7 years prior to admission with a progressive course`. | Contradicted or at least unsupported. The source implies onset around 34, not 30. |
| 554 | `FU_duration` | `24` | Stage 07 chars 2601-2656: `The effect of the treatment has lasted for about 1 year`. | Contradicted. Source follow-up/treatment effect is about 12 months, not 24. |
| 554 | `immunotherapy` | `steroids;IVIG;RXB` | Stage 07 chars 1551-1578: `we decided to try rituximab`; chars 2927-2954: `rituximab (dose 375 mg/m 2)`. The text discusses plasma exchange and hyperimmune globulin as literature options, not as treatment received by this patient. | Partly supported. Rituximab is supported; patient steroids/IVIG are not supported in the audited source text. |
| 554 | `immuntherapy_detail` | `steroids, IVIG: partial improvement. Rituximab 1000mg with improvement of stiffness and spasms, persistence of improvement for 3 months.` | Stage 07 chars 2927-2954: `rituximab (dose 375 mg/m 2)`; chars 2601-2656: `The effect of the treatment has lasted for about 1 year`. | Contradicted. Dose and duration conflict with source, and steroids/IVIG are not supported as patient treatments. |
| 554 | `sympt_treatment` | `benzo;gabapentin;tizanidine` | Stage 07 chars 2817-2872: `still needs to use benzodiazepines as symptomatic drugs`; chars 1187-1249: `intravenous diazepam and application of botulinum toxin type A`. | Partly supported. Benzodiazepine/diazepam is supported; gabapentin and tizanidine are not supported by the audited spans. |
| 621 | `age_description` | `58` | Stage 07 chars 13-63: `A 46-year-old Japanese womanexperienced clumsiness`. The missing space is an OCR artefact; the PDF-derived text still states a 46-year-old woman. | Contradicted. Source age is 46. |
| 621 | `diagnosis_onset_other` | `spinocerebellar_ataxia` | Stage 07 chars 198-273: `Cerebellar ataxia was diagnosed because of her right upper extremity ataxia`; chars 2077-2138: `Gene analysis for familial ataxia (SCA1, 2, 3, 6, 8) found no`. | Over-specific or contradicted. Cerebellar ataxia is supported; spinocerebellar/familial ataxia is not. |
| 623 | `age_description` | `42` | Stage 07 chars 9-49: `We report a case of a 40-year-old female`. The same age appears in the original PDF table row as `Present 40 F SPS`. | Contradicted. Source age is 40. |
| 623 | `antibody_status` | `seronegative` | Stage 07 chars 312-426: `High levels of anti-glutamic acid decarboxylase GAD antibodies were detected in both serum and cerebrospinal fluid`; chars 3512-3531: `Anti-GAD antibodies`. The original PDF and liteparse output also show high anti-GAD antibody evidence. | Contradicted. The patient is anti-GAD positive in serum and CSF, not seronegative. |

## Context Or Absence-Only Rows

These rows may be valid spreadsheet codes, but they are not good positive
LangExtract examples because the evidence is absence, context, or lack of a
statement rather than a direct extractable fact.

| ID | Field | Manual gold | Exact source evidence | Audit decision |
|---|---|---|---|---|
| 524 | `ethnicity` | `white` | Stage 07 chars 16-63: `A previously healthy 67-year-old male presented`. | No patient ethnicity found. Do not promote. |
| 551 | `immunotherapy` | `none` | Stage 07 chars 2656-2771: `diaze- pam (now at 15 mg every 6 hours), baclofen (5 mg t.i.d.), and physical therapy consults had proven help- ful`. | Absence-coded. The passage lists symptomatic therapy, not an explicit no-immunotherapy statement. |
| 552 | `ethnicity` | `NA` | Stage 07 chars 0-85: `A 49-year-old male presented with progressively worsening muscle rigidity and spasms`. | Absence-coded. No ethnicity is stated. |
| 552 | `MRI_normal` | `NA` | Stage 07 chars 956-1040: `Findings from computerized tomographies of the head, chest, and abdomen were normal`. | Absence/context only. CT is normal; MRI is not reported in the audited span. |
| 623 | `ethnicity` | `E_asia` | Stage 07 chars 1130-1179: `A 40-year-old female clerical worker was admitted`. | Not directly stated. Japanese context may be inferential, but patient ethnicity is not explicit. |

## Rows Needing Human Adjudication

These rows have related evidence but should be reviewed against the field
codebook before promotion.

| ID | Field | Manual gold | Exact source evidence | Audit decision |
|---|---|---|---|---|
| 551 | `spasms_distribution_onset_multiple` | `distal_LE;lumb_prox_LE` | Stage 07 chars 419-490: `one tonic- clonic seizure episode (mainly in the lower left extremities`; chars 1179-1229: `onset of leg pain and falls over the last 6 months`. | Related lower-extremity evidence, but distal/proximal coding is not cleanly extractable. |
| 551 | `diagnosis_onset` | `functional` | Stage 07 chars 855-931: `concerns that the patient may be experienc- ing psychogenic seizure episodes`; chars 3266-3287: `con- version disorder`. | Related psychiatric/functional framing, but coding timing needs adjudication. |
| 551 | `spasms_distribution_established_multiple` | `distal_LE;lumb_prox_LE` | Stage 07 chars 960-1002: `spells, kicking his legs on the bed boards`; chars 419-490: `one tonic- clonic seizure episode (mainly in the lower left extremities`. | Related lower-extremity evidence, but the exact distribution categories need review. |
| 615 | `excessive_startle_onset` | `unspecified` | Stage 07 chars 158-217: `Symptoms were amplified by emotional upset or when startled`. | Startle sensitivity is supported, but the `unspecified` coding needs rule review. |
| 615 | `timecourse_onset` | `insidious` | Stage 07 chars 0-92: `In January 1998 a 85-year- old woman complained of sustained involuntary muscle contractions`. | Onset is described, but "insidious" is not directly stated. |
| 615 | `timecourse_subsequent` | `monophasic` | Stage 07 chars 2410-2478: `Treatment was continued successfully with low-dose prednisone orally`; chars 2514-2551: `patient remained symp- tom free since`. | Possibly compatible, but monophasic course is an inferred code. |
| 615 | `excessive_startle_established` | `unspecified` | Stage 07 chars 158-217: `Symptoms were amplified by emotional upset or when startled`. | Startle sensitivity is supported, but the `unspecified` coding needs rule review. |

## PDF Extraction Notes

ID `537`: `pypdf` produced only 647 characters and missed the anti-GAD negative
and treatment passages. Liteparse produced 43,238 characters and recovered the
anti-GAD negative passage, chemotherapy wording, and the literature-review table,
but with noisy column interleaving. This makes liteparse useful for locating
evidence in this PDF, not sufficient for structured table extraction.

ID `623`: `pypdf` and liteparse both found the table-like row containing
`Present 40 F SPS ... steroid pulse ... immunoadsorption ... thymectomy ...
radiation`. Liteparse produced more text and slightly cleaner OCR around
anti-GAD and thymoma, but both tools flattened the table; neither preserved
reliable row/column structure.

These observations support using liteparse as a fallback search/extraction aid
for difficult PDFs. They do not change the promotion rule: LangExtract examples
should still use exact reviewed source spans, and table-derived values should be
manually checked.
