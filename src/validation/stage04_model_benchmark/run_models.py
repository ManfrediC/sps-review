from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.pipelines.source_categorisation.adjudicate import needs_adjudication
from src.pipelines.source_categorisation.controller import _adjudicate_with_retry, _classify_with_retry
from src.pipelines.source_categorisation.models import ClassificationResult, LLMClassificationOutput
from src.pipelines.source_categorisation.prepare import PaperPayload
from src.pipelines.source_categorisation.validate import Severity, apply_validator_effects, run_validators
from src.validation.stage04_model_benchmark import _shared as shared


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the stage-04 benchmark payloads through new models using the canonical schema and validator path."
    )
    parser.add_argument(
        "--benchmark-id",
        default=shared.DEFAULT_BENCHMARK_ID,
        help="Benchmark set identifier under qa/validation/source_categorisation/model_benchmark/.",
    )
    parser.add_argument(
        "--model",
        action="append",
        default=[],
        help="Model(s) to run. Repeatable. Defaults to gpt-5.4-mini, gpt-5.4, and gpt-5.4-nano.",
    )
    parser.add_argument(
        "--estimate-only",
        action="store_true",
        help="Report token estimates and pending-paper counts without calling the API.",
    )
    parser.add_argument(
        "--allow-paid-run",
        action="store_true",
        help="Explicit approval flag required before any benchmark API calls are made.",
    )
    parser.add_argument(
        "--allow-baseline-regeneration",
        action="store_true",
        help="Allow gpt-4.1 to be rerun on the frozen benchmark set instead of using cached outputs only.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-run papers even if a model output already exists for them.",
    )
    return parser.parse_args()


def parse_models(args: argparse.Namespace) -> list[str]:
    models = args.model or list(shared.RUNNABLE_MODELS)
    normalised = [model.strip() for model in models if model.strip()]
    if not normalised:
        raise SystemExit("No models selected.")
    if (
        shared.CACHED_BASELINE_MODEL in normalised
        and not args.allow_baseline_regeneration
    ):
        raise SystemExit(
            "gpt-4.1 is cached-only by default. Re-run with "
            "--allow-baseline-regeneration if you explicitly want fresh structured outputs."
        )
    unsupported = [model for model in normalised if model not in shared.BENCHMARK_MODELS]
    if unsupported:
        raise SystemExit(f"Unsupported benchmark model(s): {unsupported}")
    return normalised


def load_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def append_jsonl_row(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def payload_from_frozen_dict(payload_dict: dict[str, Any]) -> PaperPayload:
    return PaperPayload(
        paper_id=str(payload_dict.get("paper_id") or "").strip(),
        metadata=dict(payload_dict.get("metadata") or {}),
        text_content=str(payload_dict.get("text_content") or ""),
        text_source=str(payload_dict.get("text_source") or "full_text"),
        proceedings_detected=bool(payload_dict.get("proceedings_detected")),
        trim_status=str(payload_dict.get("trim_status") or ""),
        text_page_count=shared.parse_int(payload_dict.get("text_page_count"), default=0),
    )


def run_frozen_payload(
    payload: PaperPayload,
    *,
    model: str,
) -> dict[str, Any]:
    llm_output, model_id = _classify_with_retry(payload, model=model, api_key=None)
    initial_flags, initial_worst = run_validators(llm_output, payload)
    validated_output = apply_validator_effects(llm_output, initial_flags, initial_worst)

    adjudicated = False
    adjudicated_output: LLMClassificationOutput | None = None
    final_flags = list(initial_flags)
    if needs_adjudication(llm_output, initial_worst):
        adjudicated_output, model_id = _adjudicate_with_retry(
            payload,
            llm_output,
            initial_flags,
            model=model,
            api_key=None,
        )
        adjudicated = True
        adj_flags, adj_worst = run_validators(adjudicated_output, payload)
        final_flags = initial_flags + [f"ADJ:{flag}" for flag in adj_flags]
        final_output = apply_validator_effects(adjudicated_output, final_flags, adj_worst)
    else:
        final_output = validated_output

    result = ClassificationResult(
        paper_id=payload.paper_id,
        source_type=final_output.source_type,
        original_sps_spectrum_data=final_output.original_sps_spectrum_data,
        contains_individual_level_data=final_output.contains_individual_level_data,
        contains_group_level_data=final_output.contains_group_level_data,
        manual_review_required=final_output.manual_review_required,
        confidence=final_output.confidence,
        likely_sps_case_count=final_output.likely_sps_case_count,
        count_confidence=final_output.count_confidence,
        count_manual_review_required=final_output.count_manual_review_required,
        count_reasoning_summary=final_output.count_reasoning_summary,
        reasoning_summary=final_output.reasoning_summary,
        evidence=final_output.evidence,
        validator_flags=final_flags,
        classification_source="llm",
        model_id=model_id,
        adjudicated=adjudicated,
    )
    result.derive_routing_fields(
        proceedings_detected=payload.proceedings_detected,
        trim_status=payload.trim_status,
    )

    return {
        "paper_id": payload.paper_id,
        "model_name": model,
        "model_id": model_id,
        "adjudicated": adjudicated,
        "initial_validator_flags": initial_flags,
        "final_validator_flags": final_flags,
        "raw_output": llm_output.model_dump(mode="json"),
        "validated_output": validated_output.model_dump(mode="json"),
        "adjudicated_output": (
            adjudicated_output.model_dump(mode="json") if adjudicated_output is not None else None
        ),
        "result": result.model_dump(mode="json"),
    }


def estimate_run(
    *,
    benchmark_rows: list[dict[str, str]],
    summary_rows_by_id: dict[str, dict[str, str]],
    model_name: str,
    existing_paper_ids: set[str],
) -> dict[str, int]:
    key = shared.model_token_key(model_name)
    pending_rows = [
        row for row in benchmark_rows if (row.get("paper_id") or "").strip() not in existing_paper_ids
    ]
    total_tokens = sum(
        shared.parse_int(summary_rows_by_id[(row.get("paper_id") or "").strip()].get(f"classify_total_tokens_{key}"))
        for row in pending_rows
        if (row.get("paper_id") or "").strip() in summary_rows_by_id
    )
    return {
        "pending_papers": len(pending_rows),
        "estimated_classify_prompt_tokens": total_tokens,
    }


def main() -> None:
    args = parse_args()
    models = parse_models(args)
    paths = shared.benchmark_paths(args.benchmark_id)
    benchmark_rows = shared.load_csv_rows(paths.benchmark_set_path)
    if not benchmark_rows:
        raise SystemExit("Benchmark set not found or empty. Run build_benchmark_set.py first.")
    summary_rows_by_id = {
        (row.get("paper_id") or "").strip(): row
        for row in shared.load_csv_rows(paths.frozen_payload_dir / "payload_summary.csv")
    }
    if not summary_rows_by_id:
        raise SystemExit("Frozen payload summary not found. Run freeze_payloads.py first.")

    if args.estimate_only:
        for model_name in models:
            predictions_path = paths.model_output_root / model_name / "predictions.jsonl"
            existing_paper_ids = {
                str(row.get("paper_id") or "").strip()
                for row in load_jsonl_rows(predictions_path)
                if str(row.get("paper_id") or "").strip()
            }
            estimate = estimate_run(
                benchmark_rows=benchmark_rows,
                summary_rows_by_id=summary_rows_by_id,
                model_name=model_name,
                existing_paper_ids=existing_paper_ids,
            )
            print(
                f"{model_name}: pending_papers={estimate['pending_papers']} "
                f"estimated_classify_prompt_tokens={estimate['estimated_classify_prompt_tokens']}"
            )
        return

    if not args.allow_paid_run:
        raise SystemExit(
            "Refusing to start paid benchmark model calls without explicit approval. "
            "Re-run with --allow-paid-run after the user has approved the spend."
        )

    for model_name in models:
        predictions_path = paths.model_output_root / model_name / "predictions.jsonl"
        existing_rows = [] if args.overwrite else load_jsonl_rows(predictions_path)
        if args.overwrite and predictions_path.exists():
            predictions_path.unlink()
        existing_paper_ids = {
            str(row.get("paper_id") or "").strip() for row in existing_rows if str(row.get("paper_id") or "").strip()
        }
        pending_rows = [
            row for row in benchmark_rows if (row.get("paper_id") or "").strip() not in existing_paper_ids
        ]
        print(f"model={model_name} pending_papers={len(pending_rows)}")

        for index, row in enumerate(pending_rows, start=1):
            paper_id = (row.get("paper_id") or "").strip()
            payload_path = paths.frozen_payload_dir / f"{paper_id}.json"
            payload_dict = json.loads(payload_path.read_text(encoding="utf-8"))
            result_payload = run_frozen_payload(payload_from_frozen_dict(payload_dict), model=model_name)
            append_jsonl_row(
                predictions_path,
                {
                    "benchmark_id": args.benchmark_id,
                    "benchmark_role": (row.get("benchmark_role") or "").strip(),
                    "benchmark_bucket": (row.get("benchmark_bucket") or "").strip(),
                    "paper_id": paper_id,
                    "payload_sha256": (summary_rows_by_id.get(paper_id, {}).get("payload_sha256") or "").strip(),
                    "created_at_utc": shared.now_utc_iso(),
                    **result_payload,
                },
            )
            print(f"  [{index}/{len(pending_rows)}] {paper_id} -> {result_payload['result']['source_type']}")

        shared.write_json(
            paths.model_output_root / model_name / "progress.json",
            {
                "benchmark_id": args.benchmark_id,
                "model_name": model_name,
                "completed_papers": len(load_jsonl_rows(predictions_path)),
                "updated_at_utc": shared.now_utc_iso(),
            },
        )


if __name__ == "__main__":
    main()
