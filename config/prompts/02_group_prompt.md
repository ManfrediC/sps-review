Extract concise, evidence-grounded snippets about group-level (cohort/aggregate) data.

Return extraction classes:
- group_design: study design, sampling, setting, inclusion framework
- group_characteristics: sample size and aggregate demographics/diagnostic composition
- group_findings: aggregate clinical and investigation findings (counts, percentages, trends)
- group_treatment_outcomes: treatment exposure and aggregate response/outcome patterns
- group_limitations: study-level or cohort-level limitations and caveats

Rules:
- Extract only information explicitly stated in the text.
- Keep snippets short and literal when possible.
- Focus on aggregated data; avoid single-patient anecdotes unless explicitly summarised as cohort findings.
