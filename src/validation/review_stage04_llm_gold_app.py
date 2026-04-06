from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st
from streamlit_pdf_viewer import pdf_viewer

from src.validation._stage04_llm_gold import (
    DEFAULT_REVIEWER,
    GOLD_MASTER_PATH,
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
    load_text_page_entries,
    resolve_repo_path,
    round_gold_snapshot_path,
    round_label_from_directory,
    search_text_page_entries,
    upsert_gold_master,
    write_round_outputs,
)


PDF_VIEW_HEIGHT = 1000
PDF_SEARCH_RESULT_LIMIT = 12


@st.cache_data(show_spinner=False)
def load_pdf_bytes(pdf_path_text: str) -> bytes:
    pdf_path = resolve_repo_path(pdf_path_text)
    return pdf_path.read_bytes()


@st.cache_data(show_spinner=False)
def load_text_pages(text_json_path_text: str) -> list[dict[str, object]]:
    return load_text_page_entries(text_json_path_text)


def normalise_count_text(value: str) -> str:
    stripped = (value or "").strip()
    return stripped if stripped else "0"


def editor_prefix(round_id: str, paper_id: str) -> str:
    return f"stage04_llm_gold::{round_id}::{paper_id}"


def editor_key(prefix: str, suffix: str) -> str:
    return f"{prefix}::{suffix}"


def apply_prediction_values(prefix: str, queue_row: dict[str, str]) -> None:
    st.session_state[editor_key(prefix, "reviewed_source_category")] = (
        queue_row.get("predicted_source_category") or ""
    ).strip()
    st.session_state[editor_key(prefix, "reviewed_extractable_sps_case_count")] = normalise_count_text(
        queue_row.get("predicted_likely_sps_case_count") or ""
    )


def sync_prediction_lock(prefix: str, queue_row: dict[str, str]) -> None:
    if st.session_state.get(editor_key(prefix, "prediction_correct"), False):
        apply_prediction_values(prefix, queue_row)


def preferred_start_page(queue_row: dict[str, str]) -> int:
    return max(1, int((queue_row.get("preferred_start_page") or "1").strip() or "1"))


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


def ensure_editor_state(
    *,
    queue_row: dict[str, str],
    response_row: dict[str, str],
) -> str:
    round_id = (queue_row.get("round_id") or "").strip()
    paper_id = (queue_row.get("paper_id") or "").strip()
    prefix = editor_prefix(round_id, paper_id)
    active_key = "stage04_llm_gold_active_editor"
    if st.session_state.get(active_key) != prefix:
        (
            prediction_correct,
            default_category,
            default_count,
            default_alignment,
            default_notes,
        ) = response_defaults(queue_row, response_row)
        st.session_state[editor_key(prefix, "prediction_correct")] = prediction_correct
        st.session_state[editor_key(prefix, "reviewed_source_category")] = default_category
        st.session_state[editor_key(prefix, "reviewed_extractable_sps_case_count")] = default_count
        st.session_state[editor_key(prefix, "pdf_content_alignment_tag")] = default_alignment
        st.session_state[editor_key(prefix, "reviewer_notes")] = default_notes
        st.session_state[editor_key(prefix, "reviewer_id")] = (
            (response_row.get("reviewer_id") or DEFAULT_REVIEWER).strip() or DEFAULT_REVIEWER
        )
        st.session_state[editor_key(prefix, "pdf_search_query")] = ""
        st.session_state[editor_key(prefix, "pdf_view_page")] = preferred_start_page(queue_row)
        st.session_state[active_key] = prefix
    return prefix


def round_options() -> list[Path]:
    return list(reversed(discover_round_directories()))


def first_pending_index(snapshot_rows: list[dict[str, str]]) -> int:
    for index, row in enumerate(snapshot_rows):
        if (row.get("review_status") or "").strip() != "reviewed":
            return index
    return 0


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
    st.sidebar.caption(f"Cumulative gold file: `{display_path(GOLD_MASTER_PATH)}`")
    return completed


def main() -> None:
    st.set_page_config(page_title="Stage 04 LLM Gold Reviewer", layout="wide")
    st.title("Stage 04 LLM Gold Reviewer")
    st.caption("Review LLM source-category and SPS case-count predictions against the source PDF.")

    available_rounds = round_options()
    if not available_rounds:
        st.warning(
            "No LLM category-review rounds are available yet. Run "
            "`python src/validation/build_stage04_llm_gold_batch.py` first."
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

    round_state_key = "stage04_llm_gold_round"
    if st.session_state.get(round_state_key) != selected_label:
        st.session_state[round_state_key] = selected_label
        st.session_state["stage04_llm_gold_index"] = first_pending_index(snapshot_rows)

    current_index = st.session_state.get("stage04_llm_gold_index", 0)
    current_index = max(0, min(current_index, len(queue_rows) - 1))
    render_sidebar(round_dir, snapshot_rows)

    jump_options = [
        f"{index + 1}. {(row.get('paper_id') or '').strip()} | {(row.get('selection_bucket') or '').strip()} | {(row.get('title') or '').strip()[:60]}"
        for index, row in enumerate(queue_rows)
    ]
    jump_selection = st.sidebar.selectbox(
        "Jump to paper",
        options=range(len(queue_rows)),
        format_func=jump_options.__getitem__,
        index=current_index,
    )
    if jump_selection != current_index:
        st.session_state["stage04_llm_gold_index"] = jump_selection
        st.rerun()

    nav_prev, nav_pending, nav_next = st.columns([1, 1, 1])
    with nav_prev:
        if st.button("Previous", use_container_width=True, disabled=current_index == 0):
            st.session_state["stage04_llm_gold_index"] = current_index - 1
            st.rerun()
    with nav_pending:
        if st.button("First pending", use_container_width=True):
            st.session_state["stage04_llm_gold_index"] = first_pending_index(snapshot_rows)
            st.rerun()
    with nav_next:
        if st.button("Next", use_container_width=True, disabled=current_index >= len(queue_rows) - 1):
            st.session_state["stage04_llm_gold_index"] = current_index + 1
            st.rerun()

    queue_row = queue_rows[current_index]
    paper_id = (queue_row.get("paper_id") or "").strip()
    response_row = responses_by_id.get(paper_id, {})
    prefix = ensure_editor_state(
        queue_row=queue_row,
        response_row=response_row,
    )

    left_col, right_col = st.columns([3, 2], gap="large")
    with left_col:
        st.subheader(f"PDF: {paper_id}")
        pdf_path_relative = (queue_row.get("pdf_path_relative") or "").strip()
        text_json_path_relative = (queue_row.get("preferred_text_json_path") or "").strip()
        pdf_path = resolve_repo_path(pdf_path_relative)
        preferred_page = preferred_start_page(queue_row)
        pdf_view_page_key = editor_key(prefix, "pdf_view_page")
        pdf_search_query_key = editor_key(prefix, "pdf_search_query")
        if pdf_path.exists():
            st.caption(f"{display_path(pdf_path)}")
            if preferred_page > 1:
                st.caption(f"Suggested start page: {preferred_page}.")
            if text_json_path_relative:
                page_entries = load_text_pages(text_json_path_relative)
                page_count = len(page_entries)
                search_col, page_col, reset_col = st.columns([2, 1, 1])
                with search_col:
                    st.text_input(
                        "Search PDF text",
                        key=pdf_search_query_key,
                        placeholder="Enter a phrase to find matching pages",
                        help=(
                            "Search uses the paper's extracted page text and jumps the PDF viewer "
                            "to the matching page."
                        ),
                    )
                with page_col:
                    st.number_input(
                        "Page",
                        min_value=1,
                        max_value=max(page_count, preferred_page),
                        step=1,
                        key=pdf_view_page_key,
                    )
                with reset_col:
                    st.write("")
                    if st.button("Suggested page", use_container_width=True):
                        st.session_state[pdf_view_page_key] = preferred_page
                        st.rerun()

                search_query = str(st.session_state[pdf_search_query_key]).strip()
                if search_query:
                    matches = search_text_page_entries(
                        page_entries,
                        search_query,
                        max_results=PDF_SEARCH_RESULT_LIMIT,
                    )
                    if matches:
                        st.caption(
                            f"Found {sum(int(match['match_count']) for match in matches)} match(es) "
                            f"across {len(matches)} page(s)."
                        )
                        for match in matches:
                            page_num = int(match["page_num"])
                            button_label = f"Page {page_num} ({match['match_count']} hit(s))"
                            if st.button(
                                button_label,
                                key=editor_key(prefix, f"search_result::{page_num}"),
                                use_container_width=True,
                            ):
                                st.session_state[pdf_view_page_key] = page_num
                                st.rerun()
                            st.caption(str(match["snippet"]))
                    else:
                        st.info("No matching pages were found in the extracted text for this paper.")
            try:
                pdf_viewer(
                    load_pdf_bytes(pdf_path_relative),
                    key=editor_key(prefix, f"pdf_viewer::{st.session_state[pdf_view_page_key]}"),
                    width="100%",
                    height=PDF_VIEW_HEIGHT,
                    render_text=True,
                    zoom_level="auto",
                    scroll_to_page=int(st.session_state[pdf_view_page_key]),
                    scroll_behavior="instant",
                )
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
            f"Subtype: `{(queue_row.get('predicted_source_subtype') or '').strip() or 'unknown'}`  \n"
            f"Category confidence: `{(queue_row.get('predicted_confidence') or '').strip() or 'unknown'}`  \n"
            f"Count confidence: `{(queue_row.get('predicted_count_confidence') or '').strip() or 'unknown'}`  \n"
            f"Count review required: `{(queue_row.get('predicted_count_manual_review_required') or '').strip() or 'unknown'}`"
        )
        if (queue_row.get("predicted_categorisation_reason") or "").strip():
            st.markdown(
                f"**Category reasoning**  \n{(queue_row.get('predicted_categorisation_reason') or '').strip()}"
            )
        if (queue_row.get("predicted_count_reason") or "").strip():
            st.markdown(f"**Count reasoning**  \n{(queue_row.get('predicted_count_reason') or '').strip()}")

        prediction_correct_key = editor_key(prefix, "prediction_correct")
        reviewed_category_key = editor_key(prefix, "reviewed_source_category")
        reviewed_count_key = editor_key(prefix, "reviewed_extractable_sps_case_count")
        alignment_key = editor_key(prefix, "pdf_content_alignment_tag")
        notes_key = editor_key(prefix, "reviewer_notes")
        reviewer_key = editor_key(prefix, "reviewer_id")

        st.toggle(
            "Prediction correct",
            key=prediction_correct_key,
            help="When this is on, the predicted category and count are accepted and the editable fields are locked.",
            on_change=sync_prediction_lock,
            args=(prefix, queue_row),
        )
        prediction_correct_value = bool(st.session_state[prediction_correct_key])

        st.selectbox(
            "Source category",
            options=SOURCE_CATEGORY_OPTIONS,
            key=reviewed_category_key,
            disabled=prediction_correct_value,
        )
        st.text_input(
            "Extractable SPS patient count",
            key=reviewed_count_key,
            disabled=prediction_correct_value,
            help="Use `0` when the source is not an extractable SPS case source.",
        )
        st.selectbox(
            "PDF alignment",
            options=PDF_ALIGNMENT_OPTIONS,
            key=alignment_key,
            help="Flag wrong-PDF or reference-linkage problems separately from classification mistakes.",
        )
        st.text_area(
            "Notes",
            key=notes_key,
            height=160,
            placeholder="Optional note about why the prediction was wrong, or why the PDF is questionable.",
        )
        st.text_input(
            "Reviewer ID",
            key=reviewer_key,
        )

        save_col, save_next_col = st.columns(2)
        save_here = save_col.button("Save", use_container_width=True)
        save_next = save_next_col.button("Save and next", type="primary", use_container_width=True)

        if save_here or save_next:
            predicted_count_text = normalise_count_text(queue_row.get("predicted_likely_sps_case_count") or "")
            reviewed_count_text = normalise_count_text(str(st.session_state[reviewed_count_key]))
            try:
                int(predicted_count_text if prediction_correct_value else reviewed_count_text)
            except ValueError:
                st.error("The reviewed count must be an integer.")
                st.stop()

            responses_by_id[paper_id] = build_response_row(
                queue_row=queue_row,
                prediction_correct=prediction_correct_value,
                reviewed_source_category=str(st.session_state[reviewed_category_key]).strip(),
                reviewed_extractable_sps_case_count=(
                    predicted_count_text if prediction_correct_value else reviewed_count_text
                ),
                pdf_content_alignment_tag=str(st.session_state[alignment_key]).strip(),
                reviewer_notes=str(st.session_state[notes_key]).strip(),
                reviewer_id=str(st.session_state[reviewer_key]).strip(),
            )
            snapshot_rows = write_round_outputs(
                round_dir=round_dir,
                queue_rows=queue_rows,
                responses_by_id=responses_by_id,
            )
            if count_completed_reviews(snapshot_rows) == len(snapshot_rows):
                upsert_gold_master(snapshot_rows)

            if save_next and current_index < len(queue_rows) - 1:
                st.session_state["stage04_llm_gold_index"] = current_index + 1
            else:
                st.session_state["stage04_llm_gold_index"] = current_index
            st.rerun()


if __name__ == "__main__":
    main()
