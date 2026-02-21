from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import langextract as lx
from tqdm import tqdm


REPO_ROOT = Path(__file__).resolve().parents[2]
TEXT_JSON_DIR = REPO_ROOT / "data" / "extraction_json" / "text"
RAW_OUT_DIR = REPO_ROOT / "data" / "extraction_json" / "langextract"
SUMMARY_OUT_DIR = REPO_ROOT / "data" / "extraction_json" / "summary"

RAW_OUT_DIR.mkdir(parents=True, exist_ok=True)
SUMMARY_OUT_DIR.mkdir(parents=True, exist_ok=True)

SECTION_ORDER = [
    "clinical_presentation",
    "diagnostics",
    "treatment",
    "outcome",
    "limitations",
]

PROMPT_DESCRIPTION = """
Extract concise, evidence-grounded snippets from a medical case report.

Return extraction classes:
- clinical_presentation: symptoms, signs, syndrome description, disease course
- diagnostics: lab/immunology, EMG/electrophysiology, imaging, diagnostic statements
- treatment: medications, immunotherapy, procedures and timing
- outcome: response, follow-up, prognosis
- limitations: uncertainty, missing data, caveats

Rules:
- Extract only information explicitly stated in the text.
- Keep snippets short and literal when possible.
- Prefer clinically relevant findings over metadata/navigation text.
""".strip()


def build_examples() -> list[Any]:
    text = (
        "A 45-year-old woman presented with progressive axial stiffness and painful spasms. "
        "EMG showed continuous motor unit activity and serum anti-GAD antibodies were positive. "
        "She received diazepam and monthly IVIG. After 6 months, spasms were less frequent and "
        "she could walk independently with mild residual stiffness."
    )

    return [
        lx.data.ExampleData(
            text=text,
            extractions=[
                lx.data.Extraction(
                    extraction_class="clinical_presentation",
                    extraction_text="progressive axial stiffness and painful spasms",
                ),
                lx.data.Extraction(
                    extraction_class="diagnostics",
                    extraction_text="EMG showed continuous motor unit activity and serum anti-GAD antibodies were positive",
                ),
                lx.data.Extraction(
                    extraction_class="treatment",
                    extraction_text="received diazepam and monthly IVIG",
                ),
                lx.data.Extraction(
                    extraction_class="outcome",
                    extraction_text="After 6 months, spasms were less frequent and she could walk independently with mild residual stiffness",
                ),
            ],
        )
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarise extracted paper text JSONs with LangExtract + OpenAI."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=TEXT_JSON_DIR,
        help="Directory containing text extraction JSON files.",
    )
    parser.add_argument(
        "--raw-out-dir",
        type=Path,
        default=RAW_OUT_DIR,
        help="Directory for raw LangExtract outputs.",
    )
    parser.add_argument(
        "--summary-out-dir",
        type=Path,
        default=SUMMARY_OUT_DIR,
        help="Directory for summarised outputs.",
    )
    parser.add_argument(
        "--paper-id",
        action="append",
        default=[],
        help="Paper ID to process (repeat flag for multiple IDs).",
    )
    parser.add_argument("--limit", type=int, default=0, help="Max files to process.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing outputs.")
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs only; no API calls.")
    parser.add_argument(
        "--model-id",
        default="gpt-4.1-mini",
        help="OpenAI model ID used by LangExtract (e.g. gpt-4.1-mini, gpt-5-mini).",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="OpenAI API key; defaults to OPENAI_API_KEY env var.",
    )
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-char-buffer", type=int, default=1200)
    parser.add_argument("--batch-length", type=int, default=8)
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--extraction-passes", type=int, default=2)
    return parser.parse_args()


def load_text_record(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalise_text(record: dict[str, Any]) -> str:
    pages = record.get("pages", [])
    chunks: list[str] = []
    for page in pages:
        page_index = page.get("page_index", 0)
        text = (page.get("text") or "").strip()
        if text:
            chunks.append(f"[Page {int(page_index) + 1}]\n{text}")
    return "\n\n".join(chunks).strip()


def serialise_extraction(extraction: Any) -> dict[str, Any]:
    data = asdict(extraction)
    status = data.get("alignment_status")
    if status is not None:
        data["alignment_status"] = str(status)
    return data


def section_texts(extractions: list[dict[str, Any]]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {key: [] for key in SECTION_ORDER}
    for item in extractions:
        cls = item.get("extraction_class")
        txt = (item.get("extraction_text") or "").strip()
        if cls in grouped and txt and txt not in grouped[cls]:
            grouped[cls].append(txt)
    return grouped


def render_summary(sections: dict[str, list[str]]) -> dict[str, str]:
    rendered: dict[str, str] = {}
    for key in SECTION_ORDER:
        snippets = sections.get(key, [])
        rendered[key] = " ".join(snippets[:3]) if snippets else "Not stated."
    return rendered


def build_overall_summary(rendered_sections: dict[str, str]) -> str:
    return (
        f"Clinical presentation: {rendered_sections['clinical_presentation']} "
        f"Diagnostics: {rendered_sections['diagnostics']} "
        f"Treatment: {rendered_sections['treatment']} "
        f"Outcome: {rendered_sections['outcome']} "
        f"Limitations: {rendered_sections['limitations']}"
    ).strip()


def run_langextract(text: str, args: argparse.Namespace) -> Any:
    api_key = args.api_key or os.getenv("OPENAI_API_KEY")
    return lx.extract(
        text_or_documents=text,
        prompt_description=PROMPT_DESCRIPTION,
        examples=build_examples(),
        model_id=args.model_id,
        api_key=api_key,
        temperature=args.temperature,
        max_char_buffer=args.max_char_buffer,
        batch_length=args.batch_length,
        max_workers=args.max_workers,
        extraction_passes=args.extraction_passes,
        use_schema_constraints=False,
        fence_output=False,
        show_progress=False,
    )


def process_file(path: Path, args: argparse.Namespace) -> str:
    record = load_text_record(path)
    paper_id = str(record.get("paper_id") or path.stem)
    out_raw = args.raw_out_dir / f"{paper_id}.json"
    out_summary = args.summary_out_dir / f"{paper_id}.json"

    if not args.force and out_raw.exists() and out_summary.exists():
        return "skipped"

    text = normalise_text(record)
    if not text:
        raise ValueError(f"No extractable text found in {path}")

    if args.dry_run:
        return "validated"

    annotated = run_langextract(text, args)
    extractions = [serialise_extraction(x) for x in (annotated.extractions or [])]
    grouped = section_texts(extractions)
    rendered = render_summary(grouped)
    overall = build_overall_summary(rendered)

    raw_payload = {
        "paper_id": paper_id,
        "source_filename": record.get("source_filename"),
        "source_sha256": record.get("source_sha256"),
        "model_id": args.model_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "extraction_count": len(extractions),
        "extractions": extractions,
    }
    out_raw.write_text(json.dumps(raw_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    summary_payload = {
        "paper_id": paper_id,
        "source_filename": record.get("source_filename"),
        "source_sha256": record.get("source_sha256"),
        "model_id": args.model_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "section_summaries": rendered,
        "overall_summary": overall,
        "extraction_count": len(extractions),
    }
    out_summary.write_text(
        json.dumps(summary_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return "processed"


def collect_input_files(input_dir: Path, paper_ids: list[str], limit: int) -> list[Path]:
    files = sorted(input_dir.glob("*.json"))
    if paper_ids:
        wanted = set(paper_ids)
        files = [p for p in files if p.stem in wanted]
    if limit and limit > 0:
        files = files[:limit]
    return files


def main() -> None:
    args = parse_args()
    args.raw_out_dir.mkdir(parents=True, exist_ok=True)
    args.summary_out_dir.mkdir(parents=True, exist_ok=True)

    files = collect_input_files(args.input_dir, args.paper_id, args.limit)
    if not files:
        raise SystemExit(f"No input JSON files found in: {args.input_dir}")

    stats = {"processed": 0, "validated": 0, "skipped": 0, "failed": 0}

    for path in tqdm(files, desc="LangExtract summaries"):
        try:
            outcome = process_file(path, args)
            stats[outcome] = stats.get(outcome, 0) + 1
        except Exception as exc:  # keep batch running even if one paper fails
            stats["failed"] += 1
            print(f"[ERROR] {path.name}: {exc}")

    print(
        "Run summary:",
        f"processed={stats['processed']}",
        f"validated={stats['validated']}",
        f"skipped={stats['skipped']}",
        f"failed={stats['failed']}",
    )

    if stats["failed"] > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
