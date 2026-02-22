Extract concise, evidence-grounded snippets about individual-level (case-level) data.

Return extraction classes:
- individual_presentation: symptoms, signs, case phenotype, clinical course
- individual_diagnostics: antibodies, CSF, EMG/electrophysiology, MRI, diagnosis details
- individual_treatment: symptomatic or immunotherapy interventions at case level
- individual_outcome: individual response, disability trajectory, follow-up outcomes
- individual_limitations: case-level uncertainty, ambiguity, missing details

Rules:
- Extract only information explicitly stated in the text.
- Keep snippets short and literal when possible.
- Ignore aggregated cohort statistics in this pass.
