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
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paper_ids = {paper_id.strip() for paper_id in args.paper_id if paper_id.strip()} or None
    result = docx_review.import_docx_review_round(
        round_dir=args.round_dir,
        paper_ids=paper_ids,
        force=args.force,
        regenerate_gold=not args.skip_regenerate_gold,
    )
    print("Imported Stage 07 XML DOCX review round")
    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
