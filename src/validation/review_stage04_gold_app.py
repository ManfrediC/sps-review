from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from src.validation._stage04_gold import (
    DEFAULT_REVIEWER,
    PDF_ALIGNMENT_OPTIONS,
    ROUND_RESPONSES_FILENAME,
    SOURCE_CATEGORY_OPTIONS,
    build_gold_snapshot_rows,
    build_response_row,
    count_completed_reviews,
    discover_round_directories,
    display_path,
    load_round_queue_rows,
    load_round_responses_by_id,
    resolve_repo_path,
    round_gold_snapshot_path,
    round_label_from_directory,
    upsert_gold_master,
    write_round_outputs,
)


PDF_VIEW_HEIGHT = 1000


@st.cache_data(show_spinner=False)
def load_pdf_bytes(pdf_path_text: str) -> bytes:
    pdf_path = resolve_repo_path(pdf_path_text)
    return pdf_path.read_bytes()


def normalise_count_text(value: str) -> str:
    stripped = (value or "").strip()
    return stripped if stripped else "0"


def round_options() -> list[Path]:
    return list(reversed(discover_round_directories()))


def first_pending_index(snapshot_rows: list[dict[str, str]]) -> int:
    for index, row in enumerate(snapshot_rows):
        if (row.get("review_status") or "").strip() != "reviewed":
            return index
    return 0


def response_defaults(
    queue_row: dict[str, str],
    response_row: dict[str, str],
) -> tuple[bool, str, str, str, str]:
    predicted_category = (queue_row.get("predicted_source_category") or "").strip()
    predicted_count = normalise_count_text(queue_row.get("predicted_likely_sps_case_count") or "")
    saved_category = (response_row.get("reviewed_source_category") or "").strip()
    saved_count = normalise_count_text(response_row.get("reviewed_extractable_sps_case_count") or "")
    prediction_correct = (response_row.get("prediction_correct") or "").strip() == "true"
    if response_row and not prediction_correct:
        category_value = saved_category or predicted_category
        count_value = saved_count or predicted_count
    else:
        category_value = predicted_category
        count_value = predicted_count
        if not response_row:
            prediction_correct = True
    alignment_value = (response_row.get("pdf_content_alignment_tag") or "appears_matched").strip()
    notes_value = (response_row.get("reviewer_notes") or "").strip()
    return prediction_correct, category_value, count_value, alignment_value, notes_value


def render_sidebar(round_dir: Path, snapshot_rows: list[dict[str, str]]) -> int:
    completed = count_completed_reviews(snapshot_rows)
    total = len(snapshot_rows)
    st.sidebar.subheader("Round progress")
    st.sidebar.progress(completed / total if total else 0.0, text=f"{completed} of {total} reviewed")
    if total:
        pending_ids = [
            (row.get("paper_id") or "").strip()
            for row in snapshot_rows
            if (row.get("review_status") or "").strip() != "reviewed"
        ]
        if pending_ids:
            st.sidebar.caption(f"Pending: {', '.join(pending_ids[:5])}{' ...' if len(pending_ids) > 5 else ''}")
        else:
            st.sidebar.success("Round complete. Gold export and master file are up to date.")
    st.sidebar.caption(f"Responses file: `{display_path(round_dir / ROUND_RESPONSES_FILENAME)}`")
    st.sidebar.caption(f"Gold snapshot: `{display_path(round_gold_snapshot_path(round_dir))}`")
    return completed


def main() -> None:
    st.set_page_config(page_title="Stage 04 Gold Reviewer", layout="wide")
    st.title("Stage 04 Gold Reviewer")
    st.caption("Review source category and extractable SPS patient count against the source PDF.")

    available_rounds = round_options()
    if not available_rounds:
        st.warning(
            "No gold-standard rounds are available yet. Run "
            "`python src/validation/build_stage04_gold_batch.py` first."
        )
        return

    round_labels = {round_label_from_directory(path): path for path in available_rounds}
    selected_label = st.sidebar.selectbox("Round", options=list(round_labels.keys()))
    round_dir = round_labels[selected_label]
    queue_rows = load_round_queue_rows(round_dir)
    responses_by_id = load_round_responses_by_id(round_dir)
    snapshot_rows = build_gold_snapshot_rows(queue_rows, responses_by_id)
    if not queue_rows:
        st.error(f"No queue rows were found in {display_path(round_dir)}.")
        return

    round_state_key = "stage04_gold_round"
    if st.session_state.get(round_state_key) != selected_label:
        st.session_state[round_state_key] = selected_label
        st.session_state["stage04_gold_index"] = first_pending_index(snapshot_rows)

    current_index = st.session_state.get("stage04_gold_index", 0)
    current_index = max(0, min(current_index, len(queue_rows) - 1))
    render_sidebar(round_dir, snapshot_rows)

    jump_options = [
        f"{index + 1}. {(row.get('paper_id') or '').strip()} | {(row.get('selection_bucket') or '').strip()} | {(row.get('title') or '').strip()[:60]}"
        for index, row in enumerate(queue_rows)
    ]
    jump_selection = st.sidebar.selectbox("Jump to paper", options=range(len(queue_rows)), format_func=jump_options.__getitem__, index=current_index)
    if jump_selection != current_index:
        st.session_state["stage04_gold_index"] = jump_selection
        st.rerun()

    nav_prev, nav_pending, nav_next = st.columns([1, 1, 1])
    with nav_prev:
        if st.button("Previous", use_container_width=True, disabled=current_index == 0):
            st.session_state["stage04_gold_index"] = current_index - 1
            st.rerun()
    with nav_pending:
        if st.button("First pending", use_container_width=True):
            st.session_state["stage04_gold_index"] = first_pending_index(snapshot_rows)
            st.rerun()
    with nav_next:
        if st.button("Next", use_container_width=True, disabled=current_index >= len(queue_rows) - 1):
            st.session_state["stage04_gold_index"] = current_index + 1
            st.rerun()

    queue_row = queue_rows[current_index]
    paper_id = (queue_row.get("paper_id") or "").strip()
    response_row = responses_by_id.get(paper_id, {})
    prediction_correct, default_category, default_count, default_alignment, default_notes = response_defaults(
        queue_row,
        response_row,
    )

    left_col, right_col = st.columns([3, 2], gap="large")
    with left_col:
        st.subheader(f"PDF: {paper_id}")
        pdf_path_relative = (queue_row.get("pdf_path_relative") or "").strip()
        pdf_path = resolve_repo_path(pdf_path_relative)
        preferred_page = max(1, int((queue_row.get("preferred_start_page") or "1").strip() or "1"))
        if pdf_path.exists():
            st.caption(f"{display_path(pdf_path)}")
            if preferred_page > 1:
                st.caption(
                    f"Suggested start page: {preferred_page}. "
                    "The in-app PDF viewer may not jump automatically, so use the page control if needed."
                )
            try:
                st.pdf(load_pdf_bytes(pdf_path_relative), height=PDF_VIEW_HEIGHT)
            except Exception as exc:  # pragma: no cover - UI fallback
                st.error(f"Could not render the PDF inline: {exc}")
        else:
            st.error(f"PDF not found: {display_path(pdf_path)}")

    with right_col:
        st.subheader("Review")
        st.markdown(f"**Title**  \n{(queue_row.get('title') or '').strip()}")
        st.markdown(f"**Authors**  \n{(queue_row.get('authors') or '').strip() or 'Unknown'}")
        st.markdown(
            f"**Selection bucket**  \n{(queue_row.get('selection_bucket') or '').strip()} | {(queue_row.get('selection_signals') or '').strip()}"
        )
        st.markdown(
            f"**Predicted**  \n"
            f"Category: `{(queue_row.get('predicted_source_category') or '').strip()}`  \n"
            f"Count: `{(queue_row.get('predicted_likely_sps_case_count') or '').strip() or '0'}`  \n"
            f"Category confidence: `{(queue_row.get('predicted_confidence') or '').strip() or 'unknown'}`  \n"
            f"Count basis: `{(queue_row.get('predicted_count_basis') or '').strip() or 'unknown'}`"
        )

        with st.form(key=f"review_form_{paper_id}"):
            prediction_correct_value = st.toggle(
                "Prediction correct",
                value=prediction_correct,
                help="Leave on to accept the prediction as-is. If you edit the fields below, the app will treat the prediction as incorrect even if this toggle stays on.",
            )
            reviewed_source_category = st.selectbox(
                "Source category",
                options=SOURCE_CATEGORY_OPTIONS,
                index=SOURCE_CATEGORY_OPTIONS.index(default_category)
                if default_category in SOURCE_CATEGORY_OPTIONS
                else 0,
            )
            reviewed_count_text = st.text_input(
                "Extractable SPS patient count",
                value=default_count or "0",
                help="Use `0` when the source is not an extractable SPS case source.",
            )
            pdf_alignment_tag = st.selectbox(
                "PDF alignment",
                options=PDF_ALIGNMENT_OPTIONS,
                index=PDF_ALIGNMENT_OPTIONS.index(default_alignment)
                if default_alignment in PDF_ALIGNMENT_OPTIONS
                else 0,
                help="Flag wrong-PDF or reference-linkage problems separately from heuristic mistakes.",
            )
            reviewer_notes = st.text_area(
                "Notes",
                value=default_notes,
                height=160,
                placeholder="Optional note about why the prediction was wrong, or why the PDF is questionable.",
            )
            reviewer_id = st.text_input(
                "Reviewer ID",
                value=(response_row.get("reviewer_id") or DEFAULT_REVIEWER).strip() or DEFAULT_REVIEWER,
            )
            save_here = st.form_submit_button("Save", use_container_width=True)
            save_next = st.form_submit_button("Save and next", type="primary", use_container_width=True)

        if save_here or save_next:
            predicted_category = (queue_row.get("predicted_source_category") or "").strip()
            predicted_count_text = normalise_count_text(queue_row.get("predicted_likely_sps_case_count") or "")
            reviewed_count_text = normalise_count_text(reviewed_count_text)
            try:
                int(reviewed_count_text)
            except ValueError:
                st.error("The reviewed count must be an integer.")
                st.stop()

            edited_prediction = (
                reviewed_source_category != predicted_category
                or reviewed_count_text != predicted_count_text
            )
            final_prediction_correct = prediction_correct_value and not edited_prediction
            final_count_text = predicted_count_text if final_prediction_correct else reviewed_count_text

            responses_by_id[paper_id] = build_response_row(
                queue_row=queue_row,
                prediction_correct=final_prediction_correct,
                reviewed_source_category=reviewed_source_category,
                reviewed_extractable_sps_case_count=final_count_text,
                pdf_content_alignment_tag=pdf_alignment_tag,
                reviewer_notes=reviewer_notes,
                reviewer_id=reviewer_id,
            )
            snapshot_rows = write_round_outputs(
                round_dir=round_dir,
                queue_rows=queue_rows,
                responses_by_id=responses_by_id,
            )
            if count_completed_reviews(snapshot_rows) == len(snapshot_rows):
                upsert_gold_master(snapshot_rows)

            if save_next and current_index < len(queue_rows) - 1:
                st.session_state["stage04_gold_index"] = current_index + 1
            else:
                st.session_state["stage04_gold_index"] = current_index
            st.rerun()


if __name__ == "__main__":
    main()
