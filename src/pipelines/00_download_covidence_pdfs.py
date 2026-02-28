from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright
except ImportError:  # pragma: no cover - handled at runtime
    Locator = Any  # type: ignore[assignment]
    Page = Any  # type: ignore[assignment]
    PlaywrightTimeoutError = TimeoutError
    sync_playwright = None


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REVIEW_URL = "https://app.covidence.org/reviews/128778/extraction/index"
DEFAULT_DOWNLOAD_DIR = REPO_ROOT / "data" / "pdf_original"
DEFAULT_STATE_PATH = REPO_ROOT / "data" / "extraction_json" / "covidence" / "playwright_state.json"
DEFAULT_MANIFEST_PATH = REPO_ROOT / "data" / "extraction_json" / "covidence" / "download_manifest.jsonl"
DEFAULT_LOGIN_ENV_PATH = REPO_ROOT / "env" / "covidence_login.env"
DEFAULT_REGISTRY_SCRIPT_PATH = REPO_ROOT / "src" / "pipelines" / "00_build_pdf_source_registry.py"
DEFAULT_ARTIFACT_REGISTRY_SCRIPT_PATH = REPO_ROOT / "src" / "pipelines" / "00_build_paper_artifact_registry.py"

PDF_LINK_TEXT_RE = re.compile(r"\.pdf\b", re.IGNORECASE)
PDF_HREF_RE = re.compile(r"(\.pdf\b|application%2fpdf)", re.IGNORECASE)
WINDOWS_INVALID_CHARS_RE = re.compile(r'[<>:"/\\|?*]')
REFERENCE_ID_RE = re.compile(r"#\s*\d{2,}")


@dataclass
class ReferenceCard:
    tag: str
    covidence_id: str
    label: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download Covidence full-text PDFs from the extraction view."
    )
    parser.add_argument(
        "--review-url",
        default=DEFAULT_REVIEW_URL,
        help="Covidence extraction page URL.",
    )
    parser.add_argument(
        "--download-dir",
        type=Path,
        default=DEFAULT_DOWNLOAD_DIR,
        help="Directory where PDFs should be saved.",
    )
    parser.add_argument(
        "--state-path",
        type=Path,
        default=DEFAULT_STATE_PATH,
        help="Path to the saved Playwright storage state JSON.",
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="JSONL manifest written after each attempted download.",
    )
    parser.add_argument(
        "--login-env-path",
        type=Path,
        default=DEFAULT_LOGIN_ENV_PATH,
        help="Optional .env-style file containing COVIDENCE_EMAIL and COVIDENCE_PASSWORD.",
    )
    parser.add_argument(
        "--email",
        default="",
        help="Covidence login email. Defaults to COVIDENCE_EMAIL if set.",
    )
    parser.add_argument(
        "--password",
        default="",
        help="Covidence login password. Defaults to COVIDENCE_PASSWORD if set.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Maximum number of references to process.")
    parser.add_argument(
        "--only-id",
        action="append",
        default=[],
        help="Specific Covidence ID to process. Repeat the flag for multiple IDs.",
    )
    parser.add_argument("--overwrite", action="store_true", help="Redownload IDs already present on disk.")
    parser.add_argument("--headless", action="store_true", help="Run Chromium in headless mode.")
    parser.add_argument("--slow-mo", type=int, default=0, help="Playwright slow motion delay in milliseconds.")
    parser.add_argument("--timeout-ms", type=int, default=15000, help="General UI timeout in milliseconds.")
    parser.add_argument(
        "--download-timeout-ms",
        type=int,
        default=30000,
        help="Timeout for the PDF reveal and file download steps.",
    )
    parser.add_argument(
        "--settle-ms",
        type=int,
        default=1200,
        help="Short pause after major UI actions to let Covidence render.",
    )
    parser.add_argument(
        "--skip-registry-refresh",
        action="store_true",
        help="Do not rebuild data/references/pdf_source_registry.csv after the download run.",
    )
    return parser.parse_args()


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_runtime_dirs(args: argparse.Namespace) -> None:
    args.download_dir.mkdir(parents=True, exist_ok=True)
    args.state_path.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_path.parent.mkdir(parents=True, exist_ok=True)


def manifest_append(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def refresh_pdf_source_registry(skip_refresh: bool) -> None:
    if skip_refresh:
        return
    subprocess.run(
        [sys.executable, str(DEFAULT_REGISTRY_SCRIPT_PATH)],
        check=True,
        cwd=str(REPO_ROOT),
    )
    subprocess.run(
        [sys.executable, str(DEFAULT_ARTIFACT_REGISTRY_SCRIPT_PATH)],
        check=True,
        cwd=str(REPO_ROOT),
    )


def sanitize_filename(filename: str) -> str:
    cleaned = WINDOWS_INVALID_CHARS_RE.sub("_", filename).strip().rstrip(".")
    if not cleaned.lower().endswith(".pdf"):
        cleaned = f"{cleaned}.pdf"
    return cleaned or "document.pdf"


def existing_pdf_for_id(download_dir: Path, covidence_id: str) -> Path | None:
    matches = sorted(download_dir.glob(f"{covidence_id}_*.pdf"))
    return matches[0] if matches else None


def load_simple_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def collect_credentials(args: argparse.Namespace) -> tuple[str, str]:
    file_values = load_simple_env_file(args.login_env_path)
    email = (
        (args.email or "").strip()
        or (os.environ.get("COVIDENCE_EMAIL") or "").strip()
        or file_values.get("COVIDENCE_EMAIL", "").strip()
    )
    password = (
        (args.password or "").strip()
        or (os.environ.get("COVIDENCE_PASSWORD") or "").strip()
        or file_values.get("COVIDENCE_PASSWORD", "").strip()
    )
    return email, password


def maybe_first_visible(locator: Locator, limit: int = 5) -> Locator | None:
    count = min(locator.count(), limit)
    for index in range(count):
        candidate = locator.nth(index)
        try:
            if candidate.is_visible():
                return candidate
        except Exception:
            continue
    return None


def visible_named_control(scope: Page | Locator, role: str, pattern: str) -> Locator | None:
    locator = scope.get_by_role(role, name=re.compile(pattern, re.IGNORECASE))
    return maybe_first_visible(locator)


def first_visible_control(scope: Page | Locator, role_patterns: list[tuple[str, str]]) -> Locator | None:
    for role, pattern in role_patterns:
        candidate = visible_named_control(scope, role, pattern)
        if candidate is not None:
            return candidate
    return None


def control_disabled(locator: Locator) -> bool:
    attributes = [
        locator.get_attribute("disabled"),
        locator.get_attribute("aria-disabled"),
        locator.get_attribute("class"),
    ]
    disabled_tokens = [value.lower() for value in attributes if value]
    return any(token == "true" or "disabled" in token for token in disabled_tokens)


def scroll_page(page: Page, settle_ms: int) -> None:
    previous_height = -1
    for _ in range(8):
        height = page.evaluate("document.body.scrollHeight")
        if height == previous_height:
            break
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(settle_ms)
        previous_height = height
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(max(200, settle_ms // 2))


def extraction_list_ready(page: Page) -> bool:
    try:
        body_text = page.locator("body").inner_text(timeout=2000)
    except Exception:
        return False
    return "View full text" in body_text and bool(REFERENCE_ID_RE.search(body_text))


def wait_for_reference_list(page: Page, timeout_ms: int, settle_ms: int) -> None:
    deadline = time.time() + (timeout_ms / 1000)
    while time.time() < deadline:
        if extraction_list_ready(page):
            return
        page.wait_for_timeout(settle_ms)
    raise RuntimeError("Covidence extraction list did not finish rendering in time.")


def discover_reference_cards(page: Page) -> list[ReferenceCard]:
    raw_cards = page.evaluate(
        """
        () => {
          const controls = Array.from(document.querySelectorAll("button, a")).filter((el) => {
            const text = (el.innerText || "").trim();
            return /view full text/i.test(text);
          });
          const seen = new Set();
          let counter = 0;

          function pickLabel(lines) {
            const ignore = [
              /^#\\s*\\d+/i,
              /^view full text$/i,
              /\\.pdf$/i,
              /^\\d{4}$/i,
            ];
            for (const line of lines) {
              if (!line) {
                continue;
              }
              if (ignore.some((pattern) => pattern.test(line))) {
                continue;
              }
              return line.slice(0, 240);
            }
            return "";
          }

          const cards = [];
          for (const control of controls) {
            let container = null;
            let covidenceId = null;
            for (let node = control.parentElement; node; node = node.parentElement) {
              const text = (node.innerText || "").trim();
              const match = text.match(/#\\s*(\\d{2,})\\b/);
              if (!match) {
                continue;
              }
              container = node;
              covidenceId = match[1];
              if (text.length <= 12000) {
                break;
              }
            }
            if (!container || !covidenceId || seen.has(covidenceId)) {
              continue;
            }
            seen.add(covidenceId);
            counter += 1;
            const tag = `codex-covidence-ref-${counter}`;
            container.setAttribute("data-codex-ref-card", tag);
            const lines = (container.innerText || "")
              .split(/\\r?\\n/)
              .map((line) => line.trim())
              .filter(Boolean);
            cards.push({
              tag,
              covidence_id: covidenceId,
              label: pickLabel(lines),
            });
          }
          return cards;
        }
        """
    )
    return [
        ReferenceCard(
            tag=item["tag"],
            covidence_id=item["covidence_id"],
            label=item.get("label", ""),
        )
        for item in raw_cards
    ]


def pdf_link_details(link: Locator, page_url: str) -> tuple[str, str]:
    text = (link.inner_text() or "").strip()
    href = (link.get_attribute("href") or "").strip()
    absolute_url = urllib.parse.urljoin(page_url, href)

    filename = text
    if not PDF_LINK_TEXT_RE.search(filename):
        parsed = urllib.parse.urlparse(absolute_url)
        filename = urllib.parse.unquote(Path(parsed.path).name)
    return sanitize_filename(filename), absolute_url


def is_pdf_link_candidate(text: str, href: str) -> bool:
    return bool(PDF_LINK_TEXT_RE.search(text) or PDF_HREF_RE.search(href))


def wait_for_pdf_link(page: Page, card: Locator, page_url: str, timeout_ms: int) -> tuple[Locator, str, str]:
    deadline = time.time() + (timeout_ms / 1000)
    while time.time() < deadline:
        preferred_scopes = [
            card.locator("li[class*='Documents-module__documentContainer'] a"),
            card.locator("a[class*='Documents-module__link']"),
            card.locator("a"),
        ]
        for anchors in preferred_scopes:
            count = min(anchors.count(), 20)
            for index in range(count):
                link = anchors.nth(index)
                try:
                    text = (link.inner_text() or "").strip()
                    href = (link.get_attribute("href") or "").strip()
                    if is_pdf_link_candidate(text, href):
                        filename, url = pdf_link_details(link, page_url)
                        return link, filename, url
                except Exception:
                    continue
        page.wait_for_timeout(250)
    raise RuntimeError("Timed out waiting for the PDF link to appear.")


def cookie_header(page: Page, url: str) -> str:
    cookies = page.context.cookies([url])
    return "; ".join(f"{cookie['name']}={cookie['value']}" for cookie in cookies)


def fetch_pdf(page: Page, url: str, target_path: Path, timeout_ms: int) -> None:
    headers = {
        "Accept": "application/pdf,application/octet-stream,*/*",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
        ),
    }
    cookie_value = cookie_header(page, url)
    if cookie_value:
        headers["Cookie"] = cookie_value

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=max(5, timeout_ms / 1000)) as response:
            payload = response.read()
            content_type = response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:  # pragma: no cover - depends on external service
        raise RuntimeError(f"HTTP {exc.code} while downloading {url}") from exc
    except urllib.error.URLError as exc:  # pragma: no cover - depends on external service
        raise RuntimeError(f"Network error while downloading {url}: {exc.reason}") from exc

    if not payload.startswith(b"%PDF") and "pdf" not in content_type.lower():
        raise RuntimeError(f"Downloaded payload was not a PDF: {url}")
    target_path.write_bytes(payload)


def download_via_browser(page: Page, link: Locator, target_path: Path, timeout_ms: int) -> None:
    with page.expect_download(timeout=timeout_ms) as download_info:
        link.click(timeout=timeout_ms)
    download = download_info.value
    download.save_as(str(target_path))


def active_login_form(page: Page) -> bool:
    password_inputs = page.locator("input[type='password']")
    return password_inputs.count() > 0 and password_inputs.first.is_visible()


def ensure_login(page: Page, args: argparse.Namespace) -> None:
    page.goto(args.review_url, wait_until="domcontentloaded")
    page.wait_for_timeout(args.settle_ms)

    if not active_login_form(page):
        return

    email, password = collect_credentials(args)
    if not email:
        email = input("Covidence email: ").strip()
    if not password:
        password = getpass.getpass("Covidence password: ")

    email_input = maybe_first_visible(page.locator("input[type='email'], input[name*='email' i], input[id*='email' i]"))
    password_input = maybe_first_visible(page.locator("input[type='password']"))
    if email_input is None or password_input is None:
        raise SystemExit("Could not find the Covidence login form fields.")

    email_input.fill(email, timeout=args.timeout_ms)
    password_input.fill(password, timeout=args.timeout_ms)

    submit = first_visible_control(
        page,
        [
            ("button", r"^(log in|sign in|continue)$"),
            ("button", r"(log in|sign in|continue)"),
            ("link", r"^(log in|sign in|continue)$"),
        ],
    )
    if submit is None:
        password_input.press("Enter")
    else:
        submit.click(timeout=args.timeout_ms)

    page.wait_for_timeout(args.settle_ms * 2)
    page.goto(args.review_url, wait_until="domcontentloaded")
    page.wait_for_timeout(args.settle_ms)

    if active_login_form(page):
        raise SystemExit("Covidence login did not complete successfully.")

    wait_for_reference_list(
        page,
        timeout_ms=max(args.download_timeout_ms, 45000),
        settle_ms=args.settle_ms,
    )


def click_view_full_text(card: Locator, timeout_ms: int) -> None:
    control = first_visible_control(
        card,
        [
            ("button", r"^view full text$"),
            ("link", r"^view full text$"),
            ("button", r"view full text"),
            ("link", r"view full text"),
        ],
    )
    if control is None:
        return
    control.scroll_into_view_if_needed(timeout=timeout_ms)
    control.click(timeout=timeout_ms)


def next_page_control(page: Page) -> Locator | None:
    candidates = [
        ("button", r"^next$"),
        ("link", r"^next$"),
        ("button", r"next"),
        ("link", r"next"),
    ]
    for role, pattern in candidates:
        control = visible_named_control(page, role, pattern)
        if control is not None and not control_disabled(control):
            return control

    locator = page.locator("[rel='next'], [aria-label*='next' i]")
    control = maybe_first_visible(locator)
    if control is not None and not control_disabled(control):
        return control
    return None


def process_reference(page: Page, args: argparse.Namespace, card_info: ReferenceCard) -> dict[str, Any]:
    started_at = now_utc_iso()
    card = page.locator(f"[data-codex-ref-card='{card_info.tag}']").first
    card.scroll_into_view_if_needed(timeout=args.timeout_ms)

    existing = existing_pdf_for_id(args.download_dir, card_info.covidence_id)
    if existing is not None and not args.overwrite:
        return {
            "covidence_id": card_info.covidence_id,
            "label": card_info.label,
            "status": "skipped_existing",
            "saved_path": str(existing),
            "source_filename": existing.name[len(card_info.covidence_id) + 1 :],
            "download_url": "",
            "error": "",
            "started_at_utc": started_at,
            "finished_at_utc": now_utc_iso(),
        }

    click_view_full_text(card, args.timeout_ms)
    page.wait_for_timeout(args.settle_ms)

    link, source_filename, download_url = wait_for_pdf_link(page, card, page.url, args.download_timeout_ms)
    target_path = args.download_dir / f"{card_info.covidence_id}_{source_filename}"

    try:
        fetch_pdf(page, download_url, target_path, args.download_timeout_ms)
        method = "direct_fetch"
    except Exception:
        download_via_browser(page, link, target_path, args.download_timeout_ms)
        method = "browser_download"

    if not target_path.exists():
        raise RuntimeError("Download reported success but the PDF was not saved.")

    return {
        "covidence_id": card_info.covidence_id,
        "label": card_info.label,
        "status": "downloaded",
        "saved_path": str(target_path),
        "source_filename": source_filename,
        "download_url": download_url,
        "method": method,
        "error": "",
        "started_at_utc": started_at,
        "finished_at_utc": now_utc_iso(),
    }


def should_process(card_info: ReferenceCard, args: argparse.Namespace) -> bool:
    if args.only_id:
        wanted = {value.strip() for value in args.only_id if value.strip()}
        return card_info.covidence_id in wanted
    return True


def iterate_review(page: Page, args: argparse.Namespace) -> list[dict[str, Any]]:
    processed_ids: set[str] = set()
    manifest_rows: list[dict[str, Any]] = []

    while True:
        wait_for_reference_list(
            page,
            timeout_ms=max(args.download_timeout_ms, 45000),
            settle_ms=args.settle_ms,
        )
        scroll_page(page, args.settle_ms)
        cards = discover_reference_cards(page)
        if not cards:
            raise RuntimeError("No reference cards with 'View full text' controls were found on the page.")

        for card_info in cards:
            if card_info.covidence_id in processed_ids:
                continue
            if not should_process(card_info, args):
                processed_ids.add(card_info.covidence_id)
                continue
            if args.limit and len(manifest_rows) >= args.limit:
                return manifest_rows

            try:
                row = process_reference(page, args, card_info)
            except Exception as exc:
                row = {
                    "covidence_id": card_info.covidence_id,
                    "label": card_info.label,
                    "status": "failed",
                    "saved_path": "",
                    "source_filename": "",
                    "download_url": "",
                    "error": str(exc),
                    "started_at_utc": now_utc_iso(),
                    "finished_at_utc": now_utc_iso(),
                }
            manifest_append(args.manifest_path, row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
            manifest_rows.append(row)
            processed_ids.add(card_info.covidence_id)

        next_control = next_page_control(page)
        if next_control is None:
            break

        seen_before = sorted(processed_ids)
        next_control.scroll_into_view_if_needed(timeout=args.timeout_ms)
        next_control.click(timeout=args.timeout_ms)
        page.wait_for_timeout(args.settle_ms * 2)

        new_cards = discover_reference_cards(page)
        new_ids = [card.covidence_id for card in new_cards]
        if new_ids and all(covidence_id in seen_before for covidence_id in new_ids):
            break

    return manifest_rows


def main() -> None:
    if sync_playwright is None:
        raise SystemExit(
            "Playwright is not installed. Install it with "
            "'.venv\\Scripts\\python.exe -m pip install playwright' and then "
            "'.venv\\Scripts\\python.exe -m playwright install chromium'."
        )

    args = parse_args()
    ensure_runtime_dirs(args)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=args.headless, slow_mo=args.slow_mo)
        context_options: dict[str, Any] = {"accept_downloads": True}
        if args.state_path.exists():
            context_options["storage_state"] = str(args.state_path)
        context = browser.new_context(**context_options)
        page = context.new_page()
        page.set_default_timeout(args.timeout_ms)

        ensure_login(page, args)
        iterate_review(page, args)

        context.storage_state(path=str(args.state_path))
        context.close()
        browser.close()

    refresh_pdf_source_registry(args.skip_registry_refresh)


if __name__ == "__main__":
    main()
