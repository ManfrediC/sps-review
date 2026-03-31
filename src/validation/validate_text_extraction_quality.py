from __future__ import annotations

import argparse
import csv
import json
import random
import re
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
TEXT_DIR = REPO_ROOT / "data" / "extraction_json" / "text"
REGISTRY_PATH = REPO_ROOT / "data" / "references" / "pdf_source_registry.csv"
DEFAULT_SEED = 20260331
DEFAULT_SAMPLE_SIZE = 300
DEFAULT_LONG_PAGE_THRESHOLD = 20
DEFAULT_BASELINE_SHARE = 0.50
DEFAULT_OCR_SHARE = 0.20
DEFAULT_LONG_PROCEEDINGS_SHARE = 0.15
DEFAULT_ARTIFACT_SHARE = 0.15
PROCEEDINGS_KEYWORDS = (
    "abstract",
    "abstracts",
    "proceedings",
    "supplement",
    "meeting",
    "conference",
    "poster",
    "annual meeting",
)
MOJIBAKE_PATTERNS = (
    "ï¬",
    "â€“",
    "â€”",
    "â€",
    "â€™",
    "â€œ",
    "â€",
    "Ã",
    "\ufffd",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a stratified manual-review sample for step 03 text extraction quality checks."
    )
    parser.add_argument(
        "--text-dir",
        type=Path,
        default=TEXT_DIR,
        help="Directory containing text extraction JSON files from 03_extract_text.py.",
    )
    parser.add_argument(
        "--registry-path",
        type=Path,
        default=REGISTRY_PATH,
        help="Path to data/references/pdf_source_registry.csv for title and author metadata.",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=DEFAULT_SAMPLE_SIZE,
        help="Total number of records to sample for manual review.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help="Random seed for reproducible sampling.",
    )
    parser.add_argument(
        "--long-page-threshold",
        type=int,
        default=DEFAULT_LONG_PAGE_THRESHOLD,
        help="Treat records with at least this many pages as long documents.",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=None,
        help="Optional JSON report path.",
    )
    parser.add_argument(
        "--review-csv-path",
        type=Path,
        default=None,
        help="Optional CSV review sheet path.",
    )
    return parser.parse_args()


def load_registry_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return {row["covidence_id"]: row for row in csv.DictReader(handle)}


def count_mojibake_markers(text: str) -> int:
    return sum(text.count(pattern) for pattern in MOJIBAKE_PATTERNS)


def looks_like_proceedings(title: str, source_filename: str) -> bool:
    haystack = f"{title} {source_filename}".lower()
    return any(keyword in haystack for keyword in PROCEEDINGS_KEYWORDS)


def first_page_excerpt(pages: list[dict[str, Any]], *, max_chars: int = 240) -> str:
    if not pages:
        return ""
    text = " ".join(str(pages[0].get("text") or "").split())
    return text[:max_chars]


def load_text_record(path: Path, registry_row: dict[str, str] | None, *, long_page_threshold: int) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    pages = payload.get("pages") or []
    full_text = "\n".join(str(page.get("text") or "") for page in pages)
    source_filename = str(payload.get("source_filename") or "")
    title = (registry_row or {}).get("title", "")
    authors = (registry_row or {}).get("authors", "")
    published_year = (registry_row or {}).get("published_year", "")
    remaining_flags = [str(flag) for flag in (payload.get("remaining_text_quality_flags") or [])]
    mojibake_count = count_mojibake_markers(full_text)
    proceedings_like = looks_like_proceedings(title, source_filename)
    n_pages = int(payload.get("n_pages") or len(pages) or 0)

    return {
        "covidence_id": path.stem,
        "text_json_path": str(path),
        "source_filename": source_filename,
        "title": title,
        "authors": authors,
        "published_year": published_year,
        "ocr_applied": bool(payload.get("ocr_applied")),
        "ocr_mode": str(payload.get("ocr_mode") or ""),
        "ocr_trigger_reasons": [str(flag) for flag in (payload.get("ocr_trigger_reasons") or [])],
        "n_pages": n_pages,
        "suspicious_control_chars": int(payload.get("suspicious_control_chars") or 0),
        "remaining_text_quality_flags": remaining_flags,
        "native_extraction_error": payload.get("native_extraction_error"),
        "ocr_error": payload.get("ocr_error"),
        "processing_error": payload.get("processing_error"),
        "mojibake_marker_count": mojibake_count,
        "proceedings_like": proceedings_like,
        "long_document": n_pages >= long_page_threshold,
        "first_page_excerpt": first_page_excerpt(pages),
    }


def load_records(
    *,
    text_dir: Path,
    registry_rows: dict[str, dict[str, str]],
    long_page_threshold: int,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(text_dir.glob("*.json")):
        records.append(
            load_text_record(
                path,
                registry_rows.get(path.stem),
                long_page_threshold=long_page_threshold,
            )
        )
    return records


def quota_plan(sample_size: int) -> dict[str, int]:
    baseline = round(sample_size * DEFAULT_BASELINE_SHARE)
    ocr = round(sample_size * DEFAULT_OCR_SHARE)
    long_proceedings = round(sample_size * DEFAULT_LONG_PROCEEDINGS_SHARE)
    text_artifacts = sample_size - baseline - ocr - long_proceedings
    return {
        "ocr_applied": ocr,
        "long_or_proceedings": long_proceedings,
        "text_artifacts": text_artifacts,
        "baseline_random": baseline,
    }


def classify_record(record: dict[str, Any]) -> list[str]:
    buckets = ["baseline_random"]
    if record["ocr_applied"]:
        buckets.append("ocr_applied")
    if record["long_document"] or record["proceedings_like"]:
        buckets.append("long_or_proceedings")
    if (
        record["suspicious_control_chars"] > 0
        or record["mojibake_marker_count"] > 0
        or record["remaining_text_quality_flags"]
        or record["native_extraction_error"] is not None
        or record["ocr_error"] is not None
        or record["processing_error"] is not None
    ):
        buckets.append("text_artifacts")
    return buckets


def build_pools(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    pools: dict[str, list[dict[str, Any]]] = {
        "baseline_random": [],
        "ocr_applied": [],
        "long_or_proceedings": [],
        "text_artifacts": [],
    }
    for record in records:
        for bucket in classify_record(record):
            pools[bucket].append(record)
    return pools


def sample_records(records: list[dict[str, Any]], *, sample_size: int, seed: int) -> tuple[list[dict[str, Any]], dict[str, int], dict[str, int]]:
    if sample_size <= 0:
        raise ValueError("sample_size must be positive")
    if sample_size > len(records):
        raise ValueError("sample_size cannot exceed the number of available extraction records")

    rng = random.Random(seed)
    quotas = quota_plan(sample_size)
    pools = build_pools(records)
    selected_ids: set[str] = set()
    selected: list[dict[str, Any]] = []
    actual_counts: dict[str, int] = {bucket: 0 for bucket in quotas}

    for bucket in ("ocr_applied", "long_or_proceedings", "text_artifacts"):
        candidates = [record for record in pools[bucket] if record["covidence_id"] not in selected_ids]
        take = min(quotas[bucket], len(candidates))
        for record in rng.sample(candidates, take):
            selected_ids.add(record["covidence_id"])
            selected.append(
                {
                    **record,
                    "sample_bucket": bucket,
                    "risk_tags": sorted(tag for tag in classify_record(record) if tag != "baseline_random"),
                }
            )
        actual_counts[bucket] = take

    remaining = sample_size - len(selected)
    baseline_candidates = [record for record in pools["baseline_random"] if record["covidence_id"] not in selected_ids]
    for record in rng.sample(baseline_candidates, remaining):
        selected_ids.add(record["covidence_id"])
        selected.append(
            {
                **record,
                "sample_bucket": "baseline_random",
                "risk_tags": sorted(tag for tag in classify_record(record) if tag != "baseline_random"),
            }
        )
    actual_counts["baseline_random"] = remaining

    selected.sort(key=lambda row: (row["sample_bucket"], int(row["covidence_id"])))
    return selected, quotas, actual_counts


def build_review_rows(sampled_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in sampled_records:
        rows.append(
            {
                "covidence_id": record["covidence_id"],
                "sample_bucket": record["sample_bucket"],
                "risk_tags": ";".join(record["risk_tags"]),
                "title": record["title"],
                "authors": record["authors"],
                "published_year": record["published_year"],
                "source_filename": record["source_filename"],
                "text_json_path": record["text_json_path"],
                "ocr_applied": record["ocr_applied"],
                "ocr_mode": record["ocr_mode"],
                "ocr_trigger_reasons": ";".join(record["ocr_trigger_reasons"]),
                "n_pages": record["n_pages"],
                "proceedings_like": record["proceedings_like"],
                "long_document": record["long_document"],
                "suspicious_control_chars": record["suspicious_control_chars"],
                "mojibake_marker_count": record["mojibake_marker_count"],
                "remaining_text_quality_flags": ";".join(record["remaining_text_quality_flags"]),
                "first_page_excerpt": record["first_page_excerpt"],
                "review_status": "",
                "review_notes": "",
            }
        )
    return rows


def write_review_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_report(
    *,
    records: list[dict[str, Any]],
    sampled_records: list[dict[str, Any]],
    quotas: dict[str, int],
    actual_counts: dict[str, int],
    sample_size: int,
    seed: int,
    long_page_threshold: int,
) -> dict[str, Any]:
    bucket_sizes = {bucket: len(pool) for bucket, pool in build_pools(records).items()}
    return {
        "sample_size_requested": sample_size,
        "sampled_count": len(sampled_records),
        "seed": seed,
        "long_page_threshold": long_page_threshold,
        "population_count": len(records),
        "bucket_sizes": bucket_sizes,
        "quota_plan": quotas,
        "sample_bucket_counts": dict(Counter(record["sample_bucket"] for record in sampled_records)),
        "high_risk_counts_in_sample": {
            "ocr_applied": sum(1 for record in sampled_records if record["ocr_applied"]),
            "long_or_proceedings": sum(
                1 for record in sampled_records if record["long_document"] or record["proceedings_like"]
            ),
            "text_artifacts": sum(
                1
                for record in sampled_records
                if record["suspicious_control_chars"] > 0
                or record["mojibake_marker_count"] > 0
                or record["remaining_text_quality_flags"]
                or record["native_extraction_error"] is not None
                or record["ocr_error"] is not None
                or record["processing_error"] is not None
            ),
        },
        "actual_quota_counts": actual_counts,
        "sampled_records": sampled_records,
    }


def main() -> None:
    args = parse_args()
    registry_rows = load_registry_rows(args.registry_path)
    records = load_records(
        text_dir=args.text_dir,
        registry_rows=registry_rows,
        long_page_threshold=args.long_page_threshold,
    )
    sampled_records, quotas, actual_counts = sample_records(
        records,
        sample_size=args.sample_size,
        seed=args.seed,
    )
    report = build_report(
        records=records,
        sampled_records=sampled_records,
        quotas=quotas,
        actual_counts=actual_counts,
        sample_size=args.sample_size,
        seed=args.seed,
        long_page_threshold=args.long_page_threshold,
    )

    if args.output_path is not None:
        args.output_path.parent.mkdir(parents=True, exist_ok=True)
        args.output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.review_csv_path is not None:
        write_review_csv(args.review_csv_path, build_review_rows(sampled_records))

    print(f"Built text extraction quality sample: {len(sampled_records)} / {len(records)} records")
    print(f"Quota plan: {quotas}")
    print(f"Actual counts: {actual_counts}")
    print(f"Sample bucket counts: {report['sample_bucket_counts']}")


if __name__ == "__main__":
    main()
