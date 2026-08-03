from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import re
import shutil
import tempfile
import unicodedata
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree as ET

from pypdf import PdfReader


REPO_ROOT = Path(__file__).resolve().parents[2]
GIANNIS_ROOT = REPO_ROOT / "giannis"
LEGACY_ROOT = GIANNIS_ROOT / "Single_Case_reports"
OUTPUT_ROOT = GIANNIS_ROOT / "single_case_reports_clean"
REFERENCE_CSV = REPO_ROOT / "data" / "references" / "sps_references_export.csv"
REFERENCE_RIS = REPO_ROOT / "data" / "references" / "sps_references_export.ris"
RECONCILIATION_XLSX_GLOB = "SPS Corpus Reconciliation*.xlsx"

PDF_DIR = OUTPUT_ROOT / "pdf"
RAW_DIR = OUTPUT_ROOT / "json_raw"
CLEAN_DIR = OUTPUT_ROOT / "json_clean"
REGISTRY_DIR = OUTPUT_ROOT / "registry"
REGISTRY_PATH = REGISTRY_DIR / "canonical_registry.csv"
EXCEPTIONS_PATH = REGISTRY_DIR / "missing_or_incorrect_sources.csv"
PDF_TEXT_CACHE_DIR = Path(tempfile.gettempdir()) / "sps_single_case_pdf_text_cache"

CANDIDATE_DIRS = (
    ("canonical", REPO_ROOT / "data" / "pdf_original"),
    ("primary", LEGACY_ROOT / "single_case_reports_476"),
    ("new", LEGACY_ROOT / "new pdfs"),
    ("old", LEGACY_ROOT / "old pdfs"),
    ("duplicates", GIANNIS_ROOT / "Duplicates"),
)

# These sources were recovered from verified publisher pages or official
# archives and promoted into data/pdf_original. Their canonical provenance is
# stronger than metadata extracted from the superseded multi-article bundles.
CANONICAL_SOURCE_IDS = {"193", "228", "272", "526", "568", "647", "6012"}
ACQUIRED_PDFS = {
    "10691": OUTPUT_ROOT / "downloaded_pdfs" / "10691.pdf",
    "11849": OUTPUT_ROOT / "downloaded_pdfs" / "11849.pdf",
    "11976": OUTPUT_ROOT / "downloaded_pdfs" / "11976.pdf",
    "12305": OUTPUT_ROOT / "downloaded_pdfs" / "12305.pdf",
}
RAW_SOURCE_DIR = LEGACY_ROOT / "pdf_json Case reports"
CLEAN_SOURCE_DIR = LEGACY_ROOT / "backmatter_removed Case Reports"
ISOLATED_SOURCE_DIR = LEGACY_ROOT / "ollamatextisolation Case Reports"
MAIN_RAW_SOURCE_DIR = REPO_ROOT / "data" / "extraction_json" / "text"

WORD_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

STOPWORDS = {
    "the",
    "and",
    "with",
    "for",
    "from",
    "into",
    "that",
    "this",
    "case",
    "report",
    "person",
    "syndrome",
    "stiff",
    "man",
    "patient",
    "patients",
    "of",
    "in",
    "a",
    "an",
    "to",
    "on",
    "as",
    "by",
    "after",
    "associated",
}

FRONT_JUNK_PATTERNS = (
    "subito copyright regulations",
    "copies of articles ordered through subito",
    "cross ref id:",
    "lender:",
    "borrower:",
    "interlibrary loan",
    "copyright clearance center",
)

TAIL_JUNK_PATTERNS = (
    "terms and conditions",
    "rules of use",
    "creative commons license",
    "publisher's note",
    "publisher note",
)

PLACEHOLDER_PATTERNS = (
    "the provided text does not contain",
    "the provided extracted pdf text is empty",
    "no text was provided",
    "please provide the extracted text",
    "there is no content to process",
)

# Targeted visual decisions for PDFs whose bibliographic text layer is absent,
# broken, or incomplete. Each decision was made from rendered source pages,
# not from filenames alone.
MANUAL_PDF_DECISIONS: dict[str, tuple[str, str]] = {
    "85": ("verified_visual", "delivery cover followed by the complete Chang 1995 article on PDF pages 3-5"),
    "121": ("verified_visual", "title, authors, article text, journal and year visible on PDF page 1"),
    "126": ("verified_visual", "title, authors, abstract and article text visible on PDF page 1"),
    "213": ("verified_visual", "title, authors and bilingual article text visible on PDF page 1"),
    "223": ("verified_visual", "title, authors and article text visible on PDF page 1"),
    "274": ("verified_visual", "title, authors and case text visible on PDF page 1"),
    "387": ("verified_visual", "title, authors and full short report visible on PDF page 1"),
    "531": ("verified_visual", "title, author and full article text visible on PDF page 1"),
    "637": ("verified_visual", "title, authors, abstract and case report visible on PDF page 1"),
    "861": ("verified_visual", "target article Stiff-man syndrome in childhood is present on PDF pages 5-6"),
    "1739": ("verified_visual", "title, authors, abstract and article text visible on PDF page 1"),
    "3279": ("verified_visual", "title, authors and case report visible on PDF page 1"),
    "3438": ("verified_visual", "title, author and case report visible on PDF page 1"),
    "5254": ("verified_visual", "title, authors and case report visible on PDF page 1"),
    "5373": ("verified_visual", "title, authors, abstract and paediatric case visible on PDF page 1"),
    "5529": ("verified_visual", "target abstract is visibly present on the multi-abstract proceedings page"),
    "5753": ("verified_visual", "title and complete target poster abstract visible on PDF page 1"),
    "6101": ("verified_visual", "title, authors and complete structured abstract visible on PDF page 1"),
    "6475": ("verified_visual", "title and complete case poster visible on PDF page 1"),
    "6610": ("verified_visual", "target abstract is visibly present on the proceedings page"),
    "6666": ("verified_visual", "title, authors, abstract and case text visible on PDF page 1"),
    "9182": ("verified_visual", "delivery pages followed by the complete French letter on PDF page 3"),
    "9385": ("verified_visual", "copyright cover followed by the complete Sonawalla article on PDF pages 2-5"),
    "10695": ("verified_visual", "title, authors and complete case article visible on PDF pages 1-3"),
    "11956": ("verified_visual", "complete Teaching Video NeuroImage item visible on PDF page 1"),
    "12465": ("verified_visual", "target treatment letter and article text visible on PDF page 1"),
    "12785": ("verified_visual", "title, authors and case report visible on PDF page 1"),
    "12798": ("verified_visual", "title, authors and case report visible on PDF page 1"),
    "13723": ("verified_visual", "title, authors and case report visible on PDF page 1"),
    "10691": ("verified_visual", "exact Liguori et al. meeting abstract is visible on PDF page 266, journal page A311"),
    "12305": ("verified_visual", "exact Dy Closas et al. abstract is visible on PDF page 21, supplement page S869"),
    "1297": (
        "verified_accepted_english_abstract",
        "English abstract matches the indexed Japanese article; accepted as an explicit exception because the full text is in Japanese",
    ),
    "11849": ("verified_visual", "title, authors, DOI and complete accepted manuscript are visible in the 27-page PDF"),
    "11976": ("verified_visual", "title, authors, DOI and complete four-page publisher article are visible in the PDF"),
}

# Acquisition trail for the five corrected or explicitly accepted sources.
MANUAL_ACQUISITION_TRACES: dict[str, tuple[str, str, str]] = {
    "193": (
        "publisher_pages_lossless_extract",
        "https://doi.org/10.1002/1531-8257(200003)15:2%3C358::AID-MDS1032%3E3.0.CO;2-L",
        "The exact article occupies printed pages 358-359 of the repository's original publisher issue bundle.",
    ),
    "228": (
        "publisher_pages_lossless_extract",
        "https://doi.org/10.1212/WNL.60.12.1976",
        "The exact article occupies printed pages 1976-1978 of the repository's original publisher issue bundle.",
    ),
    "272": (
        "official_archive_pdf",
        "https://europepmc.org/articles/PMC1739318?pdf=render",
        "The official archived JNNP PDF contains the complete article on printed pages 141-142.",
    ),
    "526": (
        "publisher_pages_lossless_extract",
        "https://doi.org/10.1002/mds.22521",
        "The exact article occupies printed pages 2158-2159 of the repository's original publisher issue bundle.",
    ),
    "568": (
        "publisher_pages_lossless_extract",
        "https://doi.org/10.1002/mds.23784",
        "The exact article occupies printed pages 2138-2139 of the repository's original publisher issue bundle.",
    ),
    "6012": (
        "publisher_pages_lossless_extract",
        "https://doi.org/10.1212/01.wnl.0000196488.87746.7b",
        "The exact article occupies printed pages 450-451 of the repository's original publisher issue bundle.",
    ),
    "647": (
        "official_archive_pdf",
        "https://europepmc.org/articles/PMC1753919?pdf=render",
        "The official archived Annals of the Rheumatic Diseases PDF contains the complete article on printed pages 939-940.",
    ),
    "1297": (
        "accepted_english_abstract_exception",
        "https://ndlsearch.ndl.go.jp/books/R000000004-I027093756",
        "The available one-page English abstract matches the indexed article. The user accepted it because the four-page full text is in Japanese.",
    ),
    "10691": (
        "acquired_publisher_supplement",
        "https://www.neurology.org/doi/10.1212/WNL.43.4_Suppl_2.A11",
        "The complete 1993 annual-meeting supplement contains the exact Liguori et al. abstract on PDF page 266, journal page A311.",
    ),
    "11849": (
        "acquired_accepted_manuscript",
        "https://www.tandfonline.com/doi/pdf/10.1080/21548331.2021.1961456",
        "The 27-page Taylor & Francis accepted manuscript contains the exact title, authors, DOI and complete article.",
    ),
    "11976": (
        "acquired_publisher_pdf",
        "https://www.sciencedirect.com/science/article/pii/S1566070221001405",
        "The four-page Elsevier PDF contains the exact title, authors, DOI and complete short communication.",
    ),
    "12305": (
        "acquired_publisher_category_pdf",
        "https://movementdisorders.onlinelibrary.wiley.com/doi/pdf/10.1002/mds.29548",
        "The Wiley Education/Other Topics category PDF contains the exact Dy Closas et al. abstract on PDF page 21, supplement page S869.",
    ),
}

# These are narrowly scoped repairs for records where the legacy clean JSON
# retained delivery material, an adjacent article, references, or text from an
# older PDF.  The page and marker boundaries were checked against rendered
# pages.  "raw" means the exact-hash OCR/pypdf extraction selected below;
# "legacy" means the already curated clean record, with a tighter boundary.
CLEAN_OVERRIDES: dict[str, dict[str, Any]] = {
    "17": {"source": "legacy", "pages": [2, 3], "end": "Dr. Bhutaniis"},
    "85": {"source": "legacy", "pages": [2, 3, 4]},
    "99": {"source": "isolated", "end": "*Frederique H Vermeij"},
    "110": {"source": "raw", "pages": [0], "end": "We thank Pietro"},
    "115": {"source": "raw", "pages": [0, 1], "end": "From the National Hospital for Neurology"},
    "1297": {"source": "raw", "pages": [0]},
    "155": {"source": "legacy", "pages": [0, 1, 2, 3], "end": "W e thank Professor E Albert"},
    "415": {"source": "isolated"},
    "489": {"source": "legacy", "pages": [0, 1]},
    "517": {
        "source": "raw",
        "start": "Stiff-person syndrome in a female patient with type 1 diabetes",
        "end": "References",
    },
    "570": {"source": "isolated"},
    "581": {"source": "isolated"},
    "607": {
        "source": "legacy",
        "pages": [0, 1],
        "start": "BOTULINUM TOXIN A IN ANTI",
        "end": "Evangelos Anagnostou, MD",
    },
    "626": {"source": "raw", "pages": [0], "end": "From the Department of Neurology"},
    "643": {"source": "raw", "start": "Acute attacks and brain stem", "end": "References"},
    "716": {"source": "legacy", "end": "Contributors"},
    "789": {"source": "isolated"},
    "871": {"source": "isolated"},
    "901": {
        "source": "legacy",
        "segments": [
            ("Stiff-arm syndrome", "Enrique Urrea-Mendoza, MD"),
            ("Figure Limited range of right arm movements", "VIDEO\nNEURO IMAGES"),
        ],
    },
    "1372": {"source": "legacy", "end": "\n1. Moersch F. P."},
    "2762": {"source": "legacy", "end": "Previous Presentation:"},
    "5153": {"source": "raw", "pages": [1, 2, 3, 4], "end": "Correspondence to:"},
    "6465": {"source": "raw", "pages": [0], "end": "We thank Dr F Graus"},
    "7896": {
        "source": "raw",
        "start": "Stiff person syndrome (SPS), a basal ganglia disease",
        "end": "References",
    },
    "848": {
        "source": "legacy",
        "segments": [
            (None, "Editor: N/A."),
            ("symptoms among his family members", "Informed consent was obtained from the patient for the"),
            ("3. Discussion", None),
        ],
    },
    "1094": {
        "source": "legacy",
        "segments": [(None, "This study was supported"), ("Introduction", None)],
    },
    "9182": {"source": "raw", "pages": [2], "end": "REFERENCES"},
    "10691": {
        "source": "raw",
        "pages": [265],
        "start": "Vigabatrin Improves Rigidity in Stiff-Person",
        "end": "594P",
    },
    "11849": {
        "source": "raw",
        "pages": list(range(1, 26)),
        "start": "Stiff-person syndrome: an atypical presentation",
        "end": "References",
    },
    "11976": {
        "source": "raw",
        "pages": [0, 1, 2, 3],
        "start": "Severe dysautonomia in glycine receptor antibody-positive",
        "end": "References",
    },
    "12305": {
        "source": "raw",
        "pages": [20],
        "start": "Breast Carcinoma Presenting with Anti-amphiphysin Antibody-",
        "end": "Other: Meige Syndrome",
    },
    "1133": {"source": "isolated"},
    "1248": {"source": "isolated"},
    "1661": {"source": "isolated"},
    "1773": {"source": "isolated"},
    "2442": {"source": "isolated"},
    "2885": {"source": "legacy", "end": "Accepted for Publication:"},
    "5094": {"source": "isolated"},
    "5373": {"source": "legacy", "end": "Accepted for Publication:"},
    "5381": {"source": "isolated"},
    "5985": {"source": "isolated"},
    "6010": {"source": "legacy", "pages": [0, 1, 2]},
    "6336": {"source": "isolated"},
    "6683": {"source": "legacy", "pages": [0]},
    "8181": {"source": "isolated"},
    "9477": {"source": "isolated", "end": "ROGER ABARKER"},
    "11789": {"source": "isolated", "end": "Darren Y L C, Robyn G. Anaesthetic"},
    "11803": {"source": "isolated"},
    "11903": {"source": "legacy", "end": "Ethical statement"},
    "12219": {
        "source": "legacy",
        "segments": [
            (None, "under the terms of the Creative Commons"),
            ("Le syndrome de la personne raide (SPR) est", "1. Fernando GT"),
            ("Tableau 1:", None),
        ],
    },
    "12246": {"source": "legacy", "end": "Accepted for Publication:"},
    "12465": {"source": "isolated", "end": "ROGER ABARKER"},
    "12531": {"source": "isolated"},
    "12545": {"source": "isolated"},
    "12627": {
        "source": "legacy",
        "segments": [(None, "AUTHORS INFO & AFFILIATIONS"), ("Abstract\nObjective:", None)],
    },
    "12660": {
        "source": "legacy",
        "segments": [(None, "AUTHORS INFO & AFFILIATIONS"), ("Abstract\nObjective:", None)],
    },
    "12683": {
        "source": "raw",
        "start": "Stiff person syndrome (SPS), a basal ganglia disease",
        "end": "References",
    },
    "12762": {"source": "isolated"},
    "13267": {
        "source": "legacy",
        "segments": [(None, "AUTHORS INFO & AFFILIATIONS"), ("Abstract\nObjective:", None)],
    },
    "13804": {
        "source": "legacy",
        "segments": [
            ("Successful Autologous Hematopoietic Stem Cell Transplant in a Case", "AUTHORS INFO & AFFILIATIONS"),
            ("Abstract Abstract", "Volume 100"),
            ("cases severe disability", None),
        ],
    },
}

# The title text layer is unusually fragmented in these visually verified
# sources.  Their clean text was read as part of the page review.
MANUAL_CLEAN_APPROVALS = {
    "121",
    "223",
    "387",
    "624",
    "901",
    "904",
    "6185",
    "9182",
    "9477",
    "12465",
}


@dataclass(frozen=True)
class PdfCandidate:
    paper_id: str
    kind: str
    path: Path
    sha256: str
    page_count: int
    text: str
    text_char_count: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit and publish the verified single-case PDF/raw-JSON/clean-JSON collection."
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Publish artifacts that pass all gates. Without this flag only registries are refreshed.",
    )
    parser.add_argument(
        "--paper-id",
        action="append",
        default=[],
        help="Restrict processing to one or more paper IDs.",
    )
    return parser.parse_args()


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_json(record: dict[str, Any]) -> str:
    payload = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = value.encode("ascii", "ignore").decode("ascii").lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value).split())


def token_set(value: str, *, min_len: int = 4, drop_stopwords: bool = False) -> set[str]:
    tokens = {token for token in normalize_text(value).split() if len(token) >= min_len}
    if drop_stopwords:
        tokens -= STOPWORDS
    return tokens


def title_overlap(title: str, text: str) -> float:
    expected = token_set(title, drop_stopwords=True)
    if not expected:
        return 0.0
    observed = token_set(text)
    return len(expected & observed) / len(expected)


def abstract_overlap(abstract: str, text: str) -> float:
    expected = token_set(abstract, drop_stopwords=True)
    if len(expected) < 12:
        return 0.0
    observed = token_set(text)
    return len(expected & observed) / len(expected)


def first_author_surname(authors: str) -> str:
    first = (authors or "").split(";", 1)[0].strip()
    if not first:
        return ""
    if "," in first:
        return normalize_text(first.split(",", 1)[0])
    parts = normalize_text(first).split()
    if not parts:
        return ""
    if len(parts) >= 2 and all(len(part) <= 2 for part in parts[1:]):
        return parts[0]
    return parts[-1]


def normalize_doi(value: str) -> str:
    value = normalize_text(value).replace("https dx doi org ", "").replace("https doi org ", "")
    value = value.replace("http dx doi org ", "").replace("http doi org ", "")
    return value.replace(" ", "")


def pdf_id(path: Path) -> str:
    match = re.match(r"^(\d+)", path.stem)
    return match.group(1) if match else ""


def json_text(record: dict[str, Any]) -> str:
    return "\n".join(
        str(page.get("text") or "")
        for page in (record.get("pages") or [])
        if isinstance(page, dict)
    )


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    ns = {"x": WORD_NS}
    return ["".join(node.text or "" for node in item.findall(".//x:t", ns)) for item in root.findall("x:si", ns)]


def workbook_sheet_path(archive: zipfile.ZipFile, sheet_name: str) -> str:
    ns = {"x": WORD_NS, "r": REL_NS}
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rel_id = ""
    for sheet in workbook.findall(".//x:sheet", ns):
        if sheet.attrib.get("name") == sheet_name:
            rel_id = sheet.attrib.get(f"{{{REL_NS}}}id", "")
            break
    if not rel_id:
        raise RuntimeError(f"Worksheet not found: {sheet_name}")
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    for rel in relationships.findall(f"{{{PKG_REL_NS}}}Relationship"):
        if rel.attrib.get("Id") == rel_id:
            target = rel.attrib["Target"].lstrip("/")
            return target if target.startswith("xl/") else "xl/" + target
    raise RuntimeError(f"Worksheet relationship not found: {sheet_name}")


def cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t", "")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(f".//{{{WORD_NS}}}t"))
    value_node = cell.find(f"{{{WORD_NS}}}v")
    if value_node is None or value_node.text is None:
        return ""
    if cell_type == "s":
        return shared_strings[int(value_node.text)]
    return value_node.text


def read_expected_ids_from_workbook(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        shared_strings = read_shared_strings(archive)
        sheet_path = workbook_sheet_path(archive, "Single case report")
        root = ET.fromstring(archive.read(sheet_path))
    rows = root.findall(f".//{{{WORD_NS}}}row")
    if not rows:
        raise RuntimeError("Single case report worksheet is empty")
    header_by_col: dict[str, str] = {}
    for cell in rows[0].findall(f"{{{WORD_NS}}}c"):
        ref = cell.attrib.get("r", "")
        col = re.sub(r"\d+", "", ref)
        header_by_col[col] = cell_value(cell, shared_strings)
    id_column = next((col for col, value in header_by_col.items() if value == "Manfredi ID"), "")
    if not id_column:
        raise RuntimeError("Manfredi ID column not found")
    ids: list[str] = []
    for row in rows[1:]:
        for cell in row.findall(f"{{{WORD_NS}}}c"):
            if re.sub(r"\d+", "", cell.attrib.get("r", "")) != id_column:
                continue
            value = cell_value(cell, shared_strings).strip()
            if value:
                ids.append(value.removesuffix(".0"))
            break
    return ids


def load_ris_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    current: dict[str, Any] = {}
    authors: list[str] = []
    last_tag = ""
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if len(line) >= 6 and line[2:6] == "  - ":
            tag = line[:2]
            value = line[6:]
            last_tag = tag
            if tag == "TY":
                current = {"TY": value}
                authors = []
            elif tag == "AU":
                authors.append(value)
            elif tag == "ER":
                current["AU"] = authors
                records.append(current)
                current = {}
                authors = []
            else:
                current[tag] = value
        elif current and last_tag and line.strip():
            if last_tag == "AU" and authors:
                authors[-1] += " " + line.strip()
            elif last_tag in current:
                current[last_tag] = str(current[last_tag]) + " " + line.strip()
    return records


def load_references(expected_ids: set[str]) -> dict[str, dict[str, str]]:
    with REFERENCE_CSV.open(encoding="utf-8-sig", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    ris_rows = load_ris_records(REFERENCE_RIS)
    if len(csv_rows) != len(ris_rows):
        raise RuntimeError(f"RIS/CSV record count mismatch: {len(ris_rows)} vs {len(csv_rows)}")
    rows: dict[str, dict[str, str]] = {}
    for csv_row, ris_row in zip(csv_rows, ris_rows, strict=True):
        paper_id = (csv_row.get("Covidence") or "").strip()
        ris_title = str(ris_row.get("TI") or "").strip()
        ris_year = str(ris_row.get("PY") or "").strip()
        if normalize_text(ris_title) != normalize_text(csv_row.get("Title", "")) or ris_year != (csv_row.get("Published Year") or "").strip():
            raise RuntimeError(f"RIS/CSV metadata mismatch for Covidence ID {paper_id}")
        if paper_id not in expected_ids:
            continue
        rows[paper_id] = {
            "Title": ris_title,
            "Authors": "; ".join(str(value) for value in (ris_row.get("AU") or [])),
            "Published Year": ris_year,
            "DOI": str(ris_row.get("DO") or "").strip(),
            "Abstract": str(ris_row.get("AB") or "").strip(),
            "Journal": str(ris_row.get("JO") or "").strip(),
            "Volume": str(ris_row.get("VL") or "").strip(),
            "Issue": str(ris_row.get("IS") or "").strip(),
            "Pages": str(ris_row.get("PG") or "").strip(),
        }
    missing = expected_ids - set(rows)
    if missing:
        raise RuntimeError(f"Reference CSV is missing expected IDs: {sorted(missing)}")
    return rows


def extract_pdf(path: Path, digest: str = "") -> tuple[int, str]:
    cache_path = PDF_TEXT_CACHE_DIR / f"{digest}.json.gz" if digest else None
    if cache_path is not None and cache_path.exists():
        with gzip.open(cache_path, "rt", encoding="utf-8") as handle:
            cached = json.load(handle)
        return int(cached["page_count"]), str(cached["text"])
    reader = PdfReader(str(path))
    texts = []
    for page in reader.pages:
        try:
            texts.append((page.extract_text() or "").replace("\u00a0", " "))
        except Exception:
            texts.append("")
    result = (len(reader.pages), "\n".join(texts))
    if cache_path is not None:
        PDF_TEXT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with gzip.open(cache_path, "wt", encoding="utf-8") as handle:
            json.dump({"page_count": result[0], "text": result[1]}, handle, ensure_ascii=False)
    return result


def collect_candidates(expected_ids: set[str]) -> dict[str, list[PdfCandidate]]:
    result: dict[str, list[PdfCandidate]] = defaultdict(list)
    for kind, directory in CANDIDATE_DIRS:
        if not directory.exists():
            continue
        for path in directory.glob("*.pdf"):
            paper_id = pdf_id(path)
            if paper_id not in expected_ids:
                continue
            digest = sha256_file(path)
            pages, text = extract_pdf(path, digest)
            result[paper_id].append(
                PdfCandidate(
                    paper_id=paper_id,
                    kind=kind,
                    path=path,
                    sha256=digest,
                    page_count=pages,
                    text=text,
                    text_char_count=len(text),
                )
            )
    for paper_id, path in ACQUIRED_PDFS.items():
        if paper_id not in expected_ids or not path.exists():
            continue
        digest = sha256_file(path)
        pages, text = extract_pdf(path, digest)
        result[paper_id].append(
            PdfCandidate(
                paper_id=paper_id,
                kind="acquired",
                path=path,
                sha256=digest,
                page_count=pages,
                text=text,
                text_char_count=len(text),
            )
        )
    return result


def linked_clean_text(candidate: PdfCandidate) -> str:
    path = CLEAN_SOURCE_DIR / f"{candidate.paper_id}.json"
    if not path.exists():
        return ""
    record = load_json(path)
    if (record.get("source_sha256") or "") != candidate.sha256:
        return ""
    return json_text(record)


def evidence_for(candidate: PdfCandidate, reference: dict[str, str]) -> dict[str, Any]:
    direct_text = candidate.text
    clean_text = linked_clean_text(candidate)
    surname = first_author_surname(reference.get("Authors", ""))
    year = (reference.get("Published Year") or "").strip()
    doi = normalize_doi(reference.get("DOI", ""))

    def score_text(text: str, source: str) -> dict[str, Any]:
        title_score = title_overlap(reference.get("Title", ""), text)
        abstract_score = abstract_overlap(reference.get("Abstract", ""), text)
        normalized_evidence = normalize_text(text)
        author_match = bool(surname and surname in normalized_evidence.split())
        year_match = bool(year and year in text)
        doi_match = bool(doi and doi in normalize_doi(text))
        if doi_match:
            verdict = "verified_doi"
            rank = 6
        elif abstract_score >= 0.75:
            verdict = "verified_abstract"
            rank = 5
        elif title_score >= 0.80 and author_match and year_match:
            verdict = "verified_title_author_year"
            rank = 4
        elif title_score >= 0.90 and author_match:
            verdict = "verified_title_author"
            rank = 3
        elif title_score >= 0.90 and year_match:
            verdict = "verified_title_year"
            rank = 2
        else:
            verdict = "needs_manual_review"
            rank = 0
        return {
            "verdict": verdict,
            "rank": rank,
            "title_score": round(title_score, 3),
            "abstract_score": round(abstract_score, 3),
            "author_match": author_match,
            "year_match": year_match,
            "doi_match": doi_match,
            "evidence_source": source,
            "evidence_excerpt": " ".join(text.split())[:300],
        }

    options = [score_text(direct_text, "pdf_text")]
    if clean_text:
        options.append(score_text(clean_text, "linked_clean_json"))
    best = max(
        options,
        key=lambda item: (
            int(item["rank"]),
            float(item["title_score"]),
            float(item["abstract_score"]),
            int(item["author_match"]),
            int(item["year_match"]),
        ),
    )
    return best


def candidate_preference(candidate: PdfCandidate) -> int:
    return {"canonical": 6, "acquired": 5, "new": 4, "primary": 3, "duplicates": 2, "old": 1}.get(
        candidate.kind,
        0,
    )


def select_candidate(candidates: list[PdfCandidate], reference: dict[str, str]) -> tuple[PdfCandidate | None, dict[str, Any]]:
    if not candidates:
        return None, {"verdict": "missing_pdf", "rank": -1}
    if candidates[0].paper_id in CANONICAL_SOURCE_IDS:
        candidates = [candidate for candidate in candidates if candidate.kind == "canonical"]
        if not candidates:
            return None, {"verdict": "missing_canonical_pdf", "rank": -1}
    by_hash: dict[str, PdfCandidate] = {}
    for candidate in candidates:
        current = by_hash.get(candidate.sha256)
        if current is None or candidate_preference(candidate) > candidate_preference(current):
            by_hash[candidate.sha256] = candidate
    scored = [(candidate, evidence_for(candidate, reference)) for candidate in by_hash.values()]
    scored.sort(
        key=lambda item: (
            int(item[1]["rank"]),
            float(item[1]["title_score"]),
            float(item[1].get("abstract_score", 0.0)),
            int(item[1]["author_match"]),
            int(item[1]["year_match"]),
            candidate_preference(item[0]),
            -item[0].page_count,
        ),
        reverse=True,
    )
    selected, evidence = scored[0]
    manual = MANUAL_PDF_DECISIONS.get(selected.paper_id)
    if manual is not None:
        verdict, note = manual
        evidence = dict(evidence)
        evidence.update(
            {
                "verdict": verdict,
                "rank": 4 if verdict.startswith("verified_") else 0,
                "evidence_source": "manual_visual",
                "evidence_excerpt": note,
            }
        )
    return selected, evidence


def ensure_raw_record(candidate: PdfCandidate) -> tuple[dict[str, Any], str]:
    main_path = MAIN_RAW_SOURCE_DIR / f"{candidate.paper_id}.json"
    if main_path.exists():
        main_record = load_json(main_path)
        if str(main_record.get("source_sha256") or "") == candidate.sha256:
            record = dict(main_record)
            record["paper_id"] = candidate.paper_id
            record["source_filename"] = f"{candidate.paper_id}.pdf"
            record["source_sha256"] = candidate.sha256
            return record, "verified_existing_main_workflow_extraction"
    legacy_path = RAW_SOURCE_DIR / f"{candidate.paper_id}.json"
    if legacy_path.exists():
        legacy = load_json(legacy_path)
        legacy_hash = str(legacy.get("source_sha256") or "")
        filename_matches = Path(str(legacy.get("source_filename") or "")).stem.startswith(candidate.paper_id)
        if legacy_hash == candidate.sha256 or (not legacy_hash and filename_matches):
            record = dict(legacy)
            record["paper_id"] = candidate.paper_id
            record["source_filename"] = f"{candidate.paper_id}.pdf"
            record["source_sha256"] = candidate.sha256
            return record, "verified_existing_extraction"
    pages, text = extract_pdf(candidate.path, candidate.sha256)
    page_texts = text.split("\n\f\n") if "\n\f\n" in text else None
    if page_texts is None:
        reader = PdfReader(str(candidate.path))
        page_texts = []
        for page in reader.pages:
            try:
                page_texts.append((page.extract_text() or "").replace("\u00a0", " "))
            except Exception:
                page_texts.append("")
    record = {
        "paper_id": candidate.paper_id,
        "source_filename": f"{candidate.paper_id}.pdf",
        "source_sha256": candidate.sha256,
        "extractor": "pypdf",
        "n_pages": pages,
        "pages": [{"page_index": index, "text": value} for index, value in enumerate(page_texts)],
    }
    return record, "verified_reextracted"


def selected_page_text(record: dict[str, Any], page_indices: list[int] | None) -> str:
    pages = [page for page in (record.get("pages") or []) if isinstance(page, dict)]
    if page_indices is not None:
        wanted = set(page_indices)
        pages = [page for page in pages if int(page.get("page_index", -1)) in wanted]
    return "\n".join(str(page.get("text") or "") for page in pages)


def slice_at_marker(text: str, marker: str | None, *, keep_after: bool) -> str:
    if marker is None:
        return text
    index = text.find(marker)
    if index < 0:
        flexible = re.escape(marker).replace(r"\ ", r"\s+")
        match = re.search(flexible, text, flags=re.IGNORECASE)
        index = match.start() if match is not None else -1
    if index < 0:
        raise RuntimeError(f"Configured clean-text marker was not found: {marker!r}")
    return text[index:] if keep_after else text[:index]


def sanitize_clean_text(text: str) -> str:
    # Remove legal/delivery/web boilerplate without rewriting the article.
    text = re.sub(
        r"Disclosure:\s*The Disclosure of Potential Con\s*flicts? of Interest forms are provided "
        r"with the online version of the article\s*\([^)]*\)\.?",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    junk_line_patterns = (
        r"\bthis material may be protected by copyright law\b",
        r"\bunauthorized reproduction of this article is prohibited\b",
        r"\bdownloaded by:.*copyrighted material\b",
        r"\bdownloaded from https?://.*\bterms and conditions\b",
        r"\bsee the terms and conditions\b",
        r"^\s*view publication stats\s*$",
        r"^see discussions stats and author profiles for this publication",
        r"^\s*all content following this page was uploaded by.*$",
        r"^\s*the user has requested enhancement of the downloaded file\.?\s*$",
        r"\bdownloaded from\s*$",
        r"^\s*disclosures?\b.*$",
        r"^\s*to disclose\.?\s*$",
        r"^\s*disclose\.?\s*$",
    )
    kept_lines: list[str] = []
    skipping_open_access_license = False
    open_access_license_lines = 0
    for line in text.splitlines():
        normalized_before = normalize_text(line)
        if (
            "terms of the creative commons" in normalized_before
            or "open access article distributed" in normalized_before
        ):
            if not (
                "properly cited" in normalized_before
                or "permission from the journal" in normalized_before
                or "distribution for non commercial purposes only" in normalized_before
                or "open access at sage" in normalized_before
            ):
                skipping_open_access_license = True
                open_access_license_lines = 0
            continue
        if skipping_open_access_license:
            open_access_license_lines += 1
            if (
                "properly cited" in normalized_before
                or "permission from the journal" in normalized_before
                or "distribution for non commercial purposes only" in normalized_before
                or "open access at sage" in normalized_before
                or "identical terms" in normalized_before
                or open_access_license_lines >= 6
            ):
                skipping_open_access_license = False
            continue
        line = re.sub(r"\bV?C\s*20\d{2}\s+Wiley Periodicals,?\s*Inc\.?", "", line, flags=re.IGNORECASE)
        line = re.sub(r"Potential conflict of interest:\s*None reported\.?", "", line, flags=re.IGNORECASE)
        line = re.sub(r"Potential conflict of interest:\s*Nothing to report\.?", "", line, flags=re.IGNORECASE)
        line = re.sub(
            r"Disclosure:\s*Author disclosures are provided at the end of the article\.?",
            "",
            line,
            flags=re.IGNORECASE,
        )
        line = re.sub(
            r"Disclosure:\s*The Disclosure of Potential Conflicts of Interest\s*forms are provided "
            r"with the online version of the article\s*\([^)]*\)\.?",
            "",
            line,
            flags=re.IGNORECASE,
        )
        normalized_line = normalize_text(line)
        if any(re.search(pattern, normalized_line, flags=re.IGNORECASE) for pattern in junk_line_patterns):
            continue
        if "copyright" in normalized_line and len(normalized_line) < 180:
            continue
        if "all rights reserved" in normalized_line and len(normalized_line) < 220:
            continue
        if line.strip().startswith("©") and len(line.strip()) < 220:
            continue
        if normalized_line == "article":
            continue
        if "page numbers not for citation purposes" in normalized_line:
            continue
        if "for reprints contact" in normalized_line:
            continue
        if re.match(r"^[A-Za-z0-9/+]{30,}=\s+on\s+\d{2}/\d{2}/\d{4}$", line.strip()):
            continue
        kept_lines.append(line.rstrip())
    text = "\n".join(kept_lines).strip()
    text = re.sub(
        r"Informed consent was obtained from the patient to publish\s+this report\.\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # A standalone heading late in a record marks a true bibliography.  An
    # early website navigation item named "References" is removed as a line.
    heading = re.compile(r"(?im)^\s*(references?|bibliography|literature cited|selected reading)\s*:?[ \t]*$")
    matches = list(heading.finditer(text))
    for match in matches:
        if match.start() >= max(500, int(len(text) * 0.25)):
            text = text[: match.start()].rstrip()
            break
    else:
        text = heading.sub("", text)

    tail_heading = re.compile(
        r"(?im)^\s*(author contributions?|contributors|conflicts? of interest|disclosures?|"
        r"additional information|ethical statement|informed consent|peer-review|"
        r"supplementary materials?|funding|acknowledg(?:e)?ments?)\s*:?[ \t]*"
    )
    for match in tail_heading.finditer(text):
        if match.start() >= int(len(text) * 0.65):
            text = text[: match.start()].rstrip()
            break
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def override_clean_record(
    candidate: PdfCandidate,
    raw_record: dict[str, Any],
    legacy_record: dict[str, Any] | None,
) -> dict[str, Any] | None:
    config = CLEAN_OVERRIDES.get(candidate.paper_id)
    if config is None:
        return None
    if config["source"] == "raw":
        source_record = raw_record
    elif config["source"] == "legacy":
        source_record = legacy_record
    elif config["source"] == "isolated":
        isolated_path = ISOLATED_SOURCE_DIR / f"{candidate.paper_id}.json"
        source_record = load_json(isolated_path) if isolated_path.exists() else None
        if source_record is not None:
            isolated_source_hash = str(source_record.get("source_sha256") or "")
            isolated_text = json_text(source_record)
            raw_text = json_text(raw_record)
            isolated_tokens = token_set(isolated_text)
            raw_tokens = token_set(raw_text)
            recall = len(isolated_tokens & raw_tokens) / max(1, len(isolated_tokens))
            if isolated_source_hash != candidate.sha256 and recall < 0.72:
                raise RuntimeError(
                    f"Isolated clean text for {candidate.paper_id} is not sufficiently supported "
                    f"by the selected PDF extraction (token recall {recall:.3f})"
                )
    else:
        raise RuntimeError(f"Unknown clean override source: {config['source']}")
    if source_record is None:
        raise RuntimeError(f"Clean override for {candidate.paper_id} requires a missing legacy record")
    text = selected_page_text(source_record, config.get("pages"))
    if "segments" in config:
        pieces: list[str] = []
        for start, end in config["segments"]:
            piece = slice_at_marker(text, start, keep_after=True)
            piece = slice_at_marker(piece, end, keep_after=False)
            pieces.append(piece.strip())
        text = "\n\n".join(pieces)
    else:
        text = slice_at_marker(text, config.get("start"), keep_after=True)
        text = slice_at_marker(text, config.get("end"), keep_after=False)
    text = sanitize_clean_text(text)
    return {
        "paper_id": candidate.paper_id,
        "source_filename": f"{candidate.paper_id}.pdf",
        "source_sha256": candidate.sha256,
        "raw_json_sha256": sha256_json(raw_record),
        "cleaning_method": "verified_page_and_text_boundaries",
        "pages": [{"page_index": 0, "text": text}],
    }


def clean_record_for(candidate: PdfCandidate, raw_record: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    legacy_path = CLEAN_SOURCE_DIR / f"{candidate.paper_id}.json"
    legacy = load_json(legacy_path) if legacy_path.exists() else None
    override = override_clean_record(candidate, raw_record, legacy)
    if override is not None:
        return override, "verified_targeted_clean_repair"
    if legacy is None:
        return None, "missing_clean_json"
    clean = legacy
    clean_text = json_text(clean)
    source_hash = str(clean.get("source_sha256") or "")
    if not source_hash:
        raw_source_hash = str(raw_record.get("source_sha256") or "")
        if raw_source_hash != candidate.sha256 or len(normalize_text(clean_text)) < 200:
            return None, "clean_json_not_linked_to_selected_pdf"
        clean = dict(clean)
        clean["provenance_inferred_from_raw_json_sha256"] = sha256_json(raw_record)
    elif source_hash != candidate.sha256:
        # Replacement PDFs are acceptable only when the curated clean text is
        # strongly supported by the selected PDF's directly extracted text.
        clean_tokens = token_set(clean_text)
        pdf_tokens = token_set(candidate.text)
        token_recall = len(clean_tokens & pdf_tokens) / max(1, len(clean_tokens))
        if token_recall < 0.80:
            return None, "clean_json_not_linked_to_selected_pdf"
        clean = dict(clean)
        clean["rebased_from_source_sha256"] = source_hash
    clean_source_verdict = "candidate_clean_json"
    sanitized_legacy_text = sanitize_clean_text(clean_text)
    isolated_path = ISOLATED_SOURCE_DIR / f"{candidate.paper_id}.json"
    if isolated_path.exists():
        isolated = load_json(isolated_path)
        isolated_text = sanitize_clean_text(json_text(isolated))
        isolated_tokens = token_set(isolated_text)
        legacy_tokens = token_set(sanitized_legacy_text)
        raw_tokens = token_set(json_text(raw_record))
        isolated_source_hash = str(isolated.get("source_sha256") or "")
        source_supported = isolated_source_hash == candidate.sha256
        if not source_supported:
            recall = len(isolated_tokens & raw_tokens) / max(1, len(isolated_tokens))
            source_supported = recall >= 0.72
        isolated_nontrivial = len(isolated_tokens) >= 40
        extra_ratio = 1.0 - (len(legacy_tokens & isolated_tokens) / max(1, len(legacy_tokens)))
        if (
            source_supported
            and isolated_nontrivial
            and len(normalize_text(sanitized_legacy_text)) > 1.30 * len(normalize_text(isolated_text))
            and extra_ratio >= 0.18
        ):
            clean = dict(isolated)
            clean_text = isolated_text
            clean_source_verdict = "verified_isolated_text_preferred_over_contaminated_legacy"
        else:
            clean_text = sanitized_legacy_text
    else:
        clean_text = sanitized_legacy_text

    clean["paper_id"] = candidate.paper_id
    clean["source_filename"] = f"{candidate.paper_id}.pdf"
    clean["source_sha256"] = candidate.sha256
    clean["raw_json_sha256"] = sha256_json(raw_record)
    clean["pages"] = [{"page_index": 0, "text": clean_text}]
    return clean, clean_source_verdict


def reference_density(text: str) -> float:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return 0.0
    reference_like = 0
    for line in lines:
        has_year = bool(re.search(r"\b(?:18|19|20)\d{2}\b", line))
        has_pages = bool(re.search(r"\b\d+\s*[:;,]\s*\d+(?:[-–]\d+)?\b", line))
        numbered = bool(re.match(r"^(?:\[?\d{1,3}[\].)]|\d{1,3}\s)", line))
        if (has_year and has_pages) or (numbered and has_year):
            reference_like += 1
    return reference_like / len(lines)


def clean_quality(record: dict[str, Any] | None, reference: dict[str, str]) -> tuple[str, str]:
    if record is None:
        return "failed", "missing clean JSON"
    text = json_text(record)
    normalized = normalize_text(text)
    if len(normalized) < 200:
        return "failed", "clean text is empty or too short"
    if len(normalized) > 60000:
        return "failed", "clean text is implausibly long and may contain adjacent articles or proceedings"
    placeholder_hits = [pattern for pattern in PLACEHOLDER_PATTERNS if normalize_text(pattern) in normalized]
    if placeholder_hits:
        return "failed", f"placeholder text remains: {placeholder_hits[0]}"
    title_score = title_overlap(reference.get("Title", ""), text)
    abstract_score = abstract_overlap(reference.get("Abstract", ""), text)
    surname = first_author_surname(reference.get("Authors", ""))
    author_match = bool(surname and surname in normalized.split())
    paper_id = str(record.get("paper_id") or "")
    if title_score < 0.60 and not author_match and abstract_score < 0.55 and paper_id not in MANUAL_CLEAN_APPROVALS:
        return "failed", f"bibliographic evidence is weak (title overlap {title_score:.2f})"
    prefix = text[:3000]
    prefix_normalized = normalize_text(prefix)
    prefix_title_score = title_overlap(reference.get("Title", ""), prefix)
    prefix_abstract_score = abstract_overlap(reference.get("Abstract", ""), prefix)
    prefix_author_match = bool(surname and surname in prefix_normalized.split())
    if (
        prefix_title_score < 0.35
        and prefix_abstract_score < 0.55
        and not prefix_author_match
        and paper_id not in MANUAL_CLEAN_APPROVALS
    ):
        return "failed", "target article is not established near the start of the clean text"
    start = normalize_text(text[:1500])
    end = normalize_text(text[-2500:])
    def phrase_present(haystack: str, phrase: str) -> bool:
        needle = re.escape(normalize_text(phrase)).replace(r"\ ", r"\s+")
        return bool(re.search(rf"(?<![a-z0-9]){needle}(?![a-z0-9])", haystack))

    front_hits = [pattern for pattern in FRONT_JUNK_PATTERNS if phrase_present(start, pattern)]
    if front_hits:
        return "failed", f"frontmatter junk remains: {front_hits[0]}"
    tail_hits = [pattern for pattern in TAIL_JUNK_PATTERNS if phrase_present(end, pattern)]
    if tail_hits:
        return "failed", f"backmatter junk remains: {tail_hits[0]}"
    if re.search(r"(?im)^\s*(references?|bibliography|literature cited|selected reading)\s*:?[ \t]*$", text):
        return "failed", "explicit reference-list heading remains"
    return "verified", (
        f"title overlap {title_score:.2f}; abstract overlap {abstract_score:.2f}; "
        f"prefix title overlap {prefix_title_score:.2f}; "
        "no configured junk signatures"
    )


def relative(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def write_json(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def publish_artifacts(candidate: PdfCandidate, raw: dict[str, Any], clean: dict[str, Any]) -> tuple[str, str, str]:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    pdf_out = PDF_DIR / f"{candidate.paper_id}.pdf"
    raw_out = RAW_DIR / f"{candidate.paper_id}.json"
    clean_out = CLEAN_DIR / f"{candidate.paper_id}.json"
    shutil.copy2(candidate.path, pdf_out)
    write_json(raw_out, raw)
    write_json(clean_out, clean)
    return relative(pdf_out), relative(raw_out), relative(clean_out)


REGISTRY_FIELDS = (
    "paper_id",
    "title",
    "authors",
    "published_year",
    "doi",
    "journal",
    "volume",
    "issue",
    "pages",
    "selected_candidate_kind",
    "selected_candidate_path",
    "pdf_sha256",
    "pdf_page_count",
    "pdf_title_overlap",
    "pdf_abstract_overlap",
    "pdf_author_match",
    "pdf_year_match",
    "pdf_doi_match",
    "pdf_evidence_source",
    "pdf_evidence_excerpt",
    "pdf_verdict",
    "raw_json_verdict",
    "raw_json_sha256",
    "clean_json_verdict",
    "clean_json_sha256",
    "clean_quality_note",
    "overall_status",
    "published_pdf_path",
    "published_raw_json_path",
    "published_clean_json_path",
    "candidate_count",
    "acquisition_trace_status",
    "acquisition_url",
    "acquisition_note",
    "reviewed_at_utc",
)


def write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REGISTRY_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def merge_targeted_registry_rows(
    path: Path,
    updates: list[dict[str, Any]],
    selected_ids: set[str],
) -> list[dict[str, Any]]:
    if not selected_ids:
        return updates
    if not path.exists():
        raise RuntimeError(f"Cannot apply a targeted registry update because {relative(path)} does not exist")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        existing = list(csv.DictReader(handle))
    existing_ids = [row.get("paper_id", "") for row in existing]
    if len(existing) != 476 or len(set(existing_ids)) != 476:
        raise RuntimeError(
            f"Expected 476 unique rows in the existing registry, found {len(existing)} / {len(set(existing_ids))} unique"
        )
    update_by_id = {row["paper_id"]: row for row in updates}
    if set(update_by_id) != selected_ids:
        missing = sorted(selected_ids - set(update_by_id), key=int)
        raise RuntimeError(f"Targeted registry update did not produce rows for: {', '.join(missing)}")
    return [update_by_id.get(row["paper_id"], row) for row in existing]


def build_rows(*, publish: bool, selected_ids: set[str]) -> list[dict[str, Any]]:
    workbooks = list(GIANNIS_ROOT.glob(RECONCILIATION_XLSX_GLOB))
    if len(workbooks) != 1:
        raise RuntimeError(f"Expected one reconciliation workbook, found {len(workbooks)}")
    expected_ids = read_expected_ids_from_workbook(workbooks[0])
    if len(expected_ids) != 476 or len(set(expected_ids)) != 476:
        raise RuntimeError(f"Expected 476 unique single-case IDs, found {len(expected_ids)} / {len(set(expected_ids))} unique")
    if selected_ids:
        unknown_ids = selected_ids - set(expected_ids)
        if unknown_ids:
            raise RuntimeError(f"Unknown single-case IDs: {', '.join(sorted(unknown_ids, key=int))}")
        expected_ids = [paper_id for paper_id in expected_ids if paper_id in selected_ids]
    references = load_references(set(expected_ids))
    candidates = collect_candidates(set(expected_ids))
    rows: list[dict[str, Any]] = []
    for paper_id in sorted(expected_ids, key=int):
        reference = references[paper_id]
        selected, evidence = select_candidate(candidates.get(paper_id, []), reference)
        row: dict[str, Any] = {
            "paper_id": paper_id,
            "title": reference.get("Title", ""),
            "authors": reference.get("Authors", ""),
            "published_year": reference.get("Published Year", ""),
            "doi": reference.get("DOI", ""),
            "journal": reference.get("Journal", ""),
            "volume": reference.get("Volume", ""),
            "issue": reference.get("Issue", ""),
            "pages": reference.get("Pages", ""),
            "candidate_count": len(candidates.get(paper_id, [])),
            "reviewed_at_utc": now_utc(),
        }
        trace = MANUAL_ACQUISITION_TRACES.get(paper_id)
        if trace is not None:
            row.update(
                {
                    "acquisition_trace_status": trace[0],
                    "acquisition_url": trace[1],
                    "acquisition_note": trace[2],
                }
            )
        if selected is None:
            row.update(
                {
                    "pdf_verdict": "missing_pdf",
                    "raw_json_verdict": "not_checked",
                    "clean_json_verdict": "not_checked",
                    "overall_status": "missing_or_incorrect",
                }
            )
            rows.append(row)
            continue
        row.update(
            {
                "selected_candidate_kind": selected.kind,
                "selected_candidate_path": relative(selected.path),
                "pdf_sha256": selected.sha256,
                "pdf_page_count": selected.page_count,
                "pdf_title_overlap": evidence.get("title_score", ""),
                "pdf_abstract_overlap": evidence.get("abstract_score", ""),
                "pdf_author_match": evidence.get("author_match", ""),
                "pdf_year_match": evidence.get("year_match", ""),
                "pdf_doi_match": evidence.get("doi_match", ""),
                "pdf_evidence_source": evidence.get("evidence_source", ""),
                "pdf_evidence_excerpt": evidence.get("evidence_excerpt", ""),
                "pdf_verdict": evidence["verdict"],
            }
        )
        if not str(evidence["verdict"]).startswith("verified_"):
            row.update(
                {
                    "raw_json_verdict": "not_checked",
                    "clean_json_verdict": "not_checked",
                    "overall_status": "missing_or_incorrect",
                }
            )
            rows.append(row)
            continue
        raw, raw_verdict = ensure_raw_record(selected)
        raw_hash = sha256_json(raw)
        clean, clean_candidate_verdict = clean_record_for(selected, raw)
        clean_verdict, clean_note = clean_quality(clean, reference)
        if clean is None:
            clean_verdict = clean_candidate_verdict
        overall = "verified" if clean_verdict == "verified" else "missing_or_incorrect"
        published_paths = ("", "", "")
        if publish and overall == "verified" and clean is not None:
            published_paths = publish_artifacts(selected, raw, clean)
        row.update(
            {
                "raw_json_verdict": raw_verdict,
                "raw_json_sha256": raw_hash,
                "clean_json_verdict": clean_verdict,
                "clean_json_sha256": sha256_json(clean) if clean is not None else "",
                "clean_quality_note": clean_note,
                "overall_status": overall,
                "published_pdf_path": published_paths[0],
                "published_raw_json_path": published_paths[1],
                "published_clean_json_path": published_paths[2],
            }
        )
        rows.append(row)
    return rows


def main() -> None:
    args = parse_args()
    selected_ids = {str(value).strip() for value in args.paper_id if str(value).strip()}
    updates = build_rows(publish=args.publish, selected_ids=selected_ids)
    rows = merge_targeted_registry_rows(REGISTRY_PATH, updates, selected_ids)
    write_csv(REGISTRY_PATH, rows)
    exceptions = [row for row in rows if row.get("overall_status") != "verified"]
    write_csv(EXCEPTIONS_PATH, exceptions)
    print(
        json.dumps(
            {
                "rows": len(rows),
                "verified": len(rows) - len(exceptions),
                "exceptions": len(exceptions),
                "published": bool(args.publish),
                "registry": relative(REGISTRY_PATH),
                "exceptions_path": relative(EXCEPTIONS_PATH),
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
