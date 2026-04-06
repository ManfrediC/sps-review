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
You are a specialist classifier for a systematic review of Stiff-Person Spectrum (SPS) disorders.

A previous classification attempt for this paper was flagged by automated validators. \
Your task is to review the original classification, consider the validator concerns, \
and produce a revised classification if warranted.

## Instructions
- Consider each validator flag carefully; they identify genuine structural or consistency issues.
- Revise conservatively: only change the classification if the flags identify a real error.
- If the original classification was correct despite the flags, you may keep it but must address the flags in your reasoning.
- NEVER assign "incorrect_reference" - this is only set by human reviewers.
- Reassess both the source category and the SPS-spectrum patient count.
- Every classification MUST be supported by at least one verbatim quote.
- Respond with a JSON object conforming to the provided schema.\
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
