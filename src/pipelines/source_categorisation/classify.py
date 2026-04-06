"""Stage 2: LLM-based source categorisation via OpenAI Structured Outputs.

Submits an assembled paper payload and returns a parsed
``LLMClassificationOutput`` conforming to the strict schema.
"""

from __future__ import annotations

import os

from openai import OpenAI

from src.pipelines.source_categorisation.models import LLMClassificationOutput
from src.pipelines.source_categorisation.prepare import PaperPayload, format_payload_for_llm

# ---------------------------------------------------------------------------
# Default configuration
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "gpt-4.1"
DEFAULT_TEMPERATURE = 0
DEFAULT_MAX_OUTPUT_TOKENS = 2048

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a specialist classifier for a systematic review of Stiff-Person Spectrum (SPS) disorders.

## Task
Determine BOTH:
1. the source category for the paper
2. the count of original extractable Stiff-Person Spectrum (SPS) patients reported in the paper

Use the metadata and extracted text together for both decisions.

## Categories

### conference_abstract
Conference, meeting, proceedings, poster, or supplement abstract.
**Key signals:** Published in a supplement or proceedings issue; short page span (1-2 pages); abstract word count ≤450; DOI contains supplement markers; labelled as poster, oral presentation, or meeting abstract.
**Important:** A paper published in a proceedings volume is a conference abstract even if it reads like a short article. Use metadata (supplement issue, short page span, proceedings detected flag) to distinguish from short full articles.

### review_article
Synthesises prior literature and does NOT provide clinically useful original SPS-spectrum patient data.
**Key signals:** Uses phrases like "systematic review", "literature review", "meta-analysis", "narrative review"; discusses multiple studies without reporting new patients.
**Important:** A paper that studies an original cohort of SPS patients is NOT a review article, even if it discusses prior literature extensively. Look for original patient data (demographics, clinical findings, outcomes) to distinguish.

### single_case_report
Main original clinical content is one individual SPS-spectrum patient.
**Key signals:** Reports demographics, presentation, workup, and outcomes for a single patient; uses phrases like "case report", "a case of", "we present a patient".
**Important:** A translational/immunology paper that mentions a single patient incidentally is NOT a case report — classify based on the primary content.

### case_series_or_multi_case
Multiple original patients with case-oriented or semi-individualised reporting.
**Key signals:** Presents 2+ patients with individual-level detail (e.g. case-by-case descriptions, tables with per-patient data).

### observational_group_study
Original grouped clinical data from a non-interventional design (retrospective, prospective, registry, cohort).
**Key signals:** Reports aggregate statistics on a group of SPS patients; uses study-design language like "retrospective", "cohort", "registry", "consecutive patients".
**Important:** Papers describing treatment outcomes in an observational (non-trial) setting are observational, not interventional. Only classify as interventional_study if there is a controlled trial design (randomised, placebo-controlled, crossover).

### interventional_study
Original grouped clinical data from a treatment, intervention, trial, or controlled therapeutic design.
**Key signals:** Randomised controlled trial, crossover trial, placebo-controlled study, dose-escalation study.
**Important:** Merely describing treatment outcomes (e.g. "patients were treated with IVIg") does NOT make a paper interventional. There must be a deliberate trial or controlled intervention design.

### lab_heavy_clinical_or_translational
Primarily assay, biomarker, immunology, or translational work, but still contains clinically relevant original SPS-spectrum human data.
**Key signals:** Focuses on antibody characterisation, epitope mapping, electrophysiology experiments, or other laboratory methods, but includes clinical data from SPS patients.

### non_clinical_basic_science
Primarily mechanistic or laboratory-based and does NOT provide clinically useful original SPS-spectrum patient data.
**Key signals:** Animal models, in-vitro experiments, purely molecular/genetic studies without human SPS patient data.

### unclear_manual_review
Cannot be safely classified from the available evidence. Use this when the evidence is genuinely ambiguous or insufficient.

## Decision policy
- Be conservative: prefer correct abstention (unclear_manual_review) over forced classification.
- Every classification MUST be supported by at least one verbatim quote from the paper.
- If confident, require at least 2 evidence items.
- The count must be an integer greater than or equal to 0.
- Count ONLY original SPS-spectrum patients in this paper.
- Do NOT count:
  - patients from cited prior literature
  - control patients
  - non-SPS disease cohorts unless the paper clearly states how many were SPS-spectrum
  - assay/sample counts that are not patient counts
  - large administrative datasets that are not extractable SPS case reports or cohorts
- If the paper is a review article or non-clinical basic science paper, the count is usually 0.
- If the paper describes a broad mixed cohort but only one SPS-spectrum patient, return 1.
- If the exact count is uncertain, provide your best estimate, lower `count_confidence`, and set `count_manual_review_required=true`.
- Distinguish clearly between:
  - Original patient data vs. discussion of prior literature (key for review_article vs. observational)
  - Individual-level vs. group-level reporting
  - Conference abstracts vs. short full articles (use metadata signals)
  - Hybrid translational papers (lab methods + clinical SPS data)

## Prohibited output
- NEVER assign the category "incorrect_reference" — this is only set by human reviewers.

## Output
Respond with a JSON object conforming to the provided schema.\
"""

# ---------------------------------------------------------------------------
# Classification function
# ---------------------------------------------------------------------------


def classify_paper(
    payload: PaperPayload,
    *,
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
    api_key: str | None = None,
) -> tuple[LLMClassificationOutput, str]:
    """Classify a single paper via the OpenAI Structured Outputs API.

    Returns
    -------
    tuple[LLMClassificationOutput, str]
        The parsed classification output and the model ID used.

    Raises
    ------
    openai.APIError
        On non-retryable API failures (after retry logic in the caller).
    """
    client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
    user_message = format_payload_for_llm(payload)

    response = client.responses.parse(
        model=model,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        instructions=SYSTEM_PROMPT,
        input=[{"role": "user", "content": user_message}],
        text_format=LLMClassificationOutput,
    )

    parsed = response.output_parsed
    if parsed is None:
        raise ValueError(
            f"Structured output parsing returned None for paper {payload.paper_id}. "
            f"Output text: {response.output_text!r}"
        )

    model_id = response.model or model
    return parsed, model_id
