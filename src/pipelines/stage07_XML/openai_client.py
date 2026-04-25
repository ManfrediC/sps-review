from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .core import PreparedSource, Target, source_blocks_payload

try:
    from openai import OpenAI
except ModuleNotFoundError:  # pragma: no cover - exercised when OpenAI is not installed
    OpenAI = None


SYSTEM_PROMPT = """\
You prepare source-backed Stage 07 span metadata for a systematic review of stiff person spectrum disorder.

Return JSON only. Do not rewrite the source text. Do not return XML.

For every useful segment, return paragraph block coordinates:
- block_id
- start_offset
- end_offset
- selected_text

The selected_text must exactly equal block_text[start_offset:end_offset].
Prefer coherent sentence or paragraph spans. Do not invent patients, groups, findings, or targets.
Use only declared target IDs unless an explicit source-backed group target is needed.
""".strip()


def build_user_payload(
    *,
    prepared_source: PreparedSource,
    targets: list[Target],
) -> dict[str, Any]:
    return {
        "paper_id": prepared_source.paper_id,
        "declared_targets": [
            {
                "id": target.target_id,
                "kind": target.target_kind,
                "label": target.label,
            }
            for target in targets
        ],
        "allowed_roles": [
            "patient_specific",
            "shared",
            "group_summary",
            "group_specific",
            "uncertain",
            "background",
        ],
        "blocks": source_blocks_payload(prepared_source.blocks),
        "required_output_shape": {
            "targets": [
                {
                    "id": "g2",
                    "kind": "group",
                    "label": "Only if explicitly source-backed",
                    "evidence": "Exact text justifying the extra group target",
                }
            ],
            "segments": [
                {
                    "targets": ["p1"],
                    "role": "patient_specific",
                    "confidence": "high",
                    "evidence": "Brief source-backed reason",
                    "spans": [
                        {
                            "block_id": "b0001",
                            "start_offset": 0,
                            "end_offset": 12,
                            "selected_text": "Exact source",
                        }
                    ],
                }
            ],
        },
    }


def annotate_with_openai(
    *,
    prepared_source: PreparedSource,
    targets: list[Target],
    model: str,
    api_key: str,
    trace_dir: Path | None = None,
    max_output_tokens: int = 8000,
) -> dict[str, Any]:
    if OpenAI is None:
        raise RuntimeError("The openai package is not installed.")
    user_payload = build_user_payload(prepared_source=prepared_source, targets=targets)
    if trace_dir is not None:
        trace_dir.mkdir(parents=True, exist_ok=True)
        (trace_dir / f"{prepared_source.paper_id}.request.json").write_text(
            json.dumps(
                {
                    "model": model,
                    "system_prompt": SYSTEM_PROMPT,
                    "user_payload": user_payload,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=model,
        store=False,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
        max_output_tokens=max_output_tokens,
    )
    output_text = getattr(response, "output_text", "")
    if trace_dir is not None:
        (trace_dir / f"{prepared_source.paper_id}.response.txt").write_text(
            output_text,
            encoding="utf-8",
        )
    return json.loads(output_text)

