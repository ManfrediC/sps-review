from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.pipelines.source_categorisation.prepare import assemble_payload, format_payload_for_llm, load_text_json
from src.validation.stage04_model_benchmark import _shared as shared


TOKEN_REFERENCE_MODELS = (
    "gpt-4.1",
    "gpt-5.4",
    "gpt-5.4-mini",
    "gpt-5.4-nano",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze exact stage-04 benchmark payloads and record tiktoken prompt estimates."
    )
    parser.add_argument(
        "--benchmark-id",
        default=shared.DEFAULT_BENCHMARK_ID,
        help="Benchmark set identifier under qa/validation/source_categorisation/model_benchmark/.",
    )
    return parser.parse_args()


def serialise_payload(payload: Any, *, user_message: str) -> dict[str, Any]:
    return {
        "paper_id": payload.paper_id,
        "metadata": payload.metadata,
        "text_content": payload.text_content,
        "text_source": payload.text_source,
        "proceedings_detected": payload.proceedings_detected,
        "trim_status": payload.trim_status,
        "text_page_count": payload.text_page_count,
        "user_message": user_message,
    }


def payload_token_estimates(user_message: str) -> dict[str, int]:
    estimates: dict[str, int] = {}
    for model_name in TOKEN_REFERENCE_MODELS:
        key = shared.model_token_key(model_name)
        system_tokens = shared.token_count_for_text(shared.SYSTEM_PROMPT, model_name=model_name)
        user_tokens = shared.token_count_for_text(user_message, model_name=model_name)
        adjudication_system_tokens = shared.token_count_for_text(
            shared.ADJUDICATION_SYSTEM_PROMPT,
            model_name=model_name,
        )
        estimates[f"classify_system_tokens_{key}"] = system_tokens
        estimates[f"classify_user_tokens_{key}"] = user_tokens
        estimates[f"classify_total_tokens_{key}"] = system_tokens + user_tokens
        estimates[f"adjudication_system_tokens_{key}"] = adjudication_system_tokens
    return estimates


def main() -> None:
    args = parse_args()
    paths = shared.benchmark_paths(args.benchmark_id)
    benchmark_rows = shared.load_csv_rows(paths.benchmark_set_path)
    if not benchmark_rows:
        raise SystemExit("Benchmark set not found or empty. Run build_benchmark_set.py first.")

    source_rows, _ = shared.load_cached_stage04_outputs()
    trim_rows = shared.load_trim_rows()
    reference_rows = shared.load_csv_rows_by_id(
        shared.REPO_ROOT / "data" / "references" / "sps_references_export.csv",
        "Covidence",
    )

    summary_rows: list[dict[str, str]] = []
    total_estimates = {
        field: 0 for field in shared.frozen_payload_summary_fieldnames() if field.startswith("classify_")
    }

    for row in benchmark_rows:
        paper_id = (row.get("paper_id") or "").strip()
        reference_row = reference_rows.get(paper_id, {})
        cached_source_row = source_rows.get(paper_id, {})

        text_path = shared.resolved_repo_path(
            cached_source_row.get("text_json_path") or f"data/extraction_json/text/{paper_id}.json"
        )
        preferred_path = shared.resolved_repo_path(row.get("preferred_text_json_path") or text_path.as_posix())
        text_record = load_text_json(text_path)
        preferred_record = load_text_json(preferred_path) if preferred_path.exists() else None
        payload = assemble_payload(
            paper_id=paper_id,
            reference_row=reference_row,
            text_record=text_record,
            preferred_record=preferred_record,
            preferred_text_source=(row.get("preferred_text_source") or "full_text").strip(),
            trim_row=trim_rows.get(paper_id, {}),
        )
        user_message = format_payload_for_llm(payload)
        payload_dict = serialise_payload(payload, user_message=user_message)
        payload_path = paths.frozen_payload_dir / f"{paper_id}.json"
        shared.write_json(payload_path, payload_dict)

        token_estimates = payload_token_estimates(user_message)
        payload_sha256 = shared.json_sha256(payload_dict)
        summary_row: dict[str, str] = {
            "paper_id": paper_id,
            "payload_path": shared.relative_repo_path(payload_path),
            "payload_sha256": payload_sha256,
            "text_source": payload.text_source,
            "text_page_count": str(payload.text_page_count),
        }
        for field in shared.frozen_payload_summary_fieldnames():
            if field in summary_row:
                continue
            summary_row[field] = str(token_estimates.get(field, 0))
            if field in total_estimates:
                total_estimates[field] += token_estimates.get(field, 0)
        summary_rows.append(summary_row)

    shared.write_csv_rows(
        paths.frozen_payload_dir / "payload_summary.csv",
        summary_rows,
        shared.frozen_payload_summary_fieldnames(),
    )
    shared.write_json(
        paths.frozen_payload_manifest_path,
        {
            "benchmark_id": args.benchmark_id,
            "created_at_utc": shared.now_utc_iso(),
            "payload_count": len(summary_rows),
            "payloads": summary_rows,
            "total_classify_prompt_tokens": total_estimates,
        },
    )

    print(f"benchmark_id={args.benchmark_id}")
    print(f"frozen_payload_count={len(summary_rows)}")
    print(f"total_classify_prompt_tokens={json.dumps(total_estimates, ensure_ascii=False, sort_keys=True)}")
    print(
        "frozen_payload_manifest_path="
        f"{shared.relative_repo_path(paths.frozen_payload_manifest_path)}"
    )


if __name__ == "__main__":
    main()
