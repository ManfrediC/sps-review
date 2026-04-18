from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.pipelines._sps_case_count_registry import count_row_fieldnames
from src.pipelines.stage06_counting.overrides import (
    apply_reviewed_overrides_to_rows,
    reviewed_override_rows_by_id,
)
from src.validation import _stage04_gold as gold
from src.validation import _stage06_review as review


REPO_ROOT = Path(__file__).resolve().parents[2]
TEXT_DIR = REPO_ROOT / "data" / "extraction_json" / "text"
RUN_ROOT = REPO_ROOT / "results" / "stage06_count_runs"
QA_OUTPUT_DIR = REPO_ROOT / "qa" / "validation" / "stage06_llm"
CAMPAIGN_ROOT = QA_OUTPUT_DIR / "backfill_campaign"
GOLD_MANIFEST_PATH = (
    REPO_ROOT
    / "qa"
    / "validation"
    / "source_categorisation"
    / "gold_standard"
    / "stage06_count_gold"
    / "manifest.json"
)
MANUAL_REVIEW_PATH = REPO_ROOT / "data" / "references" / "source_sps_case_count_manual_review.csv"
HYBRID_SCRIPT_PATH = REPO_ROOT / "src" / "pipelines" / "06_extract_sps_case_counts_hybrid.py"
DEFAULT_BATCH_SIZE = 50
CAMPAIGN_STATUS_FILENAME = "status.tsv"
CAMPAIGN_MANIFEST_FILENAME = "manifest.json"
BATCH_DIRNAME = "batches"
BATCH_PATH_OVERRIDE_KEYS = (
    "run_root",
    "qa_output_dir",
    "combined_output_csv_path",
    "inspection_md_path",
    "review_comments_csv_path",
    "review_notes_md_path",
    "raw_run_output_pattern",
)

UNRESOLVED_VERIFICATION_STATUSES = {
    "llm_invalid_manual_review_required",
    "llm_request_failed_manual_review_required",
    "llm_semantic_conflict_manual_review_required",
    "llm_manual_review_required",
    "llm_unable_to_determine",
}
INLINE_CITATION_PAREN_RE = re.compile(r"\(\s*\d+(?:\s*,\s*\d+){1,5}\s*\)")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def today_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def display_path(path: Path) -> str:
    return gold.display_path(path)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv_rows(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_int(value: object, *, default: int = 0) -> int:
    text = str(value or "").strip()
    if not text:
        return default
    try:
        return int(text)
    except ValueError:
        return default


def sort_key_for_paper_id(paper_id: str) -> tuple[int, str]:
    return parse_int(paper_id, default=10**9), paper_id


def sorted_paper_ids(paper_ids: set[str] | list[str]) -> list[str]:
    return sorted({str(paper_id).strip() for paper_id in paper_ids if str(paper_id).strip()}, key=sort_key_for_paper_id)


@dataclass(frozen=True)
class CoverageSnapshot:
    all_text_ids: list[str]
    gold_manual_ids: list[str]
    override_manual_ids: list[str]
    manual_gold_ids: list[str]
    hybrid_processed_ids: list[str]
    covered_ids: list[str]
    uncovered_ids: list[str]

    def summary_counts(self) -> dict[str, int]:
        manual_gold_set = set(self.manual_gold_ids)
        hybrid_set = set(self.hybrid_processed_ids)
        both = manual_gold_set & hybrid_set
        covered = manual_gold_set | hybrid_set
        return {
            "total_text": len(self.all_text_ids),
            "gold_manual": len(self.gold_manual_ids),
            "override_manual": len(self.override_manual_ids),
            "manual_gold": len(self.manual_gold_ids),
            "hybrid_processed": len(self.hybrid_processed_ids),
            "both": len(both),
            "covered": len(covered),
            "remaining": len(self.uncovered_ids),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary_counts": self.summary_counts(),
            "all_text_ids": self.all_text_ids,
            "gold_manual_ids": self.gold_manual_ids,
            "override_manual_ids": self.override_manual_ids,
            "manual_gold_ids": self.manual_gold_ids,
            "hybrid_processed_ids": self.hybrid_processed_ids,
            "covered_ids": self.covered_ids,
            "uncovered_ids": self.uncovered_ids,
        }


def load_text_ids(text_dir: Path = TEXT_DIR) -> set[str]:
    return {path.stem for path in text_dir.glob("*.json")}


def load_active_gold_manual_ids(gold_manifest_path: Path = GOLD_MANIFEST_PATH) -> set[str]:
    manifest = load_json(gold_manifest_path)
    return {
        str(entry.get("paper_id") or "").strip()
        for entry in manifest.get("entries") or []
        if str(entry.get("gold_status") or "").strip() == "active" and str(entry.get("paper_id") or "").strip()
    }


def load_reviewed_override_ids(manual_review_path: Path = MANUAL_REVIEW_PATH) -> set[str]:
    return set(reviewed_override_rows_by_id(manual_review_path))


def _payload_has_hybrid_v2(payload: dict[str, Any]) -> bool:
    count_row = payload.get("count_row") or {}
    model_row = payload.get("model_count_row") or {}
    versions = [
        str(count_row.get("count_version") or "").strip(),
        str(model_row.get("count_version") or "").strip(),
    ]
    return any(version.startswith("hybrid_v2_") for version in versions)


def load_hybrid_processed_ids(run_root: Path = RUN_ROOT) -> set[str]:
    hybrid_ids: set[str] = set()
    if not run_root.exists():
        return hybrid_ids
    for run_dir in run_root.iterdir():
        results_dir = run_dir / "results"
        if not run_dir.is_dir() or not results_dir.exists():
            continue
        for result_path in results_dir.glob("*.json"):
            try:
                payload = load_json(result_path)
            except json.JSONDecodeError:
                continue
            if not _payload_has_hybrid_v2(payload):
                continue
            paper_id = str(payload.get("paper_id") or (payload.get("count_row") or {}).get("paper_id") or result_path.stem).strip()
            if paper_id:
                hybrid_ids.add(paper_id)
    return hybrid_ids


def compute_coverage_snapshot(
    *,
    text_dir: Path = TEXT_DIR,
    gold_manifest_path: Path = GOLD_MANIFEST_PATH,
    manual_review_path: Path = MANUAL_REVIEW_PATH,
    run_root: Path = RUN_ROOT,
) -> CoverageSnapshot:
    text_ids = load_text_ids(text_dir)
    gold_manual_ids = load_active_gold_manual_ids(gold_manifest_path) & text_ids
    override_manual_ids = load_reviewed_override_ids(manual_review_path) & text_ids
    manual_gold_ids = gold_manual_ids | override_manual_ids
    hybrid_processed_ids = load_hybrid_processed_ids(run_root) & text_ids
    covered_ids = manual_gold_ids | hybrid_processed_ids
    uncovered_ids = text_ids - covered_ids
    return CoverageSnapshot(
        all_text_ids=sorted_paper_ids(text_ids),
        gold_manual_ids=sorted_paper_ids(gold_manual_ids),
        override_manual_ids=sorted_paper_ids(override_manual_ids),
        manual_gold_ids=sorted_paper_ids(manual_gold_ids),
        hybrid_processed_ids=sorted_paper_ids(hybrid_processed_ids),
        covered_ids=sorted_paper_ids(covered_ids),
        uncovered_ids=sorted_paper_ids(uncovered_ids),
    )


def chunk_paper_ids(paper_ids: list[str], batch_size: int = DEFAULT_BATCH_SIZE) -> list[list[str]]:
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1.")
    return [paper_ids[index : index + batch_size] for index in range(0, len(paper_ids), batch_size)]


def default_campaign_id(*, date_tag: str | None = None) -> str:
    return f"stage06_backfill_{date_tag or today_tag()}"


def campaign_date_tag(campaign_id: str) -> str:
    match = re.search(r"(20\d{6})", str(campaign_id or ""))
    if match:
        return match.group(1)
    return today_tag()


def campaign_dir(campaign_id: str, campaign_root: Path = CAMPAIGN_ROOT) -> Path:
    return campaign_root / str(campaign_id).strip()


def batch_id_text(batch_index: int) -> str:
    return f"b{batch_index:03d}"


def base_run_id(*, batch_index: int, paper_count: int, date_tag: str) -> str:
    return f"stage06_backfill_{batch_id_text(batch_index)}_n{paper_count}_{date_tag}"


def batch_index_from_text(value: object, *, default: int = 0) -> int:
    text = str(value or "").strip()
    match = re.fullmatch(r"b0*(\d+)", text)
    if match:
        return parse_int(match.group(1), default=default)
    return parse_int(text, default=default)


def run_id_base_paper_count(run_id_base: str) -> int:
    match = re.search(r"_n(\d+)_", str(run_id_base or "").strip())
    if not match:
        return 0
    return parse_int(match.group(1), default=0)


def batch_sizes_for_target_count(total_target_count: int, batch_size: int) -> list[int]:
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1.")
    if total_target_count < 1:
        return []
    full_batches, remainder = divmod(total_target_count, batch_size)
    batch_sizes = [batch_size] * full_batches
    if remainder:
        batch_sizes.append(remainder)
    return batch_sizes


def raw_output_csv_path_for_run(run_id: str, qa_output_dir: Path = QA_OUTPUT_DIR) -> Path:
    return qa_output_dir / f"{run_id}.csv"


def status_rows_for_snapshot(snapshot: CoverageSnapshot) -> list[dict[str, object]]:
    counts = snapshot.summary_counts()
    ordered_metrics = [
        "manual_gold",
        "hybrid_processed",
        "both",
        "covered",
        "remaining",
        "total_text",
    ]
    return [{"metric": metric, "count": counts[metric]} for metric in ordered_metrics]


def build_batch_payload(
    *,
    batch_index: int,
    paper_ids: list[str],
    date_tag: str,
    campaign_path: Path,
    manifest_path: Path,
    status_path: Path,
    qa_output_dir: Path,
    run_root: Path,
    run_id_base: str | None = None,
    path_overrides: dict[str, str] | None = None,
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    batch_id = batch_id_text(batch_index)
    resolved_run_id_base = str(run_id_base or base_run_id(batch_index=batch_index, paper_count=len(paper_ids), date_tag=date_tag)).strip()
    batch_manifest_path = campaign_path / BATCH_DIRNAME / f"{batch_id}.json"
    batch_payload = {
        "campaign_id": campaign_path.name,
        "campaign_manifest_path": display_path(manifest_path),
        "campaign_status_path": display_path(status_path),
        "generated_at_utc": now_utc_iso(),
        "batch_index": batch_index,
        "batch_id": batch_id,
        "paper_count": len(paper_ids),
        "paper_ids": paper_ids,
        "run_id_base": resolved_run_id_base,
        "run_root": display_path(run_root),
        "qa_output_dir": display_path(qa_output_dir),
        "combined_output_csv_path": display_path(qa_output_dir / f"{resolved_run_id_base}_combined.csv"),
        "inspection_md_path": display_path(qa_output_dir / f"{resolved_run_id_base}_inspection.md"),
        "review_comments_csv_path": display_path(qa_output_dir / f"{resolved_run_id_base}_review_comments.csv"),
        "review_notes_md_path": display_path(qa_output_dir / f"{resolved_run_id_base}_review_notes.md"),
        "raw_run_output_pattern": f"{resolved_run_id_base}*.csv",
    }
    if path_overrides:
        for key in BATCH_PATH_OVERRIDE_KEYS:
            value = str(path_overrides.get(key) or "").strip()
            if value:
                batch_payload[key] = value
    batch_entry = {
        "batch_index": batch_index,
        "batch_id": batch_id,
        "paper_count": len(paper_ids),
        "run_id_base": resolved_run_id_base,
        "batch_manifest_path": display_path(batch_manifest_path),
    }
    return batch_manifest_path, batch_payload, batch_entry


def load_existing_batch_specs(
    campaign_path: Path,
    manifest_path: Path,
) -> list[dict[str, Any]]:
    if not manifest_path.exists():
        return []
    try:
        manifest_payload = load_json(manifest_path)
    except json.JSONDecodeError:
        return []

    batch_specs: list[dict[str, Any]] = []
    for entry in manifest_payload.get("batches") or []:
        batch_index = parse_int(entry.get("batch_index"), default=len(batch_specs) + 1)
        batch_id = str(entry.get("batch_id") or batch_id_text(batch_index)).strip() or batch_id_text(batch_index)
        batch_manifest_path_text = str(entry.get("batch_manifest_path") or "").strip()
        if batch_manifest_path_text:
            batch_manifest_path = review.resolve_repo_path(batch_manifest_path_text)
        else:
            batch_manifest_path = campaign_path / BATCH_DIRNAME / f"{batch_id}.json"
        try:
            batch_payload = load_json(batch_manifest_path) if batch_manifest_path.exists() else {}
        except json.JSONDecodeError:
            batch_payload = {}
        paper_ids = sorted_paper_ids(batch_payload.get("paper_ids") or [])
        run_id_base = str(batch_payload.get("run_id_base") or entry.get("run_id_base") or "").strip()
        if not paper_ids:
            continue
        batch_specs.append(
            {
                "batch_index": batch_index,
                "batch_id": batch_id,
                "paper_ids": paper_ids,
                "run_id_base": run_id_base or None,
            }
        )
    return sorted(batch_specs, key=lambda spec: parse_int(spec.get("batch_index"), default=10**6))


def load_batch_specs_for_repair(
    campaign_path: Path,
    manifest_path: Path,
) -> list[dict[str, Any]]:
    manifest_payload: dict[str, Any] = {}
    if manifest_path.exists():
        try:
            manifest_payload = load_json(manifest_path)
        except json.JSONDecodeError:
            manifest_payload = {}

    manifest_entries_by_index: dict[int, dict[str, Any]] = {}
    for entry in manifest_payload.get("batches") or []:
        batch_index = parse_int(
            entry.get("batch_index"),
            default=batch_index_from_text(entry.get("batch_id"), default=len(manifest_entries_by_index) + 1),
        )
        if batch_index > 0:
            manifest_entries_by_index[batch_index] = entry

    specs_by_index: dict[int, dict[str, Any]] = {}
    batch_dir = campaign_path / BATCH_DIRNAME
    if batch_dir.exists():
        for batch_manifest_path in sorted(
            batch_dir.glob("*.json"),
            key=lambda path: batch_index_from_text(path.stem, default=10**6),
        ):
            try:
                batch_payload = load_json(batch_manifest_path)
            except json.JSONDecodeError:
                continue
            batch_index = parse_int(
                batch_payload.get("batch_index"),
                default=batch_index_from_text(batch_manifest_path.stem),
            )
            if batch_index < 1:
                continue
            manifest_entry = manifest_entries_by_index.get(batch_index, {})
            specs_by_index[batch_index] = {
                "batch_index": batch_index,
                "batch_id": str(batch_payload.get("batch_id") or batch_manifest_path.stem).strip()
                or batch_id_text(batch_index),
                "paper_ids": sorted_paper_ids(batch_payload.get("paper_ids") or []),
                "run_id_base": str(
                    batch_payload.get("run_id_base") or manifest_entry.get("run_id_base") or ""
                ).strip()
                or None,
                "path_overrides": {
                    key: str(batch_payload.get(key) or "").strip()
                    for key in BATCH_PATH_OVERRIDE_KEYS
                    if str(batch_payload.get(key) or "").strip()
                },
            }

    for batch_index, manifest_entry in manifest_entries_by_index.items():
        if batch_index in specs_by_index:
            continue
        batch_manifest_path_text = str(manifest_entry.get("batch_manifest_path") or "").strip()
        batch_manifest_path = (
            review.resolve_repo_path(batch_manifest_path_text)
            if batch_manifest_path_text
            else campaign_path / BATCH_DIRNAME / f"{batch_id_text(batch_index)}.json"
        )
        batch_payload: dict[str, Any] = {}
        if batch_manifest_path.exists():
            try:
                batch_payload = load_json(batch_manifest_path)
            except json.JSONDecodeError:
                batch_payload = {}
        specs_by_index[batch_index] = {
            "batch_index": batch_index,
            "batch_id": str(
                batch_payload.get("batch_id") or manifest_entry.get("batch_id") or batch_id_text(batch_index)
            ).strip()
            or batch_id_text(batch_index),
            "paper_ids": sorted_paper_ids(batch_payload.get("paper_ids") or []),
            "run_id_base": str(
                batch_payload.get("run_id_base") or manifest_entry.get("run_id_base") or ""
            ).strip()
            or None,
            "path_overrides": {
                key: str(batch_payload.get(key) or "").strip()
                for key in BATCH_PATH_OVERRIDE_KEYS
                if str(batch_payload.get(key) or "").strip()
            },
        }

    return [
        specs_by_index[batch_index]
        for batch_index in sorted(specs_by_index, key=lambda value: value)
    ]


def build_campaign_payload(
    *,
    snapshot: CoverageSnapshot,
    campaign_id: str,
    batch_size: int,
    campaign_root: Path,
    qa_output_dir: Path,
    run_root: Path,
    batch_specs: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], list[tuple[Path, dict[str, Any]]]]:
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1.")

    campaign_path = campaign_dir(campaign_id, campaign_root)
    manifest_path = campaign_path / CAMPAIGN_MANIFEST_FILENAME
    status_path = campaign_path / CAMPAIGN_STATUS_FILENAME
    date_tag = campaign_date_tag(campaign_id)
    batch_payloads: list[tuple[Path, dict[str, Any]]] = []
    batch_entries: list[dict[str, Any]] = []

    resolved_batch_specs = batch_specs or [
        {
            "batch_index": batch_index,
            "paper_ids": paper_ids,
            "run_id_base": None,
        }
        for batch_index, paper_ids in enumerate(chunk_paper_ids(snapshot.uncovered_ids, batch_size), start=1)
    ]
    for spec in resolved_batch_specs:
        batch_manifest_path, batch_payload, batch_entry = build_batch_payload(
            batch_index=parse_int(spec.get("batch_index"), default=len(batch_entries) + 1),
            paper_ids=sorted_paper_ids(spec.get("paper_ids") or []),
            date_tag=date_tag,
            campaign_path=campaign_path,
            manifest_path=manifest_path,
            status_path=status_path,
            qa_output_dir=qa_output_dir,
            run_root=run_root,
            run_id_base=str(spec.get("run_id_base") or "").strip() or None,
            path_overrides=spec.get("path_overrides") if isinstance(spec.get("path_overrides"), dict) else None,
        )
        batch_payload["campaign_id"] = campaign_id
        batch_payloads.append((batch_manifest_path, batch_payload))
        batch_entries.append(batch_entry)

    campaign_payload = {
        "campaign_id": campaign_id,
        "generated_at_utc": now_utc_iso(),
        "batch_size": batch_size,
        "campaign_root": display_path(campaign_path),
        "qa_output_dir": display_path(qa_output_dir),
        "run_root": display_path(run_root),
        "coverage": snapshot.to_dict(),
        "status_rows": status_rows_for_snapshot(snapshot),
        "batch_count": len(batch_entries),
        "batches": batch_entries,
    }
    return campaign_payload, batch_payloads


def repair_campaign_outputs(
    *,
    campaign_id: str,
    batch_size: int | None = None,
    campaign_root: Path = CAMPAIGN_ROOT,
    qa_output_dir: Path = QA_OUTPUT_DIR,
    text_dir: Path = TEXT_DIR,
    gold_manifest_path: Path = GOLD_MANIFEST_PATH,
    manual_review_path: Path = MANUAL_REVIEW_PATH,
    run_root: Path = RUN_ROOT,
) -> Path:
    snapshot = compute_coverage_snapshot(
        text_dir=text_dir,
        gold_manifest_path=gold_manifest_path,
        manual_review_path=manual_review_path,
        run_root=run_root,
    )
    campaign_path = campaign_dir(campaign_id, campaign_root)
    manifest_path = campaign_path / CAMPAIGN_MANIFEST_FILENAME

    manifest_payload: dict[str, Any] = {}
    if manifest_path.exists():
        try:
            manifest_payload = load_json(manifest_path)
        except json.JSONDecodeError:
            manifest_payload = {}

    existing_batch_size = parse_int(manifest_payload.get("batch_size"), default=0)
    effective_batch_size = batch_size or existing_batch_size or DEFAULT_BATCH_SIZE
    if existing_batch_size and batch_size is not None and batch_size != existing_batch_size:
        raise ValueError(
            f"Repair requires the existing batch size of {existing_batch_size}, not {batch_size}."
        )

    existing_specs = load_batch_specs_for_repair(campaign_path, manifest_path)
    if not existing_specs:
        raise ValueError("Cannot repair a campaign without existing batch manifests.")

    existing_specs_by_index = {
        parse_int(spec.get("batch_index"), default=0): spec
        for spec in existing_specs
        if parse_int(spec.get("batch_index"), default=0) > 0
    }
    completed_specs_by_index: dict[int, dict[str, Any]] = {}
    completed_target_ids: set[str] = set()

    for batch_index in sorted(existing_specs_by_index):
        spec = existing_specs_by_index[batch_index]
        run_id_base = str(spec.get("run_id_base") or "").strip()
        if not run_id_base:
            continue
        completed_ids = completed_paper_ids_for_batch({"run_id_base": run_id_base}, run_root)
        if not completed_ids:
            continue
        sorted_completed_ids = sorted_paper_ids(completed_ids)
        declared_count = run_id_base_paper_count(run_id_base)
        if declared_count and len(sorted_completed_ids) != declared_count:
            raise ValueError(
                f"Completed run '{run_id_base}' produced {len(sorted_completed_ids)} papers, "
                f"but the run ID declares {declared_count}. Repair requires a fully completed batch."
            )
        overlapping_ids = completed_target_ids & set(sorted_completed_ids)
        if overlapping_ids:
            overlap_text = ", ".join(sorted_paper_ids(overlapping_ids))
            raise ValueError(
                f"Completed campaign batches overlap on paper IDs: {overlap_text}."
            )
        completed_target_ids.update(sorted_completed_ids)
        completed_specs_by_index[batch_index] = {
            **spec,
            "paper_ids": sorted_completed_ids,
            "run_id_base": run_id_base,
        }

    uncovered_overlap = set(snapshot.uncovered_ids) & completed_target_ids
    if uncovered_overlap:
        overlap_text = ", ".join(sorted_paper_ids(uncovered_overlap))
        raise ValueError(
            f"Repair cannot continue because completed campaign papers still appear uncovered: {overlap_text}."
        )

    campaign_target_ids = sorted_paper_ids(set(snapshot.uncovered_ids) | completed_target_ids)
    batch_sizes = batch_sizes_for_target_count(len(campaign_target_ids), effective_batch_size)
    if not batch_sizes:
        raise ValueError("Repair cannot continue because the campaign target set is empty.")

    if completed_specs_by_index and max(completed_specs_by_index) > len(batch_sizes):
        raise ValueError(
            f"Completed batch index {max(completed_specs_by_index)} exceeds the repaired batch count "
            f"of {len(batch_sizes)}."
        )

    remaining_uncovered_ids = list(snapshot.uncovered_ids)
    remaining_offset = 0
    date_tag = campaign_date_tag(campaign_id)
    repaired_batch_specs: list[dict[str, Any]] = []

    for batch_index, expected_paper_count in enumerate(batch_sizes, start=1):
        completed_spec = completed_specs_by_index.get(batch_index)
        existing_spec = existing_specs_by_index.get(batch_index, {})
        if completed_spec:
            repaired_paper_ids = sorted_paper_ids(completed_spec.get("paper_ids") or [])
            if len(repaired_paper_ids) != expected_paper_count:
                raise ValueError(
                    f"Completed batch {batch_id_text(batch_index)} has {len(repaired_paper_ids)} papers, "
                    f"but deterministic repair requires {expected_paper_count}."
                )
            run_id_base = str(completed_spec.get("run_id_base") or "").strip() or base_run_id(
                batch_index=batch_index,
                paper_count=len(repaired_paper_ids),
                date_tag=date_tag,
            )
            path_overrides = dict(existing_spec.get("path_overrides") or {})
        else:
            repaired_paper_ids = remaining_uncovered_ids[
                remaining_offset : remaining_offset + expected_paper_count
            ]
            if len(repaired_paper_ids) != expected_paper_count:
                raise ValueError(
                    f"Repair could only allocate {len(repaired_paper_ids)} papers to {batch_id_text(batch_index)}, "
                    f"but expected {expected_paper_count}."
                )
            remaining_offset += expected_paper_count
            existing_run_id_base = str(existing_spec.get("run_id_base") or "").strip()
            if existing_run_id_base and run_id_base_paper_count(existing_run_id_base) == len(repaired_paper_ids):
                run_id_base = existing_run_id_base
                path_overrides = dict(existing_spec.get("path_overrides") or {})
            else:
                run_id_base = base_run_id(
                    batch_index=batch_index,
                    paper_count=len(repaired_paper_ids),
                    date_tag=date_tag,
                )
                path_overrides = {}
        repaired_batch_specs.append(
            {
                "batch_index": batch_index,
                "batch_id": batch_id_text(batch_index),
                "paper_ids": repaired_paper_ids,
                "run_id_base": run_id_base,
                "path_overrides": path_overrides,
            }
        )

    if remaining_offset != len(remaining_uncovered_ids):
        leftover_text = ", ".join(sorted_paper_ids(remaining_uncovered_ids[remaining_offset:]))
        raise ValueError(
            f"Repair left uncovered papers unassigned to campaign batches: {leftover_text}."
        )

    campaign_payload, batch_payloads = build_campaign_payload(
        snapshot=snapshot,
        campaign_id=campaign_id,
        batch_size=effective_batch_size,
        campaign_root=campaign_root,
        qa_output_dir=qa_output_dir,
        run_root=run_root,
        batch_specs=repaired_batch_specs,
    )
    write_json(manifest_path, campaign_payload)
    write_csv_rows(
        campaign_path / CAMPAIGN_STATUS_FILENAME,
        status_rows_for_snapshot(snapshot),
        ["metric", "count"],
    )
    batch_dir = campaign_path / BATCH_DIRNAME
    expected_batch_manifest_names = {batch_manifest_path.name for batch_manifest_path, _ in batch_payloads}
    if batch_dir.exists():
        for stale_batch_manifest in batch_dir.glob("*.json"):
            if stale_batch_manifest.name not in expected_batch_manifest_names:
                stale_batch_manifest.unlink()
    for batch_manifest_path, batch_payload in batch_payloads:
        write_json(batch_manifest_path, batch_payload)
    return manifest_path


def write_campaign_outputs(
    *,
    campaign_id: str,
    batch_size: int = DEFAULT_BATCH_SIZE,
    campaign_root: Path = CAMPAIGN_ROOT,
    qa_output_dir: Path = QA_OUTPUT_DIR,
    text_dir: Path = TEXT_DIR,
    gold_manifest_path: Path = GOLD_MANIFEST_PATH,
    manual_review_path: Path = MANUAL_REVIEW_PATH,
    run_root: Path = RUN_ROOT,
) -> Path:
    snapshot = compute_coverage_snapshot(
        text_dir=text_dir,
        gold_manifest_path=gold_manifest_path,
        manual_review_path=manual_review_path,
        run_root=run_root,
    )
    campaign_path = campaign_dir(campaign_id, campaign_root)
    manifest_path = campaign_path / CAMPAIGN_MANIFEST_FILENAME
    existing_batch_specs = load_existing_batch_specs(campaign_path, manifest_path)
    campaign_payload, batch_payloads = build_campaign_payload(
        snapshot=snapshot,
        campaign_id=campaign_id,
        batch_size=batch_size,
        campaign_root=campaign_root,
        qa_output_dir=qa_output_dir,
        run_root=run_root,
        batch_specs=existing_batch_specs or None,
    )
    write_json(manifest_path, campaign_payload)
    write_csv_rows(
        campaign_path / CAMPAIGN_STATUS_FILENAME,
        status_rows_for_snapshot(snapshot),
        ["metric", "count"],
    )
    batch_dir = campaign_path / BATCH_DIRNAME
    expected_batch_manifest_names = {batch_manifest_path.name for batch_manifest_path, _ in batch_payloads}
    if batch_dir.exists():
        for stale_batch_manifest in batch_dir.glob("*.json"):
            if stale_batch_manifest.name not in expected_batch_manifest_names:
                stale_batch_manifest.unlink()
    for batch_manifest_path, batch_payload in batch_payloads:
        write_json(batch_manifest_path, batch_payload)
    return manifest_path


def load_batch_manifest(path: Path) -> dict[str, Any]:
    return load_json(path)


def batch_run_dirs(batch_manifest: dict[str, Any], run_root: Path = RUN_ROOT) -> list[Path]:
    run_id_base = str(batch_manifest.get("run_id_base") or "").strip()
    if not run_id_base or not run_root.exists():
        return []
    resume_pattern = re.compile(rf"^{re.escape(run_id_base)}_resume(\d+)$")
    matched: list[tuple[int, Path]] = []
    for run_dir in run_root.iterdir():
        if not run_dir.is_dir():
            continue
        if run_dir.name == run_id_base:
            matched.append((0, run_dir))
            continue
        resume_match = resume_pattern.match(run_dir.name)
        if resume_match:
            matched.append((parse_int(resume_match.group(1), default=10**6), run_dir))
    return [path for _, path in sorted(matched, key=lambda item: item[0])]


def completed_paper_ids_for_run_dir(run_dir: Path) -> set[str]:
    results_dir = run_dir / "results"
    if not results_dir.exists():
        return set()
    return {path.stem for path in results_dir.glob("*.json")}


def completed_paper_ids_for_batch(batch_manifest: dict[str, Any], run_root: Path = RUN_ROOT) -> set[str]:
    completed_ids: set[str] = set()
    for run_dir in batch_run_dirs(batch_manifest, run_root):
        completed_ids.update(completed_paper_ids_for_run_dir(run_dir))
    return completed_ids


def remaining_paper_ids_for_batch(batch_manifest: dict[str, Any], run_root: Path = RUN_ROOT) -> list[str]:
    target_ids = {str(paper_id).strip() for paper_id in batch_manifest.get("paper_ids") or [] if str(paper_id).strip()}
    return sorted_paper_ids(target_ids - completed_paper_ids_for_batch(batch_manifest, run_root))


def next_run_id_for_batch(batch_manifest: dict[str, Any], run_root: Path = RUN_ROOT) -> str:
    run_id_base = str(batch_manifest.get("run_id_base") or "").strip()
    existing_dirs = batch_run_dirs(batch_manifest, run_root)
    if not existing_dirs:
        return run_id_base
    resume_numbers = [
        parse_int(path.name.rsplit("_resume", 1)[1], default=0)
        for path in existing_dirs
        if "_resume" in path.name
    ]
    next_resume = (max(resume_numbers) if resume_numbers else 0) + 1
    return f"{run_id_base}_resume{next_resume:02d}"


def build_hybrid_command(
    *,
    batch_manifest: dict[str, Any],
    paper_ids: list[str],
    run_id: str,
    allow_paid_run: bool,
    estimate_only: bool = False,
) -> list[str]:
    qa_output_dir = review.resolve_repo_path(str(batch_manifest.get("qa_output_dir") or display_path(QA_OUTPUT_DIR)))
    command = [
        sys.executable,
        str(HYBRID_SCRIPT_PATH),
        "--run-id",
        run_id,
        "--output-path",
        str(raw_output_csv_path_for_run(run_id, qa_output_dir)),
        "--allow-unresolved-export",
        "--skip-registry-refresh",
    ]
    if estimate_only:
        command.append("--estimate-only")
    elif allow_paid_run:
        command.append("--allow-paid-run")
    else:
        raise ValueError("Paid batch runs require allow_paid_run=True.")
    for paper_id in paper_ids:
        command.extend(["--paper-id", paper_id])
    return command


def run_hybrid_batch_command(command: list[str]) -> None:
    subprocess.run(command, check=True, cwd=str(REPO_ROOT))


def _count_row_from_result_payload(result_path: Path) -> dict[str, str]:
    payload = load_json(result_path)
    count_row = {
        fieldname: str((payload.get("count_row") or {}).get(fieldname) or "")
        for fieldname in count_row_fieldnames()
    }
    if not count_row.get("paper_id"):
        count_row["paper_id"] = result_path.stem
    return count_row


def load_count_rows_from_run_dir(
    run_dir: Path,
    *,
    qa_output_dir: Path = QA_OUTPUT_DIR,
) -> list[dict[str, str]]:
    raw_csv_path = raw_output_csv_path_for_run(run_dir.name, qa_output_dir)
    if raw_csv_path.exists():
        return [
            {fieldname: str(row.get(fieldname) or "") for fieldname in count_row_fieldnames()}
            for row in load_csv_rows(raw_csv_path)
        ]

    results_dir = run_dir / "results"
    return [
        _count_row_from_result_payload(result_path)
        for result_path in sorted(results_dir.glob("*.json"), key=lambda path: sort_key_for_paper_id(path.stem))
    ]


def combined_count_rows_for_batch(
    batch_manifest: dict[str, Any],
    *,
    run_root: Path = RUN_ROOT,
    qa_output_dir: Path = QA_OUTPUT_DIR,
) -> list[dict[str, str]]:
    rows_by_id: dict[str, dict[str, str]] = {}
    for run_dir in batch_run_dirs(batch_manifest, run_root):
        for row in load_count_rows_from_run_dir(run_dir, qa_output_dir=qa_output_dir):
            paper_id = str(row.get("paper_id") or "").strip()
            if paper_id:
                rows_by_id[paper_id] = row
    return [
        rows_by_id[paper_id]
        for paper_id in sorted(rows_by_id, key=sort_key_for_paper_id)
    ]


def _merged_review_rows_from_run_dirs(run_dirs: list[Path]) -> list[dict[str, str]]:
    latest_by_paper: dict[str, dict[str, str]] = {}
    for run_dir in run_dirs:
        for row in review.load_review_rows_from_run(run_dir):
            paper_id = str(row.get("paper_id") or "").strip()
            if paper_id:
                latest_by_paper[paper_id] = row
    return [
        latest_by_paper[paper_id]
        for paper_id in sorted(latest_by_paper, key=sort_key_for_paper_id)
    ]


def review_rows_for_batch(
    batch_manifest: dict[str, Any],
    *,
    run_root: Path = RUN_ROOT,
) -> list[dict[str, str]]:
    return _merged_review_rows_from_run_dirs(batch_run_dirs(batch_manifest, run_root))


def _overlay_reviewed_overrides(
    rows: list[dict[str, str]],
    *,
    manual_review_path: Path = MANUAL_REVIEW_PATH,
) -> tuple[list[dict[str, str]], list[str]]:
    override_rows = reviewed_override_rows_by_id(manual_review_path)
    if not override_rows:
        return [dict(row) for row in rows], []
    return apply_reviewed_overrides_to_rows(rows, override_rows)


def _local_result_payload(evidence_payload: dict[str, Any]) -> dict[str, Any]:
    path_text = str(evidence_payload.get("local_result_json_path") or "").strip()
    if not path_text:
        return {}
    return review.load_json(review.resolve_repo_path(path_text))


def inspection_markdown(
    *,
    batch_manifest: dict[str, Any],
    review_rows: list[dict[str, str]],
) -> str:
    lines = [
        f"# {batch_manifest.get('run_id_base')} Inspection Pack",
        "",
    ]
    for row in review_rows:
        paper_id = str(row.get("paper_id") or "").strip()
        title = str(row.get("title") or "").strip()
        decision_payload = review.load_decision_payload(str(row.get("count_decision_json_path") or ""))
        evidence_payload = review.load_evidence_payload(str(row.get("count_evidence_json_path") or ""))
        local_payload = _local_result_payload(evidence_payload)
        decision = decision_payload.get("decision") or {}
        local_parsed = local_payload.get("parsed_output") or {}
        local_count = local_parsed.get("n_spsd_patients")
        local_count_text = "None" if local_count in {None, ""} else str(local_count)
        evidence_items = list(decision.get("evidence") or evidence_payload.get("evidence") or [])
        missing_batch_artifacts: list[str] = []
        if not decision_payload:
            missing_batch_artifacts.append("count_decision")
        if not evidence_payload:
            missing_batch_artifacts.append("count_evidence")
        batch_artifacts_status = "complete" if not missing_batch_artifacts else f"missing {', '.join(missing_batch_artifacts)}"

        lines.extend(
            [
                f"## {paper_id} - {title}",
                f"- predicted_count: {str(row.get('likely_sps_case_count') or '').strip()}",
                f"- predicted_basis: {str(row.get('count_basis') or '').strip()}",
                f"- verification_status: {str(row.get('count_verification_status') or '').strip()}",
                f"- manual_review_required: {str(row.get('count_manual_review_required') or '').strip()}",
                f"- provenance_uncertain: {str(row.get('count_original_cohort_provenance_uncertain') or '').strip()}",
                f"- validator_flags: {str(row.get('count_validator_flags') or '').strip()}",
                f"- count_reason: {str(row.get('count_reason') or '').strip()}",
                f"- batch_artifacts_status: {batch_artifacts_status}",
                (
                    f"- local_model_count: {local_count_text} "
                    f"({str(local_parsed.get('confidence') or '').strip()}; "
                    f"needs_review={str(local_parsed.get('needs_review') or '').strip()})"
                ),
                f"- local_reasoning: {str(local_parsed.get('reasoning_short') or '').strip()}",
                f"- gpt_decision_type: {str(decision.get('decision_type') or '').strip()}",
                f"- gpt_selected_candidate_id: {str(decision.get('selected_candidate_id') or '').strip()}",
                f"- gpt_alternative_count: {decision.get('alternative_count')}",
                f"- gpt_confidence: {str(decision.get('count_confidence') or '').strip()}",
                f"- gpt_manual_review_required: {decision.get('count_manual_review_required')}",
                f"- gpt_reasoning: {str(decision.get('count_reasoning_summary') or '').strip()}",
                "- evidence:",
            ]
        )
        if evidence_items:
            for item in evidence_items:
                page_value = item.get("page")
                page_text = "None" if page_value in {None, ""} else str(page_value)
                lines.append(f"  - p{page_text}: {str(item.get('quote') or '').strip()}")
        else:
            lines.append("  - None")
        lines.append("")
    return "\n".join(lines)


def _review_comment_defaults(row: dict[str, str]) -> dict[str, str]:
    return {
        "paper_id": str(row.get("paper_id") or "").strip(),
        "title": str(row.get("title") or "").strip(),
        "stage06_output_count": str(row.get("likely_sps_case_count") or "").strip(),
        "verification_status": str(row.get("count_verification_status") or "").strip(),
        "manual_review_required": str(row.get("count_manual_review_required") or "").strip(),
        "assessment": "",
        "failure_modes": "",
        "review_comment": "",
    }


def _candidate_support_by_count(candidate_payload: dict[str, Any]) -> tuple[list[str], dict[str, dict[str, Any]]]:
    ordered_counts: list[str] = []
    support_by_count: dict[str, dict[str, Any]] = {}
    for candidate in candidate_payload.get("candidates") or []:
        count_text = str(candidate.get("proposed_count") or "").strip()
        if not count_text:
            continue
        if count_text not in ordered_counts:
            ordered_counts.append(count_text)
        entry = support_by_count.setdefault(
            count_text,
            {"bases": [], "evidence": [], "citation_like": False},
        )
        basis = str(candidate.get("count_basis") or "").strip()
        if basis and basis not in entry["bases"]:
            entry["bases"].append(basis)
        evidence_text = " ".join(str(candidate.get("evidence_text") or "").split())
        if evidence_text and evidence_text not in entry["evidence"]:
            entry["evidence"].append(evidence_text[:200])
        if (
            basis in {"diagnosis_specific_suffix_count", "diagnosis_specific_fraction_suffix_count"}
            and evidence_text
            and INLINE_CITATION_PAREN_RE.search(evidence_text)
        ):
            entry["citation_like"] = True
    return ordered_counts, support_by_count


def _format_candidate_support(ordered_counts: list[str], support_by_count: dict[str, dict[str, Any]]) -> str:
    parts: list[str] = []
    for count_text in ordered_counts:
        bases = list(support_by_count.get(count_text, {}).get("bases") or [])
        if bases:
            parts.append(f"{count_text} ({'; '.join(bases[:3])})")
        else:
            parts.append(count_text)
    return ", ".join(parts)


def _likely_count_note(
    *,
    predicted_count_text: str,
    ordered_counts: list[str],
    support_by_count: dict[str, dict[str, Any]],
    manual_review_required: bool,
) -> str:
    nonzero_counts = [count_text for count_text in ordered_counts if count_text != "0"]
    predicted_support = support_by_count.get(predicted_count_text, {})

    if predicted_support.get("citation_like") and nonzero_counts:
        alternative_counts = [count_text for count_text in nonzero_counts if count_text != predicted_count_text]
        if alternative_counts:
            alternative = alternative_counts[0]
            return (
                f"{alternative} looks likelier because {predicted_count_text} only comes from a citation-like "
                "suffix snippet."
            )

    if predicted_count_text not in support_by_count and len(nonzero_counts) == 1:
        only_count = nonzero_counts[0]
        return f"{only_count} looks likelier because it is the only explicit extracted count surfaced in the candidate package."

    if manual_review_required and len(set(nonzero_counts)) > 1:
        return f"The likelier count is still unclear because the candidate package surfaced competing counts: {', '.join(nonzero_counts)}."

    if predicted_support and nonzero_counts:
        alternative_counts = [count_text for count_text in nonzero_counts if count_text != predicted_count_text]
        if alternative_counts:
            alternative = max(
                alternative_counts,
                key=lambda count_text: (
                    len(support_by_count.get(count_text, {}).get("bases") or []),
                    len(support_by_count.get(count_text, {}).get("evidence") or []),
                ),
            )
            if len(support_by_count.get(alternative, {}).get("bases") or []) > len(predicted_support.get("bases") or []):
                return (
                    f"{alternative} may be likelier because it appears in more independent extracted signals than "
                    f"{predicted_count_text}."
                )
    return ""


def _auto_review_comment(row: dict[str, str]) -> str:
    candidate_payload = review.load_candidate_package(str(row.get("count_candidate_json_path") or ""))
    if not candidate_payload:
        return ""
    ordered_counts, support_by_count = _candidate_support_by_count(candidate_payload)
    if not ordered_counts:
        return ""

    verification_status = str(row.get("count_verification_status") or "").strip()
    manual_review_required = str(row.get("count_manual_review_required") or "").strip().lower() == "true"
    if len(set(ordered_counts)) <= 1 and not (manual_review_required or verification_status in UNRESOLVED_VERIFICATION_STATUSES):
        return ""

    predicted_count_text = str(row.get("likely_sps_case_count") or "").strip()
    decision_payload = review.load_decision_payload(str(row.get("count_decision_json_path") or ""))
    decision = decision_payload.get("decision") or {}

    parts = [
        f"Pipeline output: {predicted_count_text or 'unknown'}.",
        f"Extracted counts seen: {_format_candidate_support(ordered_counts, support_by_count)}.",
    ]
    decision_type = str(decision.get("decision_type") or "").strip()
    decision_confidence = str(decision.get("count_confidence") or "").strip()
    if decision_type or decision_confidence:
        decision_bits = [bit for bit in [decision_type, decision_confidence] if bit]
        parts.append(f"GPT decision: {'; '.join(decision_bits)}.")

    likely_note = _likely_count_note(
        predicted_count_text=predicted_count_text,
        ordered_counts=ordered_counts,
        support_by_count=support_by_count,
        manual_review_required=manual_review_required,
    )
    if likely_note:
        parts.append(likely_note)
    return " ".join(part for part in parts if part).strip()


def build_review_comments_rows(
    review_rows: list[dict[str, str]],
    *,
    existing_rows_by_id: dict[str, dict[str, str]] | None = None,
    manual_review_path: Path = MANUAL_REVIEW_PATH,
) -> list[dict[str, str]]:
    existing_rows_by_id = existing_rows_by_id or {}
    override_rows_by_id = reviewed_override_rows_by_id(manual_review_path)
    rows: list[dict[str, str]] = []
    for row in review_rows:
        paper_id = str(row.get("paper_id") or "").strip()
        existing = existing_rows_by_id.get(paper_id, {})
        verification_status = str(row.get("count_verification_status") or "").strip()
        override_row = override_rows_by_id.get(paper_id, {})
        review_comment = str(existing.get("review_comment") or "").strip()
        if verification_status == "manual_review_override":
            review_comment = str(override_row.get("reviewer_notes") or "").strip() or review_comment
        if not review_comment:
            review_comment = _auto_review_comment(row)
        merged = _review_comment_defaults(row)
        merged.update(
            {
                "assessment": str(existing.get("assessment") or "").strip(),
                "failure_modes": str(existing.get("failure_modes") or "").strip(),
                "review_comment": review_comment,
            }
        )
        rows.append(merged)
    return rows


def write_review_comments_csv(
    *,
    review_rows: list[dict[str, str]],
    output_path: Path,
    manual_review_path: Path = MANUAL_REVIEW_PATH,
) -> None:
    existing_rows_by_id: dict[str, dict[str, str]] = {}
    if output_path.exists():
        existing_rows_by_id = {
            str(row.get("paper_id") or "").strip(): row
            for row in load_csv_rows(output_path)
            if str(row.get("paper_id") or "").strip()
        }
    rows = build_review_comments_rows(
        review_rows,
        existing_rows_by_id=existing_rows_by_id,
        manual_review_path=manual_review_path,
    )
    write_csv_rows(
        output_path,
        rows,
        [
            "paper_id",
            "title",
            "stage06_output_count",
            "verification_status",
            "manual_review_required",
            "assessment",
            "failure_modes",
            "review_comment",
        ],
    )


def review_notes_markdown(
    *,
    batch_manifest: dict[str, Any],
    review_rows: list[dict[str, str]],
    manual_review_path: Path = MANUAL_REVIEW_PATH,
) -> str:
    verification_counts: dict[str, int] = {}
    likely_clean_ids: list[str] = []
    likely_user_review_ids: list[str] = []
    override_rows_by_id = reviewed_override_rows_by_id(manual_review_path)
    resolved_override_lines: list[str] = []
    priority_review_lines: list[str] = []
    for row in review_rows:
        verification_status = str(row.get("count_verification_status") or "").strip() or "<blank>"
        verification_counts[verification_status] = verification_counts.get(verification_status, 0) + 1
        paper_id = str(row.get("paper_id") or "").strip()
        predicted_count = str(row.get("likely_sps_case_count") or "").strip() or "unknown"
        requires_manual = str(row.get("count_manual_review_required") or "").strip().lower() == "true"
        if requires_manual or verification_status in UNRESOLVED_VERIFICATION_STATUSES:
            likely_user_review_ids.append(paper_id)
            auto_comment = _auto_review_comment(row)
            if auto_comment:
                priority_review_lines.append(f"- `{paper_id}`: {auto_comment}")
            else:
                priority_review_lines.append(
                    f"- `{paper_id}`: pipeline output `{predicted_count}` still needs manual source comparison."
                )
        elif verification_status == "llm_candidate_exact":
            likely_clean_ids.append(paper_id)
        if verification_status == "manual_review_override":
            override_row = override_rows_by_id.get(paper_id, {})
            reviewer_notes = str(override_row.get("reviewer_notes") or "").strip()
            if reviewer_notes:
                resolved_override_lines.append(f"- `{paper_id} -> {predicted_count}`: {reviewer_notes}")
            else:
                resolved_override_lines.append(f"- `{paper_id} -> {predicted_count}`")

    lines = [
        f"# Stage 06 {batch_manifest.get('batch_id')} Review Notes",
        "",
        f"- Combined QA CSV: `{batch_manifest.get('combined_output_csv_path')}`",
        f"- Inspection pack: `{batch_manifest.get('inspection_md_path')}`",
        f"- Per-paper comments: `{batch_manifest.get('review_comments_csv_path')}`",
        "",
        "## Outcome",
        "",
        f"- Reviewed papers: {len(review_rows)}",
    ]
    for verification_status in sorted(verification_counts):
        lines.append(f"- `{verification_status}`: {verification_counts[verification_status]}")
    lines.extend(
        [
            "",
            "## Model-Based Triage",
            "",
            f"- Likely clean on first pass: {', '.join(likely_clean_ids) if likely_clean_ids else 'None'}",
            (
                "- Likely user review candidates: "
                f"{', '.join(likely_user_review_ids) if likely_user_review_ids else 'None'}"
            ),
            "",
            "## Resolved Manual Overrides",
            "",
        ]
    )
    if resolved_override_lines:
        lines.extend(resolved_override_lines)
    else:
        lines.append("- None applied for this batch.")
    lines.extend(
        [
            "",
            "## Priority Review Candidates",
            "",
        ]
    )
    if priority_review_lines:
        lines.extend(priority_review_lines)
    else:
        lines.append("- None remaining after applying reviewed overrides.")
    lines.extend(
        [
            "",
            "## Assistant QA Notes",
            "",
            (
                "- Reviewed overrides have already been folded into the combined QA CSV and these notes."
                if resolved_override_lines
                else "- No reviewed override rows were available for this batch when these notes were generated."
            ),
            (
                "- Populate the paired review-comments CSV during manual batch QA for the remaining review candidates."
                if priority_review_lines
                else "- No remaining model-flagged review candidates are present in this batch."
            ),
        ]
    )
    return "\n".join(lines)


def write_combined_count_csv(rows: list[dict[str, str]], output_path: Path) -> None:
    write_csv_rows(output_path, rows, count_row_fieldnames())


def write_batch_qa_pack(
    *,
    batch_manifest: dict[str, Any],
    run_root: Path = RUN_ROOT,
    qa_output_dir: Path = QA_OUTPUT_DIR,
    manual_review_path: Path = MANUAL_REVIEW_PATH,
) -> dict[str, str]:
    run_dirs = batch_run_dirs(batch_manifest, run_root)
    if not run_dirs:
        raise ValueError("No stage-06 run directories were found for the requested batch.")

    raw_combined_rows = combined_count_rows_for_batch(batch_manifest, run_root=run_root, qa_output_dir=qa_output_dir)
    raw_review_rows = _merged_review_rows_from_run_dirs(run_dirs)
    combined_rows, _ = _overlay_reviewed_overrides(raw_combined_rows, manual_review_path=manual_review_path)
    review_rows, _ = _overlay_reviewed_overrides(raw_review_rows, manual_review_path=manual_review_path)

    combined_output_path = review.resolve_repo_path(str(batch_manifest.get("combined_output_csv_path") or ""))
    inspection_path = review.resolve_repo_path(str(batch_manifest.get("inspection_md_path") or ""))
    comments_path = review.resolve_repo_path(str(batch_manifest.get("review_comments_csv_path") or ""))
    notes_path = review.resolve_repo_path(str(batch_manifest.get("review_notes_md_path") or ""))

    write_combined_count_csv(combined_rows, combined_output_path)
    inspection_path.parent.mkdir(parents=True, exist_ok=True)
    inspection_path.write_text(
        inspection_markdown(batch_manifest=batch_manifest, review_rows=review_rows),
        encoding="utf-8",
    )
    write_review_comments_csv(
        review_rows=review_rows,
        output_path=comments_path,
        manual_review_path=manual_review_path,
    )
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    notes_path.write_text(
        review_notes_markdown(
            batch_manifest=batch_manifest,
            review_rows=review_rows,
            manual_review_path=manual_review_path,
        ),
        encoding="utf-8",
    )
    return {
        "combined_output_csv_path": display_path(combined_output_path),
        "inspection_md_path": display_path(inspection_path),
        "review_comments_csv_path": display_path(comments_path),
        "review_notes_md_path": display_path(notes_path),
    }
