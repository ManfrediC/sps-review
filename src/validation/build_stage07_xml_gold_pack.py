from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.validation import _stage07_xml_review as review


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a static Stage 07 XML human verification pack and gold-standard ledger."
    )
    parser.add_argument(
        "--stage07-root",
        type=Path,
        default=review.STAGE07_XML_ROOT,
        help="Root directory containing canonical Stage 07 XML outputs.",
    )
    parser.add_argument(
        "--registry-path",
        type=Path,
        default=review.STAGE07_XML_REGISTRY_PATH,
        help="Stage 07 XML registry CSV.",
    )
    parser.add_argument(
        "--gold-root",
        type=Path,
        default=review.GOLD_STANDARD_ROOT,
        help="Root directory for non-canonical Stage 07 XML gold-standard review packs.",
    )
    parser.add_argument(
        "--round-id",
        default="",
        help="Optional review round identifier. Defaults to the next YYYY-MM-DD_round_NN directory.",
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
        help="Overwrite an existing round directory with the same round id.",
    )
    parser.add_argument(
        "--refresh-gold-only",
        action="store_true",
        help="Only refresh the cumulative gold-standard CSV from reviewed response rows.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.refresh_gold_only:
        gold_path = review.refresh_gold_standard(gold_root=args.gold_root)
        print(f"Refreshed Stage 07 XML gold ledger: {review.display_path(gold_path)}")
        return

    result = review.build_review_pack(
        round_id=args.round_id or None,
        stage07_root=args.stage07_root,
        registry_path=args.registry_path,
        gold_root=args.gold_root,
        paper_ids={str(paper_id).strip() for paper_id in args.paper_id} if args.paper_id else None,
        force=args.force,
    )
    print("Built Stage 07 XML review pack")
    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
