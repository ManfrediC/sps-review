"""Stage 4: Conditional adjudication via a second LLM call.

Triggered only when validators return a ``reject`` action and the original
LLM response was not already ``unclear_manual_review``.
"""

from __future__ import annotations

import json
import os

from openai import OpenAI

from src.pipelines.source_categorisation.classify import (
    DEFAULT_MAX_OUTPUT_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_TEMPERATURE,
)
from src.pipelines.source_categorisation.models import (
    LLMClassificationOutput,
    SourceCategory,
)
from src.pipelines.source_categorisation.prepare import PaperPayload, format_payload_for_llm


ADJUDICATION_SYSTEM_PROMPT = """\
You are a specialist classifier for a systematic review of Stiff person spectrum disorder (SPSD).

SPSD encompasses Classic Stiff person syndrome (SPS), Stiff-limb syndrome (SLS), SPS-plus, progressive encephalomyelitis with rigidity and myoclonus (PERM), and focal or segmental SPS.

Review the original paper payload, original classification, and validator flags, then return revised JSON matching the schema.

Reassess:
- `source_type`
- `original_sps_spectrum_data`
- `contains_individual_level_data`
- `contains_group_level_data`
- `likely_sps_case_count`
- confidence and review flags

Rules:
- Treat validator flags as consistency checks, not automatic proof that the original answer was wrong.
- Revise conservatively, but fix real inconsistencies.
- If the original answer is still correct, you may keep it, but the revised output must resolve or appropriately reflect the flagged issue.
- Never output `incorrect_reference`.
- Prefer `unclear_manual_review` over a forced guess.
- `contains_individual_level_data=true` when the paper links features to specific patients.
- `contains_group_level_data=true` when the paper reports aggregated cohort-level or subgroup-level results.
- If both forms are present, set both booleans to `true`.
- Set both booleans to `false` only when there is no original SPSD patient data or the evidence is too unclear to decide safely.
- Count only unique original SPSD patients reported in this paper.
- Do not count cited-literature patients, controls, non-SPSD cohorts unless the SPSD subset is explicit, sample counts, repeated specimens, repeated visits, or overlapping subgroup totals.
- If the exact count is uncertain, provide the best estimate, lower `count_confidence`, and set `count_manual_review_required=true`.
- Every classification must be supported by evidence from this paper.
- Provide evidence that supports the corrected category and, where available, the count or reporting granularity.
- High confidence requires at least 2 evidence items.
- Use the minimum evidence needed: usually 1 item, or 2 for high confidence; use more only if essential.
- Return only JSON conforming to the schema.
- Keep `reasoning_summary` and `count_reasoning_summary` concise.\
"""


def needs_adjudication(
    output: LLMClassificationOutput,
    worst_severity: int,
) -> bool:
    """Determine whether adjudication should be triggered."""
    if output.source_type == SourceCategory.unclear_manual_review:
        return False
    return worst_severity >= 3


def adjudicate_paper(
    payload: PaperPayload,
    original_output: LLMClassificationOutput,
    validator_flags: list[str],
    *,
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
    api_key: str | None = None,
) -> tuple[LLMClassificationOutput, str]:
    """Run a single adjudication call."""
    client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))

    paper_text = format_payload_for_llm(payload)
    original_json = original_output.model_dump_json(indent=2)

    user_message = (
        f"## Original paper\n\n{paper_text}\n\n"
        f"## Original classification\n\n```json\n{original_json}\n```\n\n"
        f"## Validator flags\n\n{json.dumps(validator_flags)}\n\n"
        "Please review the validator concerns and produce a revised classification."
    )

    response = client.responses.parse(
        model=model,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        instructions=ADJUDICATION_SYSTEM_PROMPT,
        input=[{"role": "user", "content": user_message}],
        text_format=LLMClassificationOutput,
    )

    parsed = response.output_parsed
    if parsed is None:
        raise ValueError(
            f"Adjudication parsing returned None for paper {payload.paper_id}. "
            f"Output text: {response.output_text!r}"
        )

    model_id = response.model or model
    return parsed, model_id
