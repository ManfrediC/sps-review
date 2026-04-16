from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import tiktoken

from src.pipelines.source_categorisation.adjudicate import ADJUDICATION_SYSTEM_PROMPT
from src.pipelines.source_categorisation.classify import SYSTEM_PROMPT
from src.validation import _stage04_gold as gold

REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_registry.csv"
COUNT_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "source_sps_case_count_registry.csv"
ARTIFACT_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "paper_artifact_registry.csv"
TRIM_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "text_trim_registry.csv"
MANUAL_REVIEW_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_manual_review.csv"
TEXT_DIR = REPO_ROOT / "data" / "extraction_json" / "text"
TEXT_TRIMMED_DIR = REPO_ROOT / "data" / "extraction_json" / "text_trimmed"
GOLD_MASTER_PATH = REPO_ROOT / "qa" / "validation" / "source_categorisation" / "gold_standard" / "04_categorisation_gold_standard.csv"
BENCHMARK_ROOT = REPO_ROOT / "qa" / "validation" / "source_categorisation" / "model_benchmark"

DEFAULT_BENCHMARK_ID = "mixed20_v1"
DEFAULT_BENCHMARK_SIZE = 20
DEFAULT_AMBIGUOUS_TARGET = 8

CACHED_BASELINE_MODEL = "gpt-4.1"
BENCHMARK_MODELS = (
    "gpt-4.1",
    "gpt-5.4-mini",
    "gpt-5.4",
    "gpt-5.4-nano",
)
RUNNABLE_MODELS = (
    "gpt-5.4-mini",
    "gpt-5.4",
    "gpt-5.4-nano",
)

CLEAR_CATEGORY_TARGETS = (
    ("clear_review", "review_article"),
    ("clear_review_embedded_original_cohort", "review_format_with_embedded_original_cohort"),
    ("clear_conference_abstract", "conference_abstract"),
    ("clear_single_case", "single_case_report"),
    ("clear_case_series", "case_series_or_multi_case"),
    ("clear_observational_group", "observational_group_study"),
    ("clear_lab_heavy", "lab_heavy_clinical_or_translational"),
    ("clear_basic_science", "non_clinical_basic_science"),
)
AMBIGUOUS_BUCKET_PREFIXES = (
    "conference_edge",
    "case_group_boundary",
    "review_lab_edge",
    "count_ambiguity",
)


@dataclass(frozen=True)
class BenchmarkPaths:
    benchmark_dir: Path
    benchmark_set_path: Path
    manifest_path: Path
    frozen_payload_dir: Path
    frozen_payload_manifest_path: Path
    model_output_root: Path
    report_root: Path


def benchmark_paths(benchmark_id: str) -> BenchmarkPaths:
    benchmark_dir = BENCHMARK_ROOT / benchmark_id
    return BenchmarkPaths(
        benchmark_dir=benchmark_dir,
        benchmark_set_path=benchmark_dir / "benchmark_set.csv",
        manifest_path=benchmark_dir / "benchmark_manifest.json",
        frozen_payload_dir=benchmark_dir / "frozen_payloads",
        frozen_payload_manifest_path=benchmark_dir / "frozen_payload_manifest.json",
        model_output_root=benchmark_dir / "model_outputs",
        report_root=benchmark_dir / "reports",
    )


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def truthy(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def parse_int(value: str | int | None, default: int = 0) -> int:
    try:
        return int(str(value or "").strip())
    except ValueError:
        return default


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_csv_rows_by_id(path: Path, key_column: str) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    for row in load_csv_rows(path):
        key = (row.get(key_column) or "").strip()
        if key:
            rows[key] = row
    return rows


def write_csv_rows(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict[str, Any] | list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def relative_repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path.resolve()).replace("\\", "/")


def resolved_repo_path(path_text: str) -> Path:
    path = Path(str(path_text or "").strip())
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def json_sha256(payload: dict[str, Any] | list[Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def token_encoding_for_model(model_name: str):
    try:
        return tiktoken.encoding_for_model(model_name)
    except KeyError:
        return tiktoken.get_encoding("o200k_base")


def token_count_for_text(text: str, *, model_name: str) -> int:
    encoding = token_encoding_for_model(model_name)
    return len(encoding.encode(text))


def benchmark_fieldnames() -> list[str]:
    return [
        "benchmark_id",
        "benchmark_role",
        "benchmark_bucket",
        "selection_priority",
        "selection_reason",
        "selection_created_at_utc",
        "source_round_id",
        "paper_id",
        "covidence_id",
        "title",
        "authors",
        "published_year",
        "journal",
        "selection_bucket",
        "selection_signals",
        "pdf_path_relative",
        "preferred_text_json_path",
        "preferred_text_source",
        "proceedings_detected",
        "trim_status",
        "gold_source_category",
        "gold_extractable_sps_case_count",
        "gold_original_sps_data",
        "gold_contains_individual_level_data",
        "gold_contains_group_level_data",
        "gold_ambiguity_tier",
        "gold_label_status",
        "gold_label_notes",
        "cached_gpt41_source_category",
        "cached_gpt41_source_subtype",
        "cached_gpt41_confidence",
        "cached_gpt41_likely_case_count",
        "cached_gpt41_contains_individual_level_data",
        "cached_gpt41_contains_group_level_data",
        "cached_gpt41_manual_review_required",
        "cached_gpt41_count_confidence",
        "cached_gpt41_count_manual_review_required",
        "cached_gpt41_original_sps_data",
        "cached_gpt41_evidence_available",
        "cached_gpt41_categorisation_reason",
        "cached_gpt41_count_reason",
    ]


def reviewed_gold_rows(path: Path = GOLD_MASTER_PATH) -> list[dict[str, str]]:
    return gold.reviewed_gold_rows_from_path(path)


def load_cached_stage04_outputs(
    *,
    source_registry_path: Path = SOURCE_REGISTRY_PATH,
    count_registry_path: Path = COUNT_REGISTRY_PATH,
) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    return (
        load_csv_rows_by_id(source_registry_path, "paper_id"),
        load_csv_rows_by_id(count_registry_path, "paper_id"),
    )


def load_artifact_rows(path: Path = ARTIFACT_REGISTRY_PATH) -> dict[str, dict[str, str]]:
    return load_csv_rows_by_id(path, "paper_id")


def load_trim_rows(path: Path = TRIM_REGISTRY_PATH) -> dict[str, dict[str, str]]:
    return load_csv_rows_by_id(path, "paper_id")


def infer_gold_original_data(category: str) -> str:
    if category in {"review_article", "non_clinical_basic_science"}:
        return "no"
    if category == "unclear_manual_review":
        return "unclear"
    return "yes"


def infer_gold_data_presence(
    *,
    category: str,
    cached_source_row: dict[str, str],
) -> tuple[str, str]:
    individual = (cached_source_row.get("contains_individual_level_data") or "").strip().lower()
    group = (cached_source_row.get("contains_group_level_data") or "").strip().lower()
    if individual in {"true", "false"} and group in {"true", "false"}:
        return individual, group

    defaults = {
        "single_case_report": ("true", "false"),
        "case_series_or_multi_case": ("true", "true"),
        "observational_group_study": ("false", "true"),
        "interventional_study": ("false", "true"),
        "lab_heavy_clinical_or_translational": ("false", "true"),
        "review_format_with_embedded_original_cohort": ("false", "true"),
        "conference_abstract": ("false", "true"),
        "review_article": ("false", "false"),
        "non_clinical_basic_science": ("false", "false"),
        "unclear_manual_review": ("", ""),
    }
    return defaults.get(category, ("", ""))


def infer_ambiguity_tier(gold_row: dict[str, str], cached_source_row: dict[str, str]) -> str:
    selection_bucket = (gold_row.get("selection_bucket") or "").strip()
    if any(selection_bucket.startswith(prefix) for prefix in AMBIGUOUS_BUCKET_PREFIXES):
        return "ambiguous"
    if (gold_row.get("prediction_correct") or "").strip().lower() == "false":
        return "ambiguous"
    if (cached_source_row.get("classification_confidence") or "").strip() != "high":
        return "ambiguous"
    if truthy(cached_source_row.get("manual_review_required")):
        return "ambiguous"
    return "clear"


def benchmark_selection_priority(
    *,
    benchmark_role: str,
    gold_row: dict[str, str],
    cached_source_row: dict[str, str],
) -> tuple[int, int, int, int]:
    confidence = (cached_source_row.get("classification_confidence") or "").strip()
    confidence_rank = {"high": 0, "medium": 1, "low": 2}.get(confidence, 3)
    selection_bucket = (gold_row.get("selection_bucket") or "").strip()
    bucket_rank = 0 if selection_bucket == "high_confidence_control" else 1
    ambiguity_rank = 0 if benchmark_role.startswith("ambiguous_") else 1
    paper_id = parse_int(gold_row.get("paper_id"), default=10**9)
    return (ambiguity_rank, bucket_rank, confidence_rank, paper_id)


def benchmark_manifest_payload(
    *,
    benchmark_id: str,
    benchmark_rows: list[dict[str, str]],
    requested_categories: list[str],
    missing_requested_categories: list[str],
    default_ambiguous_target: int,
) -> dict[str, Any]:
    return {
        "benchmark_id": benchmark_id,
        "created_at_utc": now_utc_iso(),
        "benchmark_size": len(benchmark_rows),
        "requested_clear_categories": requested_categories,
        "missing_requested_clear_categories": missing_requested_categories,
        "target_ambiguous_rows": default_ambiguous_target,
        "selected_category_counts": dict(
            Counter((row.get("gold_source_category") or "").strip() for row in benchmark_rows)
        ),
        "selected_ambiguity_counts": dict(
            Counter((row.get("gold_ambiguity_tier") or "").strip() for row in benchmark_rows)
        ),
        "models": list(BENCHMARK_MODELS),
        "cached_baseline_model": CACHED_BASELINE_MODEL,
        "runnable_models": list(RUNNABLE_MODELS),
        "gpt41_partial_scoring_note": (
            "Cached gpt-4.1 rows are loaded from flattened registries only. "
            "Metrics that require raw structured outputs, such as evidence quality and "
            "original_sps_spectrum_data, may be unavailable."
        ),
    }


def frozen_payload_summary_fieldnames() -> list[str]:
    return [
        "paper_id",
        "payload_path",
        "payload_sha256",
        "text_source",
        "text_page_count",
        "classify_system_tokens_gpt41",
        "classify_user_tokens_gpt41",
        "classify_total_tokens_gpt41",
        "classify_system_tokens_gpt54",
        "classify_user_tokens_gpt54",
        "classify_total_tokens_gpt54",
        "classify_system_tokens_gpt54_mini",
        "classify_user_tokens_gpt54_mini",
        "classify_total_tokens_gpt54_mini",
        "classify_system_tokens_gpt54_nano",
        "classify_user_tokens_gpt54_nano",
        "classify_total_tokens_gpt54_nano",
        "adjudication_system_tokens_gpt41",
        "adjudication_system_tokens_gpt54",
        "adjudication_system_tokens_gpt54_mini",
        "adjudication_system_tokens_gpt54_nano",
    ]


def model_token_key(model_name: str) -> str:
    mapping = {
        "gpt-4.1": "gpt41",
        "gpt-5.4": "gpt54",
        "gpt-5.4-mini": "gpt54_mini",
        "gpt-5.4-nano": "gpt54_nano",
    }
    return mapping.get(model_name, model_name.replace(".", "").replace("-", "_"))
