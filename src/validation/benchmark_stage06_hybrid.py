from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
GOLD_MANIFEST_PATH = REPO_ROOT / "qa" / "validation" / "source_categorisation" / "gold_standard" / "stage06_count_gold" / "manifest.json"
GOLD_PAPERS_DIR = GOLD_MANIFEST_PATH.parent / "papers"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def parse_int(value: object, *, default: int = 0) -> int:
    text = str(value or "").strip()
    if not text:
        return default
    try:
        return int(text)
    except ValueError:
        return default


def truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def sort_key_for_paper_id(paper_id: str) -> tuple[int, str]:
    return parse_int(paper_id, default=10**9), paper_id


def load_gold_counts(
    *,
    manifest_path: Path,
    gold_papers_dir: Path,
) -> dict[str, int]:
    manifest = load_json(manifest_path)
    counts: dict[str, int] = {}
    for entry in manifest.get("entries") or []:
        if str(entry.get("gold_status") or "") != "active":
            continue
        paper_id = str(entry.get("paper_id") or "").strip()
        if not paper_id:
            continue
        gold_payload = load_json(gold_papers_dir / f"{paper_id}.json")
        counts[paper_id] = parse_int(((gold_payload.get("count_row") or {}).get("likely_sps_case_count")), default=0)
    return counts


def load_selection_ids(path: Path) -> set[str]:
    payload = load_json(path)
    return {str(paper_id).strip() for paper_id in payload.get("paper_ids") or [] if str(paper_id).strip()}


def selected_gold_counts(
    *,
    manifest_path: Path,
    gold_papers_dir: Path,
    selection_path: Path | None,
    exclude_selection_paths: list[Path],
) -> dict[str, int]:
    gold_counts = load_gold_counts(manifest_path=manifest_path, gold_papers_dir=gold_papers_dir)
    selected_ids = set(gold_counts)
    if selection_path is not None:
        selected_ids &= load_selection_ids(selection_path)
    for exclude_path in exclude_selection_paths:
        selected_ids -= load_selection_ids(exclude_path)
    return {
        paper_id: gold_counts[paper_id]
        for paper_id in sorted(selected_ids, key=sort_key_for_paper_id)
    }


def workflow_rows_by_id(path: Path) -> dict[str, dict[str, str]]:
    rows_by_id: dict[str, dict[str, str]] = {}
    for row in load_csv_rows(path):
        paper_id = str(row.get("paper_id") or "").strip()
        if paper_id:
            rows_by_id[paper_id] = dict(row)
    return rows_by_id


def score_workflow(
    *,
    workflow_label: str,
    workflow_path: Path,
    gold_counts: dict[str, int],
) -> dict[str, Any]:
    rows_by_id = workflow_rows_by_id(workflow_path)
    exact = 0
    manual_review = 0
    silent_wrong = 0
    reviewed_overrides = 0
    missing_predictions: list[str] = []
    mismatches: list[dict[str, Any]] = []

    for paper_id, gold_count in gold_counts.items():
        row = rows_by_id.get(paper_id)
        if row is None:
            missing_predictions.append(paper_id)
            mismatches.append(
                {
                    "paper_id": paper_id,
                    "gold_count": gold_count,
                    "predicted_count": None,
                    "count_manual_review_required": None,
                    "count_verification_status": "missing_prediction",
                }
            )
            continue

        predicted_count = parse_int(row.get("likely_sps_case_count"), default=0)
        requires_review = truthy(row.get("count_manual_review_required"))
        verification_status = str(row.get("count_verification_status") or "").strip()
        if verification_status == "manual_review_override":
            reviewed_overrides += 1
        if requires_review:
            manual_review += 1
        if predicted_count == gold_count:
            exact += 1
            continue
        if not requires_review:
            silent_wrong += 1
        mismatches.append(
            {
                "paper_id": paper_id,
                "gold_count": gold_count,
                "predicted_count": predicted_count,
                "count_manual_review_required": requires_review,
                "count_verification_status": verification_status,
            }
        )

    total = len(gold_counts)
    return {
        "workflow_label": workflow_label,
        "workflow_path": str(workflow_path),
        "total": total,
        "exact": exact,
        "exact_accuracy": 0.0 if total == 0 else exact / total,
        "manual_review_rows": manual_review,
        "silent_wrong_auto_accepts": silent_wrong,
        "reviewed_override_rows": reviewed_overrides,
        "missing_predictions": len(missing_predictions),
        "missing_prediction_paper_ids": missing_predictions,
        "mismatches": mismatches,
    }


def markdown_summary(
    *,
    selection_description: str,
    workflow_scores: list[dict[str, Any]],
) -> str:
    lines = [
        "# Stage-06 Hybrid Benchmark",
        "",
        f"- Selection: {selection_description}",
        "",
    ]
    for score in workflow_scores:
        lines.extend(
            [
                f"## {score['workflow_label']}",
                "",
                f"- Exact: `{score['exact']}/{score['total']}`",
                f"- Silent wrong auto-accepts: `{score['silent_wrong_auto_accepts']}`",
                f"- Manual-review rows: `{score['manual_review_rows']}`",
                f"- Reviewed overrides: `{score['reviewed_override_rows']}`",
                f"- Missing predictions: `{score['missing_predictions']}`",
                "",
            ]
        )
    return "\n".join(lines)


def parse_workflow_arg(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("Workflow arguments must be in the form label=path.")
    label, path_text = value.split("=", 1)
    label = label.strip()
    path = Path(path_text.strip())
    if not label or not path_text.strip():
        raise argparse.ArgumentTypeError("Workflow arguments must include both label and path.")
    return label, path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark one or more stage-06 workflow CSV outputs against the reviewed stage-06 gold corpus."
    )
    parser.add_argument("--gold-manifest", type=Path, default=GOLD_MANIFEST_PATH)
    parser.add_argument("--gold-papers-dir", type=Path, default=GOLD_PAPERS_DIR)
    parser.add_argument("--selection-path", type=Path, default=None, help="Optional selection JSON with paper_ids.")
    parser.add_argument(
        "--exclude-selection-path",
        type=Path,
        action="append",
        default=[],
        help="Selection JSON whose paper_ids should be excluded from the benchmark.",
    )
    parser.add_argument(
        "--workflow",
        action="append",
        default=[],
        type=parse_workflow_arg,
        help="Workflow CSV to score, in the form label=path.",
    )
    parser.add_argument("--output-json-path", type=Path, default=None)
    parser.add_argument("--output-md-path", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.workflow:
        raise SystemExit("Provide at least one --workflow label=path argument.")

    gold_counts = selected_gold_counts(
        manifest_path=args.gold_manifest,
        gold_papers_dir=args.gold_papers_dir,
        selection_path=args.selection_path,
        exclude_selection_paths=args.exclude_selection_path,
    )
    selection_description = "full active gold corpus"
    if args.selection_path is not None:
        selection_description = str(args.selection_path)
    if args.exclude_selection_path:
        selection_description += " excluding " + ", ".join(str(path) for path in args.exclude_selection_path)

    workflow_scores = [
        score_workflow(workflow_label=label, workflow_path=path, gold_counts=gold_counts)
        for label, path in args.workflow
    ]
    payload = {
        "selection_description": selection_description,
        "gold_manifest_path": str(args.gold_manifest),
        "gold_papers_dir": str(args.gold_papers_dir),
        "selection_total": len(gold_counts),
        "workflow_scores": workflow_scores,
    }

    if args.output_json_path is not None:
        args.output_json_path.parent.mkdir(parents=True, exist_ok=True)
        args.output_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.output_md_path is not None:
        args.output_md_path.parent.mkdir(parents=True, exist_ok=True)
        args.output_md_path.write_text(
            markdown_summary(selection_description=selection_description, workflow_scores=workflow_scores),
            encoding="utf-8",
        )

    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
