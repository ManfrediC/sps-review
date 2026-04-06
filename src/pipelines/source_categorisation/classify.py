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

DEFAULT_MODEL = "gpt-5.4"
DEFAULT_TEMPERATURE = 0
DEFAULT_MAX_OUTPUT_TOKENS = 2048

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You classify papers for a systematic review of Stiff person spectrum disorder (SPSD).

SPSD includes Classic Stiff person syndrome (SPS), Stiff-limb syndrome (SLS), SPS-plus, progressive encephalomyelitis with rigidity and myoclonus (PERM), and focal or segmental SPS.

Use metadata and extracted text together. Return JSON matching the schema.

Determine:
- `source_type`
- `original_sps_spectrum_data`
- `contains_individual_level_data`
- `contains_group_level_data`
- `likely_sps_case_count`
- confidence and review flags

Categories:
- `conference_abstract`: meeting/proceedings/supplement abstract; use supplement issue, short page span, DOI supplement markers, proceedings flag, or very short text.
- `review_article`: synthesises prior literature without clinically useful original SPSD patient data.
- `single_case_report`: main original clinical content is 1 SPSD patient.
- `case_series_or_multi_case`: 2+ original SPSD patients with patient-level, case-by-case, or otherwise individually linkable reporting.
- `observational_group_study`: original grouped clinical data from a non-interventional design such as retrospective, prospective, registry, or cohort work.
- `interventional_study`: original grouped clinical data from a deliberate trial or controlled therapeutic design.
- `lab_heavy_clinical_or_translational`: primarily assay, biomarker, immunology, electrophysiology, or translational work that still includes clinically useful original SPSD human data.
- `non_clinical_basic_science`: mechanistic or laboratory work without clinically useful original SPSD human data.
- `unclear_manual_review`: evidence is insufficient or genuinely ambiguous.

Rules:
- Prefer `unclear_manual_review` over a forced guess. Never output `incorrect_reference`.
- Distinguish original patient data from discussion of prior literature.
- Distinguish conference abstracts from short full articles using metadata and proceedings signals.
- For translational papers, classify by the primary content, not by incidental mention of one patient.
- Observational treatment reports are not interventional unless there is a deliberate trial or controlled intervention design.

Original data:
- `yes`: original SPSD patient data are reported in this paper.
- `no`: no original SPSD patient data are reported.
- `unclear`: this cannot be decided safely.

Granularity:
- `contains_individual_level_data=true` when features or outcomes can be linked to specific patients.
- `contains_group_level_data=true` when the paper reports aggregated cohort-level or subgroup-level results.
- If both forms are present, set both booleans to `true`.
- Set both booleans to `false` only when there is no original SPSD patient data or the evidence is too unclear.

Counting:
- Count only unique original SPSD patients in this paper.
- Do not count cited-literature patients, controls, non-SPSD cohorts unless the SPSD subset is explicit, assay/specimen/serum/CSF/biopsy/sample counts, repeated specimens, repeated visits, overlapping subgroup totals, or large administrative datasets that are not extractable SPSD case reports or cohorts.
- `review_article` and `non_clinical_basic_science` usually have count `0`.
- If a mixed cohort clearly includes only one SPSD patient, return `1`.
- If the exact count is uncertain, give the best estimate, lower `count_confidence`, and set `count_manual_review_required=true`.

Evidence and brevity:
- Support every decision with evidence from this paper, not cited-literature summaries.
- High confidence requires at least 2 evidence items.
- Use the minimum evidence needed: usually 1 item, or 2 for high confidence; use more only if essential.
- Keep `reasoning_summary` and `count_reasoning_summary` brief and information-dense, ideally 1-2 short sentences each.\
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
