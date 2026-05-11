"""Snapshot and compare Codex-approved Stage 07 single-case outputs."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STAGE07_ROOT = REPO_ROOT / "data" / "extraction_json" / "stage07_xml"
DEFAULT_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "stage07_xml_registry.csv"
DEFAULT_GOLD_ROOT = REPO_ROOT / "qa" / "validation" / "stage07_single_case_codex_gold"
GOLD_SCHEMA_VERSION = "stage07_single_case_codex_gold_v1"
VOLATILE_JSON_KEYS = {"generated_at_utc", "manifest_run_id"}


@dataclass(frozen=True)
class Stage07Files:
    paper_json: Path
    annotated_text: Path
    segments_json: Path
    target_view_json: Path
    validation_json: Path


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sorted_ids(values: list[str]) -> list[str]:
    def sort_key(value: str) -> tuple[int, str]:
        return (0, f"{int(value):010d}") if value.isdigit() else (1, value)

    return sorted({value.strip() for value in values if value.strip()}, key=sort_key)


def load_registry_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def selected_paper_ids(explicit_ids: list[str], registry_path: Path) -> list[str]:
    if explicit_ids:
        return sorted_ids(explicit_ids)
    return sorted_ids([row.get("paper_id", "") for row in load_registry_rows(registry_path)])


def stage07_files(stage07_root: Path, paper_id: str) -> Stage07Files:
    return Stage07Files(
        paper_json=stage07_root / "papers" / f"{paper_id}.json",
        annotated_text=stage07_root / "annotated_text" / f"{paper_id}.annotated.txt",
        segments_json=stage07_root / "segments" / f"{paper_id}.segments.json",
        target_view_json=stage07_root / "target_views" / paper_id / "p1.json",
        validation_json=stage07_root / "validation" / f"{paper_id}.validation.json",
    )


def gold_batch_dir(gold_root: Path, batch_id: str) -> Path:
    return gold_root / batch_id


def gold_files(gold_root: Path, batch_id: str, paper_id: str) -> Stage07Files:
    batch_dir = gold_batch_dir(gold_root, batch_id)
    return Stage07Files(
        paper_json=batch_dir / "json" / "papers" / f"{paper_id}.json",
        annotated_text=batch_dir / "xml" / f"{paper_id}.annotated.xml",
        segments_json=batch_dir / "json" / "segments" / f"{paper_id}.segments.json",
        target_view_json=batch_dir / "json" / "target_views" / paper_id / "p1.json",
        validation_json=batch_dir / "json" / "validation" / f"{paper_id}.validation.json",
    )


def gold_file_record(gold_root: Path, batch_id: str, paper_id: str) -> dict[str, str]:
    target = gold_files(gold_root, batch_id, paper_id)
    batch_dir = gold_batch_dir(gold_root, batch_id)
    return {
        "paper_id": paper_id,
        "xml": str(target.annotated_text.relative_to(batch_dir)),
        "paper_json": str(target.paper_json.relative_to(batch_dir)),
        "segments_json": str(target.segments_json.relative_to(batch_dir)),
        "target_view_json": str(target.target_view_json.relative_to(batch_dir)),
        "validation_json": str(target.validation_json.relative_to(batch_dir)),
    }


def copy_file(source: Path, target: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def write_registry_snapshot(
    *,
    registry_path: Path,
    gold_root: Path,
    batch_id: str,
    paper_ids: list[str],
    merge_existing: bool = False,
) -> None:
    selected = set(paper_ids)
    rows = [row for row in load_registry_rows(registry_path) if row.get("paper_id") in selected]
    target = gold_batch_dir(gold_root, batch_id) / "registry.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    if merge_existing and target.exists():
        rows_by_id = {
            str(row.get("paper_id") or ""): row
            for row in load_registry_rows(target)
            if str(row.get("paper_id") or "").strip()
        }
        for row in rows:
            rows_by_id[str(row.get("paper_id") or "")] = row
        rows = [rows_by_id[paper_id] for paper_id in sorted_ids(list(rows_by_id))]
    if not rows:
        target.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def snapshot_batch(
    *,
    batch_id: str,
    paper_ids: list[str],
    stage07_root: Path = DEFAULT_STAGE07_ROOT,
    registry_path: Path = DEFAULT_REGISTRY_PATH,
    gold_root: Path = DEFAULT_GOLD_ROOT,
    reviewer_label: str = "codex_gpt5_5_xhigh",
) -> dict[str, Any]:
    ids = selected_paper_ids(paper_ids, registry_path)
    if not ids:
        raise ValueError("No paper ids were provided or found in the registry.")
    copied: list[dict[str, str]] = []
    for paper_id in ids:
        source = stage07_files(stage07_root, paper_id)
        target = gold_files(gold_root, batch_id, paper_id)
        copy_file(source.annotated_text, target.annotated_text)
        copy_file(source.paper_json, target.paper_json)
        copy_file(source.segments_json, target.segments_json)
        copy_file(source.target_view_json, target.target_view_json)
        copy_file(source.validation_json, target.validation_json)
        copied.append(gold_file_record(gold_root, batch_id, paper_id))
    manifest_path = gold_batch_dir(gold_root, batch_id) / "manifest.json"
    existing_manifest: dict[str, Any] = {}
    existing_files_by_id: dict[str, dict[str, str]] = {}
    if paper_ids and manifest_path.exists():
        existing_manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        existing_files_by_id = {
            str(item.get("paper_id") or ""): item
            for item in existing_manifest.get("files") or []
            if str(item.get("paper_id") or "").strip()
        }
    copied_by_id = {item["paper_id"]: item for item in copied}
    if existing_manifest:
        manifest_ids = sorted_ids([*(str(item) for item in existing_manifest.get("paper_ids") or []), *ids])
        copied = [
            copied_by_id.get(paper_id)
            or existing_files_by_id.get(paper_id)
            or gold_file_record(gold_root, batch_id, paper_id)
            for paper_id in manifest_ids
        ]
    else:
        manifest_ids = ids
    write_registry_snapshot(
        registry_path=registry_path,
        gold_root=gold_root,
        batch_id=batch_id,
        paper_ids=ids,
        merge_existing=bool(existing_manifest),
    )
    manifest = {
        "schema_version": GOLD_SCHEMA_VERSION,
        "batch_id": batch_id,
        "reviewer": reviewer_label,
        "created_at_utc": now_utc_iso(),
        "stage07_root": str(stage07_root),
        "registry_path": str(registry_path),
        "paper_ids": manifest_ids,
        "files": copied,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def scrub_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: scrub_json(item)
            for key, item in value.items()
            if key not in VOLATILE_JSON_KEYS
        }
    if isinstance(value, list):
        return [scrub_json(item) for item in value]
    return value


def normalised_json_text(path: Path) -> str:
    payload = scrub_json(json.loads(path.read_text(encoding="utf-8")))
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)


def normalised_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def compare_text_files(current: Path, gold: Path, label: str, failures: list[str]) -> None:
    if normalised_text(current) != normalised_text(gold):
        failures.append(label)


def compare_json_files(current: Path, gold: Path, label: str, failures: list[str]) -> None:
    if normalised_json_text(current) != normalised_json_text(gold):
        failures.append(label)


def compare_batch(
    *,
    batch_id: str,
    stage07_root: Path = DEFAULT_STAGE07_ROOT,
    gold_root: Path = DEFAULT_GOLD_ROOT,
) -> list[str]:
    manifest_path = gold_batch_dir(gold_root, batch_id) / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    failures: list[str] = []
    for paper_id in manifest.get("paper_ids") or []:
        current = stage07_files(stage07_root, str(paper_id))
        gold = gold_files(gold_root, batch_id, str(paper_id))
        compare_text_files(current.annotated_text, gold.annotated_text, f"{paper_id}:annotated_xml", failures)
        compare_json_files(current.paper_json, gold.paper_json, f"{paper_id}:paper_json", failures)
        compare_json_files(current.segments_json, gold.segments_json, f"{paper_id}:segments_json", failures)
        compare_json_files(current.target_view_json, gold.target_view_json, f"{paper_id}:target_view_json", failures)
        compare_json_files(current.validation_json, gold.validation_json, f"{paper_id}:validation_json", failures)
    return failures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    snapshot = subparsers.add_parser("snapshot", help="Copy approved Stage 07 outputs into gold directories.")
    snapshot.add_argument("--batch-id", required=True)
    snapshot.add_argument("--paper-id", action="append", default=[])
    snapshot.add_argument("--stage07-root", type=Path, default=DEFAULT_STAGE07_ROOT)
    snapshot.add_argument("--registry-path", type=Path, default=DEFAULT_REGISTRY_PATH)
    snapshot.add_argument("--gold-root", type=Path, default=DEFAULT_GOLD_ROOT)
    snapshot.add_argument("--reviewer-label", default="codex_gpt5_5_xhigh")

    compare = subparsers.add_parser("compare", help="Compare current Stage 07 outputs with a gold batch.")
    compare.add_argument("--batch-id", required=True)
    compare.add_argument("--stage07-root", type=Path, default=DEFAULT_STAGE07_ROOT)
    compare.add_argument("--gold-root", type=Path, default=DEFAULT_GOLD_ROOT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "snapshot":
        manifest = snapshot_batch(
            batch_id=args.batch_id,
            paper_ids=args.paper_id,
            stage07_root=args.stage07_root,
            registry_path=args.registry_path,
            gold_root=args.gold_root,
            reviewer_label=args.reviewer_label,
        )
        print(f"Snapshotted {len(manifest['paper_ids'])} Stage 07 gold outputs to {gold_batch_dir(args.gold_root, args.batch_id)}")
    elif args.command == "compare":
        failures = compare_batch(
            batch_id=args.batch_id,
            stage07_root=args.stage07_root,
            gold_root=args.gold_root,
        )
        if failures:
            raise SystemExit("Gold comparison failed: " + ", ".join(failures))
        print(f"Gold comparison passed for {args.batch_id}.")


if __name__ == "__main__":
    main()
