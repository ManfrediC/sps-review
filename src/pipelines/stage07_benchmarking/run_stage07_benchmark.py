"""Offline Stage 07 XML benchmark runner.

The runner compares candidate Stage 07 behaviour with reviewed gold annotations
without making live LLM calls. It writes scratch Stage 07 outputs inside the
benchmark run directory only, then stores compact scores under the configured
QA evaluation root.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stage07_XML import core
from stage07_benchmarking.manifest import (
    DEFAULT_EVALUATION_ROOT,
    RUN_CONFIG_SCHEMA_VERSION,
    benchmark_paths,
    load_model_matrix,
    now_run_id,
    write_benchmark_artifacts,
)
from stage07_benchmarking.metrics import score_segments_payloads, summarise_paper_scores


DEFAULT_REVIEWED_GOLD_DIR = (
    core.REPO_ROOT
    / "qa"
    / "validation"
    / "stage07_xml"
    / "gold_standard"
    / "stage07_xml_live_test10_20260425"
    / "reviewed_annotations"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Offline Stage 07 XML benchmark against reviewed gold annotations."
    )
    parser.add_argument(
        "--reviewed-gold-dir",
        type=Path,
        default=DEFAULT_REVIEWED_GOLD_DIR,
        help="Directory containing reviewed {paper_id}.json annotations used as gold.",
    )
    parser.add_argument(
        "--candidate-annotation-dir",
        type=Path,
        default=None,
        help=(
            "Optional directory containing candidate {paper_id}.json annotations. "
            "If omitted, the current deterministic/no-model Stage 07 path is scored."
        ),
    )
    parser.add_argument(
        "--evaluation-root",
        type=Path,
        default=DEFAULT_EVALUATION_ROOT,
        help="Root for non-canonical benchmark artefacts.",
    )
    parser.add_argument("--run-id", default="", help="Optional benchmark run id.")
    parser.add_argument("--paper-id", action="append", default=[], help="Paper ID to score. Repeatable.")
    parser.add_argument(
        "--model-matrix",
        type=Path,
        default=None,
        help="Optional JSON model/config matrix to record with the run.",
    )
    parser.add_argument(
        "--max-block-chars",
        type=int,
        default=core.DEFAULT_MAX_BLOCK_CHARS,
        help="Maximum prepared source characters per paragraph block.",
    )
    return parser.parse_args()


def selected_paper_ids(reviewed_gold_dir: Path, requested_ids: list[str]) -> list[str]:
    """Return requested IDs or all reviewed gold IDs in paper-number order."""

    def sort_key(paper_id: str) -> tuple[int, int | str]:
        text = str(paper_id or "").strip()
        if text.isdigit():
            return (0, int(text))
        return (1, text)

    if requested_ids:
        return sorted({str(item).strip() for item in requested_ids if str(item).strip()}, key=sort_key)
    return sorted(
        (path.stem for path in reviewed_gold_dir.glob("*.json")),
        key=sort_key,
    )


def load_annotation_payload(path: Path, prepared_source: core.PreparedSource) -> dict[str, Any]:
    """Load either reviewed anchors or already-compiled span metadata.

    This lets the same benchmark path compare the current deterministic pipeline,
    reviewed gold, or a directory of saved candidate model responses.
    """

    payload = json.loads(path.read_text(encoding="utf-8"))
    if str(payload.get("stage07_reviewed_annotation_schema_version") or "").strip():
        return core.compile_reviewed_annotation_payload(
            reviewed_payload=payload,
            prepared_source=prepared_source,
        )
    if any("selections" in segment for segment in payload.get("segments") or []):
        return core.compile_reviewed_annotation_payload(
            reviewed_payload=payload,
            prepared_source=prepared_source,
        )
    return payload


def process_with_annotation(
    *,
    paper_id: str,
    annotation_payload: dict[str, Any] | None,
    output_root: Path,
    source_rows: dict[str, dict[str, str]],
    manual_rows: dict[str, dict[str, str]],
    stage06_rows: dict[str, dict[str, str]],
    max_block_chars: int,
) -> core.ProcessResult:
    """Run the normal Stage 07 compiler against one annotation payload.

    The benchmark scores post-validation Stage 07 outputs rather than raw
    annotations, so failures in target recovery, table trimming, readiness, and
    manual-review flags are all represented in the same shape used downstream.
    """

    paths = core.output_paths(output_root)
    prior = core.parse_stage06_prior(stage06_rows.get(paper_id, {}))
    source_path = core.resolve_source_json_path(
        paper_id=paper_id,
        source_row=source_rows.get(paper_id, {}),
        stage06_prior=prior,
    )
    return core.process_paper(
        paper_id=paper_id,
        source_row=source_rows.get(paper_id, {}),
        manual_row=manual_rows.get(paper_id, {}),
        stage06_row=stage06_rows.get(paper_id, {}),
        paths=paths,
        manifest_run_id="stage07_benchmark",
        annotation_model="offline",
        annotation_payload=annotation_payload,
        max_block_chars=max_block_chars,
    )


def benchmark_paper(
    *,
    paper_id: str,
    reviewed_gold_dir: Path,
    candidate_annotation_dir: Path | None,
    output_root: Path,
    source_rows: dict[str, dict[str, str]],
    manual_rows: dict[str, dict[str, str]],
    stage06_rows: dict[str, dict[str, str]],
    max_block_chars: int,
) -> dict[str, Any]:
    """Score one paper by compiling gold and candidate annotations side by side."""

    prior = core.parse_stage06_prior(stage06_rows.get(paper_id, {}))
    source_path = core.resolve_source_json_path(
        paper_id=paper_id,
        source_row=source_rows.get(paper_id, {}),
        stage06_prior=prior,
    )
    prepared_source = core.prepare_source(
        paper_id=paper_id,
        source_path=source_path,
        max_block_chars=max_block_chars,
    )
    gold_annotation = load_annotation_payload(reviewed_gold_dir / f"{paper_id}.json", prepared_source)
    candidate_annotation = None
    if candidate_annotation_dir is not None:
        candidate_path = candidate_annotation_dir / f"{paper_id}.json"
        if candidate_path.exists():
            candidate_annotation = load_annotation_payload(candidate_path, prepared_source)
    # Gold and candidate runs share the same scratch root. Filenames may overlap,
    # but the benchmark keeps the returned in-memory payloads and writes only the
    # final score artefacts for comparison.
    gold_result = process_with_annotation(
        paper_id=paper_id,
        annotation_payload=gold_annotation,
        output_root=output_root,
        source_rows=source_rows,
        manual_rows=manual_rows,
        stage06_rows=stage06_rows,
        max_block_chars=max_block_chars,
    )
    candidate_result = process_with_annotation(
        paper_id=paper_id,
        annotation_payload=candidate_annotation,
        output_root=output_root,
        source_rows=source_rows,
        manual_rows=manual_rows,
        stage06_rows=stage06_rows,
        max_block_chars=max_block_chars,
    )
    return score_segments_payloads(
        gold_payload=gold_result.segments_payload,
        predicted_payload=candidate_result.segments_payload,
        paper_id=paper_id,
        registry_row=candidate_result.registry_row,
    )


def main() -> None:
    args = parse_args()
    paper_ids = selected_paper_ids(args.reviewed_gold_dir, args.paper_id)
    if not paper_ids:
        raise SystemExit("No reviewed gold annotations matched the benchmark request.")

    run_id = args.run_id or now_run_id()
    paths = benchmark_paths(args.evaluation_root, run_id)
    # Scratch Stage 07 outputs are intentionally nested under this benchmark run.
    # They are non-canonical intermediates and should not be consumed by the main
    # pipeline or paper artefact registry.
    scratch_output_root = paths.run_dir / "scratch_stage07_xml"
    source_rows = core.load_csv_rows_by_id(core.SOURCE_CATEGORISATION_PATH, "paper_id")
    manual_rows = core.load_csv_rows_by_id(core.SOURCE_MANUAL_REVIEW_PATH, "paper_id")
    stage06_rows = core.load_csv_rows_by_id(core.SOURCE_CASE_COUNT_PATH, "paper_id")
    paper_scores = [
        benchmark_paper(
            paper_id=paper_id,
            reviewed_gold_dir=args.reviewed_gold_dir,
            candidate_annotation_dir=args.candidate_annotation_dir,
            output_root=scratch_output_root,
            source_rows=source_rows,
            manual_rows=manual_rows,
            stage06_rows=stage06_rows,
            max_block_chars=args.max_block_chars,
        )
        for paper_id in paper_ids
    ]
    summary = summarise_paper_scores(paper_scores)
    run_config = {
        "schema_version": RUN_CONFIG_SCHEMA_VERSION,
        "run_id": run_id,
        "reviewed_gold_dir": str(args.reviewed_gold_dir),
        "candidate_annotation_dir": str(args.candidate_annotation_dir or ""),
        "paper_ids": paper_ids,
        "max_block_chars": args.max_block_chars,
        "model_matrix": load_model_matrix(args.model_matrix),
        # This runner is intentionally offline. Future live benchmarks should
        # make paid execution explicit in a separate command path.
        "paid_api_calls": False,
    }
    write_benchmark_artifacts(
        paths=paths,
        run_config=run_config,
        paper_scores=paper_scores,
        summary=summary,
    )
    print(f"Wrote Stage 07 benchmark artefacts to {paths.run_dir}")


if __name__ == "__main__":
    main()
