from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.validation import _stage07_xml_docx_review as docx_review
from src.validation import _stage07_xml_review as html_review


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a DOCX-based Stage 07 XML gold review pack."
    )
    parser.add_argument(
        "--stage07-root",
        type=Path,
        default=html_review.STAGE07_XML_ROOT,
        help="Root directory containing canonical Stage 07 XML outputs.",
    )
    parser.add_argument(
        "--registry-path",
        type=Path,
        default=html_review.STAGE07_XML_REGISTRY_PATH,
        help="Stage 07 XML registry CSV.",
    )
    parser.add_argument(
        "--review-root",
        type=Path,
        default=docx_review.DOCX_REVIEW_ROOT,
        help="Root directory for DOCX review rounds.",
    )
    parser.add_argument(
        "--round-id",
        required=True,
        help="DOCX review round identifier.",
    )
    parser.add_argument(
        "--paper-id",
        action="append",
        default=[],
        help="Restrict the pack to a paper ID. Repeat for multiple papers.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite files in an existing round directory.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paper_ids = {paper_id.strip() for paper_id in args.paper_id if paper_id.strip()} or None
    result = docx_review.build_docx_review_pack(
        round_id=args.round_id,
        stage07_root=args.stage07_root,
        registry_path=args.registry_path,
        review_root=args.review_root,
        paper_ids=paper_ids,
        force=args.force,
    )
    print("Built Stage 07 XML DOCX review pack")
    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
