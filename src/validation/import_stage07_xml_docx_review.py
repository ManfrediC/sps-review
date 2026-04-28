from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.validation import _stage07_xml_docx_review as docx_review


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import edited Stage 07 XML DOCX review files into reviewed annotation specs."
    )
    parser.add_argument(
        "--round-dir",
        type=Path,
        required=True,
        help="DOCX review round directory.",
    )
    parser.add_argument(
        "--paper-id",
        action="append",
        default=[],
        help="Restrict import to a paper ID. Repeat for multiple papers.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing reviewed annotation JSON files.",
    )
    parser.add_argument(
        "--skip-regenerate-gold",
        action="store_true",
        help="Only import reviewed annotations; do not regenerate QA-local gold XML/JSON outputs.",
    )
    parser.add_argument(
        "--rescore-candidate-stage07-root",
        type=Path,
        default=None,
        help=(
            "Optional existing Stage 07 XML output root to rescore against the imported review. "
            "No API calls are made; this compares saved candidate outputs with the new gold."
        ),
    )
    parser.add_argument(
        "--rescore-candidate-registry-path",
        type=Path,
        default=None,
        help="Optional Stage 07 XML registry CSV for the rescored candidate root.",
    )
    parser.add_argument(
        "--rescore-evaluation-root",
        type=Path,
        default=None,
        help="Optional root for benchmark artefacts from the import-triggered rescore.",
    )
    parser.add_argument(
        "--rescore-run-id",
        default="",
        help="Optional benchmark run id for the import-triggered rescore.",
    )
    parser.add_argument(
        "--rescore-matrix-config-name",
        default="",
        help="Optional matrix/configuration label attached to the import-triggered rescore.",
    )
    parser.add_argument(
        "--rescore-api-telemetry-path",
        type=Path,
        default=None,
        help="Optional saved telemetry CSV or JSONL to merge into the import-triggered rescore.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paper_ids = {paper_id.strip() for paper_id in args.paper_id if paper_id.strip()} or None
    result = docx_review.import_docx_review_round(
        round_dir=args.round_dir,
        paper_ids=paper_ids,
        force=args.force,
        regenerate_gold=not args.skip_regenerate_gold,
        rescore_candidate_stage07_root=args.rescore_candidate_stage07_root,
        rescore_candidate_registry_path=args.rescore_candidate_registry_path,
        rescore_evaluation_root=args.rescore_evaluation_root,
        rescore_run_id=args.rescore_run_id,
        rescore_matrix_config_name=args.rescore_matrix_config_name,
        rescore_api_telemetry_path=args.rescore_api_telemetry_path,
    )
    print("Imported Stage 07 XML DOCX review round")
    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
