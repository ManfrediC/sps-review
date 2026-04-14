from __future__ import annotations

import os

from openai import OpenAI

from src.pipelines.stage06_counting.models import CountCandidatePackage, LLMCountDecisionOutput
from src.pipelines.stage06_counting.prepare import format_candidate_package_for_llm


DEFAULT_MODEL = "gpt-5.4"
DEFAULT_TEMPERATURE = 0
DEFAULT_MAX_OUTPUT_TOKENS = 1600

SYSTEM_PROMPT = """\
You adjudicate extractable SPS-spectrum case counts for a systematic review.

The paper has already been routed into a fixed source category. Do not reclassify the paper.
If the source category is `unclear_manual_review`, treat that as uncertainty in the upstream routing rather than evidence that the paper has zero extractable cases.

Your task:
- inspect the review evidence pack first, then the ordered heuristic candidate package
- choose the best-supported candidate count when possible
- propose a bounded alternative only when the paper text contains explicit count evidence not captured by the candidate list
- otherwise require manual review

Count only unique original SPS-spectrum patients reported in this paper.

Do not count:
- cited-literature cases
- controls or non-SPSD participants unless the SPS subset is explicit
- samples, sera, CSF specimens, biopsies, assays, titres, visits, or repeated measurements
- overlapping subgroup totals
- administrative datasets that are not extractable case-level or cohort-level SPS counts

Subgroup handling:
- Separate the full cohort from the SPS-spectrum subset whenever the paper reports a broader antibody-positive or mixed-neurology cohort.
- If the package includes an explicit SPS-spectrum subgroup count, treat that as the safest upper bound unless the evidence clearly supports a different bounded alternative.
- If only some patients are explicitly labelled SPS/PERM/stiff-limb syndrome and others are only suggestive because of symptoms such as rigidity or spasms, require manual review rather than counting the whole cohort.
- Treat statements such as "only 1 patient had clinical rigidity" as uncertainty about SPS-spectrum membership, not proof that every reported patient qualifies.

Fixed-category handling:
- If the fixed source category is `review_article` or `non_clinical_basic_science`, prefer an exact zero-count candidate unless the supplied evidence clearly shows an original single-patient report within the paper itself.

Decision guidance:
- `candidate_exact`: one heuristic candidate is clearly best supported
- `bounded_alternative`: the evidence supports a different explicit count than every listed candidate
- `manual_review_required`: there is real unresolved ambiguity
- `unable_to_determine`: the provided evidence is too weak to resolve safely

Conservatism:
- Treat the candidate list as advisory, not authoritative.
- Prefer selecting a valid candidate over inventing a new number.
- Use `bounded_alternative` when the review evidence pack contains a clearer explicit count than any listed candidate.
- If the SPS-spectrum subset is ambiguous, prefer `manual_review_required` over a confident whole-cohort count.
- If confidence is not high, set `count_manual_review_required=true`.
- High confidence should usually have at least 2 evidence items.
- Return JSON only.
"""


def adjudicate_count_package(
    package: CountCandidatePackage,
    *,
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
    api_key: str | None = None,
) -> tuple[LLMCountDecisionOutput, str]:
    client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
    response = client.responses.parse(
        model=model,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        instructions=SYSTEM_PROMPT,
        input=[{"role": "user", "content": format_candidate_package_for_llm(package)}],
        text_format=LLMCountDecisionOutput,
    )
    parsed = response.output_parsed
    if parsed is None:
        raise ValueError(
            f"Structured output parsing returned None for paper {package.paper_id}. "
            f"Output text: {response.output_text!r}"
        )
    model_id = response.model or model
    return parsed, model_id
