# Covidence Download Agent

## Purpose

This project needs all full-text PDFs in `data/pdf_original/`, but the review content currently lives inside Covidence. The download agent automates the repetitive browser workflow required to open each reference, reveal its full-text link, and save the PDF locally.

## Script

`src/pipelines/00_download_covidence_pdfs.py`

## What it does

1. Opens the Covidence extraction page in Chromium.
2. Signs in using runtime credentials or a saved browser session.
3. Finds each reference block that exposes a `View full text` control.
4. Extracts the Covidence ID from the visible `#<id>` header.
5. Reveals the PDF link.
6. Saves the file as `<Covidence_ID>_<original_filename>.pdf` in `data/pdf_original/`.
7. Appends one JSON object per attempt to `data/extraction_json/covidence/download_manifest.jsonl`.

## Installation

```powershell
.venv\Scripts\python.exe -m pip install playwright
.venv\Scripts\python.exe -m playwright install chromium
```

## Usage

Interactive first run:

```powershell
.venv\Scripts\python.exe src\pipelines\00_download_covidence_pdfs.py
```

Headless rerun after the session has been saved:

```powershell
.venv\Scripts\python.exe src\pipelines\00_download_covidence_pdfs.py --headless
```

Environment variables are supported:

```powershell
$env:COVIDENCE_EMAIL="your.email@example.com"
$env:COVIDENCE_PASSWORD="your-password"
```

## Notes

- Credentials should not be committed to the repository.
- The manifest is append-only so reruns remain auditable.
- The script skips any existing `data/pdf_original/<Covidence_ID>_*.pdf` file unless `--overwrite` is used.
- Covidence UI changes may require selector updates in the script.
