"""Run-manifest and artefact writers for Stage 07 benchmarking.

All benchmark outputs are non-canonical validation artefacts. Keeping path
construction and writers in this module makes it harder for experiments to
spread into `data/`, `results/`, or new top-level directories.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_EVALUATION_ROOT = REPO_ROOT / "qa" / "validation" / "stage07_xml" / "evaluation"
MODEL_MATRIX_SCHEMA_VERSION = "stage07_benchmark_model_matrix_v1"
RUN_CONFIG_SCHEMA_VERSION = "stage07_benchmark_run_config_v1"


@dataclass(frozen=True)
class BenchmarkPaths:
    """All files written by a single benchmark run."""

    run_dir: Path
    config_path: Path
    paper_scores_path: Path
    summary_csv_path: Path
    summary_json_path: Path
    summary_md_path: Path


def now_run_id(prefix: str = "stage07_benchmark") -> str:
    """Return a sortable UTC run identifier."""

    return datetime.now(timezone.utc).strftime(f"%Y%m%dT%H%M%SZ_{prefix}")


def benchmark_paths(evaluation_root: Path, run_id: str) -> BenchmarkPaths:
    """Resolve the contained QA output layout for one run."""

    run_dir = evaluation_root / run_id
    return BenchmarkPaths(
        run_dir=run_dir,
        config_path=run_dir / "run_config.json",
        paper_scores_path=run_dir / "paper_scores.jsonl",
        summary_csv_path=run_dir / "paper_scores.csv",
        summary_json_path=run_dir / "summary.json",
        summary_md_path=run_dir / "summary.md",
    )


def ensure_benchmark_paths(paths: BenchmarkPaths) -> None:
    """Create the run directory without touching canonical output roots."""

    paths.run_dir.mkdir(parents=True, exist_ok=True)


def load_model_matrix(path: Path | None) -> list[dict[str, Any]]:
    """Load an optional provider/model matrix for provenance only.

    The first-pass benchmark runner is offline. This matrix records the intended
    model configurations for a later approved live run, but loading it never
    resolves API keys or performs provider calls.
    """

    if path is None:
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    configs = payload.get("configs") or payload.get("runs") or []
    if not isinstance(configs, list):
        raise ValueError("Model matrix must contain a list under 'configs' or 'runs'.")
    normalised: list[dict[str, Any]] = []
    for index, item in enumerate(configs, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Model matrix item {index} is not an object.")
        name = str(item.get("name") or "").strip()
        provider = str(item.get("provider") or "").strip()
        model = str(item.get("model") or "").strip()
        if not name or not provider or not model:
            raise ValueError(f"Model matrix item {index} needs name, provider, and model.")
        normalised.append(
            {
                "name": name,
                "provider": provider,
                "model": model,
                "reasoning_effort": str(item.get("reasoning_effort") or "").strip(),
                "max_output_tokens": item.get("max_output_tokens"),
                "strict_json_schema": item.get("strict_json_schema"),
                "notes": str(item.get("notes") or "").strip(),
            }
        )
    return normalised


def write_json(path: Path, payload: dict[str, Any] | list[dict[str, Any]]) -> None:
    """Write stable UTF-8 JSON with a trailing newline."""

    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write per-paper rows as deterministic JSON Lines."""

    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def write_paper_scores_csv(path: Path, paper_scores: list[dict[str, Any]]) -> None:
    """Write the compact table used for quick spreadsheet inspection."""

    fieldnames = [
        "paper_id",
        "precision",
        "recall",
        "f1",
        "predicted_chars",
        "gold_chars",
        "overlap_chars",
        "missing_targets",
        "extra_targets",
        "contamination_flags",
        "ready_for_langextract",
        "manual_review_reasons",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for score in paper_scores:
            micro = score.get("micro") or {}
            writer.writerow(
                {
                    "paper_id": score.get("paper_id", ""),
                    "precision": f"{float(micro.get('precision') or 0):.6f}",
                    "recall": f"{float(micro.get('recall') or 0):.6f}",
                    "f1": f"{float(micro.get('f1') or 0):.6f}",
                    "predicted_chars": micro.get("predicted_chars", 0),
                    "gold_chars": micro.get("gold_chars", 0),
                    "overlap_chars": micro.get("overlap_chars", 0),
                    "missing_targets": "|".join(score.get("missing_targets") or []),
                    "extra_targets": "|".join(score.get("extra_targets") or []),
                    "contamination_flags": "|".join(score.get("contamination_flags") or []),
                    "ready_for_langextract": score.get("ready_for_langextract", ""),
                    "manual_review_reasons": score.get("manual_review_reasons", ""),
                }
            )


def summary_markdown(summary: dict[str, Any]) -> str:
    """Render a small human-readable benchmark summary."""

    return (
        "# Stage 07 Benchmark Summary\n\n"
        f"- Papers: {summary.get('n_papers', 0)}\n"
        f"- Micro precision: {float(summary.get('micro_precision') or 0):.4f}\n"
        f"- Micro recall: {float(summary.get('micro_recall') or 0):.4f}\n"
        f"- Micro F1: {float(summary.get('micro_f1') or 0):.4f}\n"
        f"- Contaminated papers: {summary.get('n_contaminated_papers', 0)}\n"
        f"- Papers with missing targets: {summary.get('n_missing_target_papers', 0)}\n"
    )


def write_benchmark_artifacts(
    *,
    paths: BenchmarkPaths,
    run_config: dict[str, Any],
    paper_scores: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    """Write all benchmark artefacts into the run directory."""

    ensure_benchmark_paths(paths)
    write_json(paths.config_path, run_config)
    write_jsonl(paths.paper_scores_path, paper_scores)
    write_paper_scores_csv(paths.summary_csv_path, paper_scores)
    write_json(paths.summary_json_path, summary)
    paths.summary_md_path.write_text(summary_markdown(summary), encoding="utf-8")
