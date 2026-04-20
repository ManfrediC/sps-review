from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.pipelines.stage06_counting.classify import DEFAULT_MODEL as DEFAULT_GPT_MODEL
from src.pipelines.stage06_counting.local_ollama import DEFAULT_OLLAMA_BASE_URL, DEFAULT_OLLAMA_MODEL
from src.pipelines.stage06_counting.runtime import run_stage06_dependency_preflight
from src.validation import _stage06_backfill as backfill


def _batch_resume_payload(
    batch_manifest: dict[str, object],
    *,
    batch_manifest_path: Path,
    run_root: Path,
) -> dict[str, object]:
    existing_run_dirs = backfill.batch_run_dirs(batch_manifest, run_root)
    completed_ids = backfill.completed_paper_ids_for_batch(batch_manifest, run_root)
    remaining_ids = backfill.remaining_paper_ids_for_batch(batch_manifest, run_root)
    payload: dict[str, object] = {
        "batch_manifest_path": backfill.display_path(batch_manifest_path),
        "batch_id": batch_manifest.get("batch_id"),
        "run_id_base": batch_manifest.get("run_id_base"),
        "existing_run_dirs": [backfill.display_path(path) for path in existing_run_dirs],
        "completed_count": len(completed_ids),
        "remaining_count": len(remaining_ids),
        "remaining_paper_ids": remaining_ids,
    }
    if remaining_ids:
        planned_run_id = backfill.next_run_id_for_batch(batch_manifest, run_root)
        payload["planned_run_id"] = planned_run_id
        payload["planned_command"] = backfill.build_hybrid_command(
            batch_manifest=batch_manifest,
            paper_ids=remaining_ids,
            run_id=planned_run_id,
            allow_paid_run=True,
            estimate_only=False,
        )
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run or resume one stage-06 hybrid backfill batch and build the batch QA pack."
    )
    parser.add_argument("--batch-manifest", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, default=backfill.RUN_ROOT)
    parser.add_argument("--qa-output-dir", type=Path, default=backfill.QA_OUTPUT_DIR)
    parser.add_argument("--campaign-root", type=Path, default=backfill.CAMPAIGN_ROOT)
    parser.add_argument("--allow-paid-run", action="store_true")
    parser.add_argument("--estimate-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    batch_manifest = backfill.load_batch_manifest(args.batch_manifest)
    plan_payload = _batch_resume_payload(
        batch_manifest,
        batch_manifest_path=args.batch_manifest,
        run_root=args.run_root,
    )
    remaining_ids = list(plan_payload.get("remaining_paper_ids") or [])
    if args.dry_run:
        print(json.dumps(plan_payload, ensure_ascii=False, indent=2))
        return

    if args.estimate_only and remaining_ids:
        estimate_run_id = backfill.next_run_id_for_batch(batch_manifest, args.run_root)
        command = backfill.build_hybrid_command(
            batch_manifest=batch_manifest,
            paper_ids=remaining_ids,
            run_id=estimate_run_id,
            allow_paid_run=args.allow_paid_run,
            estimate_only=True,
        )
        backfill.run_hybrid_batch_command(command)
        return

    if remaining_ids:
        if not args.allow_paid_run:
            raise SystemExit("Refusing to run a paid stage-06 backfill batch without --allow-paid-run.")
        run_stage06_dependency_preflight(
            ollama_model=DEFAULT_OLLAMA_MODEL,
            ollama_base_url=DEFAULT_OLLAMA_BASE_URL,
            gpt_model=DEFAULT_GPT_MODEL,
        )
        run_id = backfill.next_run_id_for_batch(batch_manifest, args.run_root)
        command = backfill.build_hybrid_command(
            batch_manifest=batch_manifest,
            paper_ids=remaining_ids,
            run_id=run_id,
            allow_paid_run=True,
            estimate_only=False,
        )
        try:
            backfill.run_hybrid_batch_command(command)
        except BaseException as error:
            qa_pack_paths = backfill.write_batch_qa_pack(
                batch_manifest=batch_manifest,
                run_root=args.run_root,
                qa_output_dir=args.qa_output_dir,
            )
            manifest_path = backfill.write_campaign_outputs(
                campaign_id=str(batch_manifest.get("campaign_id") or "").strip(),
                campaign_root=args.campaign_root,
                qa_output_dir=args.qa_output_dir,
                run_root=args.run_root,
            )
            high_risk_rollup_path = backfill.write_campaign_high_risk_review_rollup(
                campaign_id=str(batch_manifest.get("campaign_id") or "").strip(),
                campaign_root=args.campaign_root,
                run_root=args.run_root,
            )
            print(
                json.dumps(
                    {
                        "batch_id": batch_manifest.get("batch_id"),
                        "run_status": "interrupted_or_failed",
                        "resume_summary": _batch_resume_payload(
                            batch_manifest,
                            batch_manifest_path=args.batch_manifest,
                            run_root=args.run_root,
                        ),
                        "qa_pack_paths": qa_pack_paths,
                        "campaign_manifest_path": backfill.display_path(manifest_path),
                        "high_risk_review_rollup_path": backfill.display_path(high_risk_rollup_path),
                        "failure_type": type(error).__name__,
                        "failure_message": str(error),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            raise

    qa_pack_paths = backfill.write_batch_qa_pack(
        batch_manifest=batch_manifest,
        run_root=args.run_root,
        qa_output_dir=args.qa_output_dir,
    )
    manifest_path = backfill.write_campaign_outputs(
        campaign_id=str(batch_manifest.get("campaign_id") or "").strip(),
        campaign_root=args.campaign_root,
        qa_output_dir=args.qa_output_dir,
        run_root=args.run_root,
    )
    high_risk_rollup_path = backfill.write_campaign_high_risk_review_rollup(
        campaign_id=str(batch_manifest.get("campaign_id") or "").strip(),
        campaign_root=args.campaign_root,
        run_root=args.run_root,
    )
    print(
        json.dumps(
            {
                "batch_id": batch_manifest.get("batch_id"),
                "qa_pack_paths": qa_pack_paths,
                "campaign_manifest_path": backfill.display_path(manifest_path),
                "high_risk_review_rollup_path": backfill.display_path(high_risk_rollup_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
