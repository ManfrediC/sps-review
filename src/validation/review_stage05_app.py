from __future__ import annotations

import json
from pathlib import Path

import streamlit as st
from streamlit_pdf_viewer import pdf_viewer

from src.validation import _stage05_review as review


PDF_VIEW_HEIGHT = 1000
PDF_SEARCH_RESULT_LIMIT = 12
PDF_ZOOM_MIN = 0.5
PDF_ZOOM_MAX = 3.0
PDF_ZOOM_STEP = 0.25
PDF_DEFAULT_ZOOM = 1.0


@st.cache_data(show_spinner=False)
def load_pdf_bytes(pdf_path_text: str) -> bytes:
    return review.resolve_repo_path(pdf_path_text).read_bytes()


@st.cache_data(show_spinner=False)
def load_text_pages(text_json_path_text: str) -> list[dict[str, object]]:
    return review.load_text_page_entries(text_json_path_text)


@st.cache_data(show_spinner=False)
def load_trimmed_preview(trimmed_text_json_path_text: str) -> str:
    trimmed_path = review.resolve_repo_path(trimmed_text_json_path_text)
    if not trimmed_path.exists():
        return ""
    payload = json.loads(trimmed_path.read_text(encoding="utf-8"))
    preview_lines: list[str] = []
    for page in payload.get("pages") or []:
        page_text = str(page.get("text") or "").strip()
        if not page_text:
            continue
        preview_lines.extend(line.strip() for line in page_text.splitlines() if line.strip())
        if len(preview_lines) >= 24:
            break
    return "\n".join(preview_lines[:24])


def editor_prefix(batch_id: str, paper_id: str) -> str:
    return f"stage05_review::{batch_id}::{paper_id}"


def editor_key(prefix: str, suffix: str) -> str:
    return f"{prefix}::{suffix}"


def available_report_dirs() -> list[Path]:
    if not review.REPORTS_DIR.exists():
        return []
    candidates = [path for path in review.REPORTS_DIR.iterdir() if path.is_dir() and path.name.startswith("batch_")]
    return sorted(
        [path for path in candidates if (path / "batch_report.json").exists()],
        key=lambda path: path.name,
        reverse=True,
    )


def response_defaults(queue_row: dict[str, str], response_row: dict[str, str]) -> tuple[bool, str, str, str]:
    return review.response_defaults(queue_row, response_row)


def ensure_editor_state(
    *,
    queue_row: dict[str, str],
    response_row: dict[str, str],
) -> str:
    batch_id = str(queue_row.get("batch_id") or "").strip()
    paper_id = str(queue_row.get("paper_id") or "").strip()
    prefix = editor_prefix(batch_id, paper_id)
    active_key = "stage05_active_editor"
    if st.session_state.get(active_key) != prefix:
        extraction_correct, corrected_start, corrected_end, reviewer_comments = response_defaults(queue_row, response_row)
        st.session_state[editor_key(prefix, "extraction_correct")] = extraction_correct
        st.session_state[editor_key(prefix, "corrected_start_text")] = corrected_start
        st.session_state[editor_key(prefix, "corrected_end_text")] = corrected_end
        st.session_state[editor_key(prefix, "reviewer_comments")] = reviewer_comments
        st.session_state[editor_key(prefix, "reviewer_id")] = (
            str(response_row.get("reviewer_id") or review.DEFAULT_REVIEWER).strip() or review.DEFAULT_REVIEWER
        )
        st.session_state[editor_key(prefix, "pdf_search_query")] = ""
        st.session_state[editor_key(prefix, "pdf_view_page")] = max(
            1,
            review.parse_int(queue_row.get("preferred_start_page"), default=1),
        )
        st.session_state[editor_key(prefix, "pdf_zoom_level")] = PDF_DEFAULT_ZOOM
        st.session_state[active_key] = prefix
    return prefix


def first_pending_index(queue_rows: list[dict[str, str]], responses_by_id: dict[str, dict[str, str]]) -> int:
    for index, row in enumerate(queue_rows):
        paper_id = str(row.get("paper_id") or "").strip()
        response_row = responses_by_id.get(paper_id, {})
        if (response_row.get("review_status") or "").strip() != "reviewed":
            return index
    return 0


def render_sidebar(
    report_dir: Path,
    queue_rows: list[dict[str, str]],
    responses_by_id: dict[str, dict[str, str]],
) -> None:
    completed = review.count_completed_reviews(queue_rows, responses_by_id)
    total = len(queue_rows)
    st.sidebar.subheader("Batch progress")
    st.sidebar.progress(completed / total if total else 0.0, text=f"{completed} of {total} reviewed")
    if total:
        pending_ids = [
            str(row.get("paper_id") or "").strip()
            for row in queue_rows
            if (responses_by_id.get(str(row.get("paper_id") or "").strip(), {}).get("review_status") or "").strip() != "reviewed"
        ]
        if pending_ids:
            st.sidebar.caption(f"Pending: {', '.join(pending_ids[:5])}{' ...' if len(pending_ids) > 5 else ''}")
        else:
            st.sidebar.success("Batch review complete. Feedback and acceptance files are up to date.")

    acceptance_path = review.acceptance_report_path(report_dir)
    if acceptance_path.exists():
        payload = json.loads(acceptance_path.read_text(encoding="utf-8"))
        st.sidebar.caption(
            f"Acceptance: {payload.get('passed_count', 0)} passed / {payload.get('failed_count', 0)} failed"
        )

    st.sidebar.caption(f"Queue: `{review.display_path(review.review_queue_path(report_dir))}`")
    st.sidebar.caption(f"Responses: `{review.display_path(review.responses_path(report_dir))}`")
    st.sidebar.caption(f"Feedback: `{review.display_path(review.feedback_path(report_dir))}`")
    st.sidebar.caption(f"Overrides: `{review.display_path(review.manual_overrides_path(report_dir))}`")


def refresh_report_dir(report_dir: Path) -> dict[str, object]:
    batch_id = report_dir.name
    return review.refresh_review_materials(
        batch_id=batch_id,
        report_dir=report_dir,
    )


def set_session_value(key: str, value: int | str | bool) -> None:
    st.session_state[key] = value


def clamp_zoom_level(value: float) -> float:
    return max(PDF_ZOOM_MIN, min(PDF_ZOOM_MAX, round(value, 2)))


def adjust_zoom_level(key: str, delta: float) -> None:
    current = float(st.session_state.get(key, PDF_DEFAULT_ZOOM))
    st.session_state[key] = clamp_zoom_level(current + delta)


def main() -> None:
    st.set_page_config(page_title="Stage 05 Review App", layout="wide")
    st.title("Stage 05 Review App")
    st.caption("Review proceedings trimming against the source PDF and save feedback immediately.")

    report_dirs = available_report_dirs()
    if not report_dirs:
        st.warning(
            "No stage-05 batch reports are available yet. Run "
            "`python src/validation/manage_trimming_batches.py` first."
        )
        return

    labels = {report_dir.name: report_dir for report_dir in report_dirs}
    selected_label = st.sidebar.selectbox("Batch", options=list(labels.keys()))
    report_dir = labels[selected_label]

    if not review.review_queue_path(report_dir).exists():
        refresh_report_dir(report_dir)

    queue_rows = review.load_review_queue_rows(report_dir)
    responses_by_id = review.load_responses_by_id(report_dir)
    if not queue_rows:
        st.error(f"No review queue rows were found in {review.display_path(report_dir)}.")
        return

    round_state_key = "stage05_review_batch"
    if st.session_state.get(round_state_key) != selected_label:
        st.session_state[round_state_key] = selected_label
        st.session_state["stage05_review_index"] = first_pending_index(queue_rows, responses_by_id)

    current_index = st.session_state.get("stage05_review_index", 0)
    current_index = max(0, min(current_index, len(queue_rows) - 1))
    render_sidebar(report_dir, queue_rows, responses_by_id)

    jump_options = [
        f"{index + 1}. {(row.get('paper_id') or '').strip()} | {(row.get('trim_status') or '').strip()} | {(row.get('title') or '').strip()[:60]}"
        for index, row in enumerate(queue_rows)
    ]
    jump_selection = st.sidebar.selectbox(
        "Jump to paper",
        options=range(len(queue_rows)),
        format_func=jump_options.__getitem__,
        index=current_index,
    )
    if jump_selection != current_index:
        st.session_state["stage05_review_index"] = jump_selection
        st.rerun()

    nav_prev, nav_pending, nav_next = st.columns([1, 1, 1])
    with nav_prev:
        if st.button("Previous", use_container_width=True, disabled=current_index == 0):
            st.session_state["stage05_review_index"] = current_index - 1
            st.rerun()
    with nav_pending:
        if st.button("First pending", use_container_width=True):
            st.session_state["stage05_review_index"] = first_pending_index(queue_rows, responses_by_id)
            st.rerun()
    with nav_next:
        if st.button("Next", use_container_width=True, disabled=current_index >= len(queue_rows) - 1):
            st.session_state["stage05_review_index"] = current_index + 1
            st.rerun()

    queue_row = queue_rows[current_index]
    paper_id = str(queue_row.get("paper_id") or "").strip()
    response_row = responses_by_id.get(paper_id, {})
    prefix = ensure_editor_state(queue_row=queue_row, response_row=response_row)

    left_col, right_col = st.columns([3, 2], gap="large")
    with left_col:
        st.subheader(f"PDF: {paper_id}")
        pdf_path_relative = str(queue_row.get("pdf_path_relative") or "").strip()
        text_json_path_relative = str(queue_row.get("source_text_json_path") or "").strip()
        preferred_page = max(1, review.parse_int(queue_row.get("preferred_start_page"), default=1))
        pdf_view_page_key = editor_key(prefix, "pdf_view_page")
        pdf_search_query_key = editor_key(prefix, "pdf_search_query")
        pdf_zoom_level_key = editor_key(prefix, "pdf_zoom_level")
        if pdf_path_relative:
            pdf_path = review.resolve_repo_path(pdf_path_relative)
        else:
            pdf_path = Path()

        if pdf_path_relative and pdf_path.exists():
            st.caption(f"{review.display_path(pdf_path)}")
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
                        help="Search uses the extracted full-text JSON and jumps the PDF viewer to matching pages.",
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
                    st.button(
                        "Suggested page",
                        use_container_width=True,
                        on_click=set_session_value,
                        args=(pdf_view_page_key, preferred_page),
                    )

                search_query = str(st.session_state[pdf_search_query_key]).strip()
                if search_query:
                    matches = review.search_text_page_entries(
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
                                on_click=set_session_value,
                                args=(pdf_view_page_key, page_num),
                            ):
                                pass
                            st.caption(str(match["snippet"]))
                    else:
                        st.info("No matching pages were found in the extracted text for this paper.")
            zoom_down_col, zoom_slider_col, zoom_up_col, zoom_reset_col = st.columns([1, 2, 1, 1])
            with zoom_down_col:
                st.write("")
                st.button(
                    "Zoom -",
                    use_container_width=True,
                    key=editor_key(prefix, "zoom_down"),
                    on_click=adjust_zoom_level,
                    args=(pdf_zoom_level_key, -PDF_ZOOM_STEP),
                )
            with zoom_slider_col:
                st.slider(
                    "Zoom",
                    min_value=PDF_ZOOM_MIN,
                    max_value=PDF_ZOOM_MAX,
                    value=float(st.session_state[pdf_zoom_level_key]),
                    step=PDF_ZOOM_STEP,
                    key=pdf_zoom_level_key,
                    help="Keeps the viewer frame fixed and zooms the PDF inside it.",
                )
            with zoom_up_col:
                st.write("")
                st.button(
                    "Zoom +",
                    use_container_width=True,
                    key=editor_key(prefix, "zoom_up"),
                    on_click=adjust_zoom_level,
                    args=(pdf_zoom_level_key, PDF_ZOOM_STEP),
                )
            with zoom_reset_col:
                st.write("")
                st.button(
                    "100%",
                    use_container_width=True,
                    key=editor_key(prefix, "zoom_reset"),
                    on_click=set_session_value,
                    args=(pdf_zoom_level_key, PDF_DEFAULT_ZOOM),
                )
            st.caption(f"Current zoom: {int(round(float(st.session_state[pdf_zoom_level_key]) * 100))}%")
            try:
                pdf_viewer(
                    load_pdf_bytes(pdf_path_relative),
                    key=editor_key(
                        prefix,
                        f"pdf_viewer::{st.session_state[pdf_view_page_key]}::{st.session_state[pdf_zoom_level_key]}",
                    ),
                    width="100%",
                    height=PDF_VIEW_HEIGHT,
                    render_text=False,
                    resolution_boost=2,
                    zoom_level=float(st.session_state[pdf_zoom_level_key]),
                    viewer_align="left",
                    scroll_to_page=int(st.session_state[pdf_view_page_key]),
                    scroll_behavior="instant",
                )
            except Exception as exc:  # pragma: no cover - UI fallback
                st.error(f"Could not render the PDF inline: {exc}")
        else:
            st.error(f"PDF not found: {review.display_path(pdf_path) if pdf_path_relative else 'missing PDF path'}")

    with right_col:
        st.subheader("Review")
        st.markdown(f"**Title**  \n{str(queue_row.get('title') or '').strip()}")
        st.markdown(f"**Authors**  \n{str(queue_row.get('authors') or '').strip() or 'Unknown'}")
        st.markdown(
            f"**Current status**  \n"
            f"Workflow: `{str(queue_row.get('workflow_stage') or '').strip()}`  \n"
            f"Trim: `{str(queue_row.get('trim_status') or '').strip() or 'unknown'}`  \n"
            f"QC: `{str(queue_row.get('qc_status') or '').strip() or 'unknown'}`  \n"
            f"Manual follow-up: `{str(queue_row.get('manual_follow_up_required') or '').strip() or 'unknown'}`"
        )
        if str(queue_row.get("trim_reason") or "").strip():
            st.markdown(f"**Trim note**  \n{str(queue_row.get('trim_reason') or '').strip()}")
        if str(queue_row.get("qc_note") or "").strip():
            st.markdown(f"**QC note**  \n{str(queue_row.get('qc_note') or '').strip()}")

        trimmed_preview = ""
        trimmed_text_json_path = str(queue_row.get("trimmed_text_json_path") or "").strip()
        if trimmed_text_json_path:
            trimmed_preview = load_trimmed_preview(trimmed_text_json_path)
        st.text_area(
            "Current trimmed abstract preview",
            value=trimmed_preview or "No trimmed abstract is currently stored for this paper.",
            height=260,
            disabled=True,
        )

        extraction_correct_key = editor_key(prefix, "extraction_correct")
        corrected_start_key = editor_key(prefix, "corrected_start_text")
        corrected_end_key = editor_key(prefix, "corrected_end_text")
        comments_key = editor_key(prefix, "reviewer_comments")
        reviewer_key = editor_key(prefix, "reviewer_id")

        st.checkbox(
            "Extraction correct",
            key=extraction_correct_key,
            help="Tick this when the current stage-05 outcome is correct for this paper.",
        )
        extraction_correct = bool(st.session_state[extraction_correct_key])

        st.text_input(
            "Correct beginning of abstract",
            key=corrected_start_key,
            disabled=extraction_correct,
        )
        st.text_input(
            "Correct end of abstract",
            key=corrected_end_key,
            disabled=extraction_correct,
        )
        st.text_area(
            "Comments / suggestions for patching",
            key=comments_key,
            height=160,
            disabled=extraction_correct,
            placeholder="Describe the shared failure mode or the paper-specific issue if the extraction is wrong.",
        )
        st.text_input(
            "Reviewer ID",
            key=reviewer_key,
        )

        save_col, save_next_col = st.columns(2)
        save_here = save_col.button("Save", use_container_width=True)
        save_next = save_next_col.button("Save and next", type="primary", use_container_width=True)

        if save_here or save_next:
            corrected_start_text = str(st.session_state[corrected_start_key]).strip()
            corrected_end_text = str(st.session_state[corrected_end_key]).strip()
            reviewer_comments = str(st.session_state[comments_key]).strip()
            if not extraction_correct and not any([corrected_start_text, corrected_end_text, reviewer_comments]):
                st.error("Add at least one correction field or a comment before saving an incorrect extraction.")
                st.stop()

            response_row = review.build_response_row(
                queue_row=queue_row,
                extraction_correct=extraction_correct,
                corrected_start_text=corrected_start_text,
                corrected_end_text=corrected_end_text,
                reviewer_comments=reviewer_comments,
                reviewer_id=str(st.session_state[reviewer_key]).strip(),
                existing_row=response_row,
            )
            review.save_response_row(report_dir, response_row)
            refreshed = review.refresh_review_materials(
                batch_id=str(queue_row.get("batch_id") or "").strip(),
                report_dir=report_dir,
            )
            responses_by_id = refreshed["responses_by_id"]

            if save_next and current_index < len(queue_rows) - 1:
                st.session_state["stage05_review_index"] = current_index + 1
            else:
                st.session_state["stage05_review_index"] = current_index
            st.rerun()


if __name__ == "__main__":
    main()
