from io import BytesIO
from pathlib import Path
import re

import fitz
from docx import Document
from PIL import Image

try:
    import pytesseract
except ImportError:  # pragma: no cover - optional dependency in minimal envs
    pytesseract = None


# ============================================================================
# TESSERACT CONFIGURATION
# ============================================================================

if pytesseract is not None:
    candidate_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]

    for candidate in candidate_paths:
        if Path(candidate).exists():
            pytesseract.pytesseract.tesseract_cmd = candidate
            break


# ============================================================================
# CONFIGURATION
# ============================================================================

CHUNK_SIZE = 1400
CHUNK_OVERLAP = 180

MIN_WORDS_FOR_OCR = 12
OCR_DPI = 300

BULLET_CHARS = (
    "\u25cf"
    "\u2022"
    "\uf0b7"
    "\ufffd"
    "\u2219"
    "\u25e6"
    "\u2023"
    "\u2043"
    "\u00b7"
)


# ============================================================================
# TEXT UTILITIES
# ============================================================================

def _normalize_line(line: str) -> str:
    """
    Normalize spaces inside one line.
    """
    return re.sub(r"[ \t]+", " ", line).strip()


def _normalize_text(text: str) -> str:
    """
    Normalize text while preserving paragraph breaks.
    """
    if not text:
        return ""

    paragraphs = []

    for paragraph in re.split(r"\n\s*\n", text):
        lines = []

        for line in paragraph.splitlines():
            line = _normalize_line(line)

            if line:
                lines.append(line)

        if lines:
            paragraphs.append(" ".join(lines))

    return "\n\n".join(paragraphs).strip()


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or ""))


def _is_page_number_only(line: str) -> bool:
    """
    Detect page-number-only lines.
    """
    value = line.strip().lower()

    if not value:
        return False

    if re.fullmatch(r"[\d\s|,.\-/\\]+", value):
        return any(char.isdigit() for char in value)

    if re.fullmatch(r"page\s*\d+", value):
        return True

    if re.fullmatch(r"p\.?\s*\d+", value):
        return True

    return False


def _is_bullet_only(line: str) -> bool:
    """
    Detect standalone bullet characters.
    """
    stripped = line.strip()

    if not stripped:
        return False

    allowed = BULLET_CHARS + " \t"

    return all(char in allowed for char in stripped)


def _is_noise_line(line: str) -> bool:
    """
    Remove obvious extraction noise.
    """
    stripped = line.strip()

    if not stripped:
        return True

    if _is_page_number_only(stripped):
        return True

    if _is_bullet_only(stripped):
        return True

    alpha_numeric_count = len(
        re.findall(r"[A-Za-z0-9]", stripped)
    )

    if len(stripped) > 5 and alpha_numeric_count == 0:
        return True

    return False


# ============================================================================
# HEADER / FOOTER DETECTION
# ============================================================================

def _signature(line: str) -> str:
    """
    Create a common signature for repeated headers and footers.
    """
    key = _normalize_line(line).lower()

    if not key:
        return ""

    key = re.sub(
        r"\s*\|\s*\d+\s*$",
        "",
        key,
    )

    key = re.sub(
        r"\s*[-–—]\s*\d+\s*$",
        "",
        key,
    )

    key = re.sub(
        r"\s+\d+\s*$",
        "",
        key,
    )

    return re.sub(r"\s+", " ", key).strip()


def _detect_boilerplate(
    raw_lines_by_page: list[list[str]],
) -> set[str]:
    """
    Detect repeated headers and footers.
    """
    if not raw_lines_by_page:
        return set()

    page_count = len(raw_lines_by_page)

    required_pages = max(
        2,
        int(page_count * 0.5),
    )

    occurrences: dict[str, set[int]] = {}
    edge_occurrences: dict[str, int] = {}

    for page_index, lines in enumerate(raw_lines_by_page):
        if not lines:
            continue

        edge_positions = (
            set(range(0, min(3, len(lines))))
            |
            set(range(max(0, len(lines) - 4), len(lines)))
        )

        for line_index, raw_line in enumerate(lines):
            line = _normalize_line(raw_line)
            signature = _signature(line)

            if not signature:
                continue

            occurrences.setdefault(
                signature,
                set(),
            ).add(page_index)

            if line_index in edge_positions:
                edge_occurrences[signature] = (
                    edge_occurrences.get(signature, 0) + 1
                )

    boilerplate = set()

    for signature, page_indexes in occurrences.items():
        if (
            len(page_indexes) >= required_pages
            and edge_occurrences.get(signature, 0) >= required_pages
        ):
            boilerplate.add(signature)

    return boilerplate


# ============================================================================
# PAGE TEXT CLEANING
# ============================================================================

def _clean_page_lines(
    lines: list[str],
    boilerplate: set[str],
) -> list[str]:
    """
    Clean extracted lines while preserving paragraph content.
    """
    cleaned_lines: list[str] = []
    seen_lines: set[str] = set()

    for raw_line in lines:
        line = _normalize_line(raw_line)

        if _is_noise_line(line):
            continue

        signature = _signature(line)

        if not signature:
            continue

        if signature in boilerplate:
            continue

        dedupe_key = line.lower()

        if dedupe_key in seen_lines:
            continue

        seen_lines.add(dedupe_key)
        cleaned_lines.append(line)

    return cleaned_lines


def _clean_extracted_text(
    text: str,
    boilerplate: set[str] | None = None,
) -> str:
    """
    Clean extracted text without destroying paragraph structure.
    """
    if not text:
        return ""

    boilerplate = boilerplate or set()

    paragraphs: list[str] = []

    for raw_paragraph in re.split(r"\n\s*\n", text):
        cleaned_lines = _clean_page_lines(
            lines=raw_paragraph.splitlines(),
            boilerplate=boilerplate,
        )

        if cleaned_lines:
            paragraphs.append(
                " ".join(cleaned_lines)
            )

    return "\n\n".join(paragraphs).strip()


# ============================================================================
# OCR
# ============================================================================

def _ocr_page(
    page,
    dpi: int = OCR_DPI,
) -> str:
    """
    OCR fallback for scanned pages.
    """
    if pytesseract is None:
        raise RuntimeError("pytesseract is not installed. OCR is unavailable.")

    matrix = fitz.Matrix(
        dpi / 72.0,
        dpi / 72.0,
    )

    pixmap = page.get_pixmap(
        matrix=matrix,
        alpha=False,
    )

    image = Image.open(
        BytesIO(
            pixmap.tobytes("png")
        )
    ).convert("RGB")

    text = pytesseract.image_to_string(
        image,
        config="--psm 6",
    )

    return text.strip()


# ============================================================================
# PDF BLOCK / PARAGRAPH EXTRACTION
# ============================================================================

def _extract_pdf_blocks(page) -> list[str]:
    """
    Extract PDF text using PyMuPDF blocks.

    Every text block is treated as a paragraph-like unit.
    This is better than using page.get_text("text").splitlines()
    because lines belonging to the same paragraph are joined together.
    """
    blocks = page.get_text(
        "blocks",
        sort=True,
    )

    paragraphs: list[str] = []

    for block in blocks:
        if len(block) < 5:
            continue

        block_text = block[4]

        if not block_text or not block_text.strip():
            continue

        lines = []

        for line in block_text.splitlines():
            line = _normalize_line(line)

            if line:
                lines.append(line)

        if not lines:
            continue

        paragraph = " ".join(lines).strip()

        if paragraph:
            paragraphs.append(paragraph)

    return paragraphs


def _extract_page_text(
    page,
    boilerplate: set[str] | None = None,
) -> str:
    """
    Extract page text.

    Priority:
    1. PDF text blocks
    2. OCR if selectable text is missing or poor
    """
    boilerplate = boilerplate or set()

    pdf_blocks = _extract_pdf_blocks(page)

    selectable_text = "\n\n".join(
        pdf_blocks
    ).strip()

    selectable_text = _clean_extracted_text(
        selectable_text,
        boilerplate=boilerplate,
    )

    selectable_word_count = _word_count(
        selectable_text
    )

    if selectable_word_count >= MIN_WORDS_FOR_OCR:
        return selectable_text

    try:
        ocr_text = _ocr_page(page)

        ocr_text = _clean_extracted_text(
            ocr_text,
            boilerplate=boilerplate,
        )

    except Exception:
        ocr_text = ""

    ocr_word_count = _word_count(
        ocr_text
    )

    if ocr_word_count > selectable_word_count:
        return ocr_text

    return selectable_text


# ============================================================================
# PAGE CLASSIFICATION
# ============================================================================

def classify_page(page_text: str) -> str:
    """
    Classify page as cover, toc, or content.
    """
    text = page_text.strip()

    if not text:
        return "content"

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    words = re.findall(
        r"\w+",
        text,
    )

    if len(words) < 60 and len(lines) <= 8:
        return "cover"

    numbered_headings = 0

    for line in lines:
        if re.match(
            r"^\d+(\.\d+)*\.?\s+[A-Z]",
            line,
        ):
            numbered_headings += 1

    heading_ratio = (
        numbered_headings / len(lines)
        if lines
        else 0
    )

    first_part = text[:250].lower()

    if "table of contents" in first_part:
        return "toc"

    if "contents" in first_part:
        return "toc"

    if len(lines) >= 6 and heading_ratio >= 0.5:
        return "toc"

    return "content"


# ============================================================================
# PDF EXTRACTION
# ============================================================================

def extract_pdf_pages(
    file_path: str,
) -> list[dict]:
    """
    Extract all PDF pages with paragraph-preserving text.
    """
    pages: list[dict] = []

    with fitz.open(file_path) as pdf_document:
        raw_lines_by_page: list[list[str]] = []

        # Pass 1: detect repeated headers and footers
        for page in pdf_document:
            blocks = _extract_pdf_blocks(page)

            raw_lines: list[str] = []

            for block in blocks:
                raw_lines.extend(
                    block.splitlines()
                )

            raw_lines_by_page.append(
                [
                    _normalize_line(line)
                    for line in raw_lines
                    if _normalize_line(line)
                ]
            )

        boilerplate = _detect_boilerplate(
            raw_lines_by_page
        )

        # Pass 2: final extraction
        for page_number, page in enumerate(
            pdf_document,
            start=1,
        ):
            page_text = _extract_page_text(
                page=page,
                boilerplate=boilerplate,
            )

            page_text = page_text.strip()

            pages.append({
                "page": page_number,
                "text": page_text,
                "page_type": classify_page(
                    page_text
                ),
            })

    return pages


# ============================================================================
# DOCX EXTRACTION
# ============================================================================

def extract_docx_pages(
    file_path: str,
) -> list[dict]:
    """
    Extract DOCX paragraphs.
    """
    document = Document(file_path)

    paragraphs: list[str] = []

    for paragraph in document.paragraphs:
        text = _normalize_line(
            paragraph.text
        )

        if text:
            paragraphs.append(text)

    full_text = "\n\n".join(
        paragraphs
    ).strip()

    return [
        {
            "page": None,
            "text": full_text,
            "page_type": "content",
        }
    ]


# ============================================================================
# CHUNKING
# ============================================================================

def _get_segments(
    text: str,
) -> list[tuple[int, int]]:
    """
    Split text into paragraph blocks.

    Important:
    Each paragraph is kept together as much as possible.
    """
    if not text.strip():
        return []

    segments: list[tuple[int, int]] = []

    for match in re.finditer(
        r"\S(?:.*?\S)?(?=\n\s*\n|\Z)",
        text,
        flags=re.DOTALL,
    ):
        start = match.start()
        end = match.end()

        segment_text = text[start:end].strip()

        if segment_text:
            segments.append(
                (
                    start,
                    end,
                )
            )

    if not segments:
        segments.append(
            (
                0,
                len(text),
            )
        )

    return segments


def _split_oversized(
    text: str,
    segment: tuple[int, int],
    chunk_size: int,
) -> list[tuple[int, int]]:
    """
    Split oversized paragraph only when necessary.
    """
    start, end = segment

    pieces: list[tuple[int, int]] = []

    current_start = start

    while current_start < end:
        hard_end = min(
            current_start + chunk_size,
            end,
        )

        window = text[
            current_start:hard_end
        ]

        boundary = None

        # Prefer sentence boundaries
        for match in re.finditer(
            r"[.!?]\s+(?=[A-Z0-9\"'(\u201c])",
            window,
        ):
            boundary = match.end() - 1

        # If no sentence boundary exists,
        # prefer the last whitespace.
        if boundary is None:
            whitespace_matches = list(
                re.finditer(
                    r"\s+",
                    window,
                )
            )

            if whitespace_matches:
                boundary = whitespace_matches[-1].start()
            else:
                boundary = len(window)

        if boundary <= 0:
            boundary = len(window)

        piece_end = current_start + boundary

        if piece_end <= current_start:
            piece_end = hard_end

        pieces.append(
            (
                current_start,
                piece_end,
            )
        )

        current_start = piece_end

        while (
            current_start < end
            and text[current_start].isspace()
        ):
            current_start += 1

    return pieces


def _merge_pieces(
    pieces: list[tuple[int, int]],
    chunk_size: int,
    overlap: int,
) -> list[tuple[int, int]]:
    """
    Merge nearby small pieces.
    """
    if not pieces:
        return []

    merged: list[tuple[int, int]] = []

    current_start, current_end = pieces[0]

    for piece_start, piece_end in pieces[1:]:
        combined_length = piece_end - current_start

        if combined_length <= chunk_size:
            current_end = piece_end

        else:
            merged.append(
                (
                    current_start,
                    current_end,
                )
            )

            next_start = max(
                piece_start,
                current_end - overlap,
            )

            current_start = next_start
            current_end = piece_end

    merged.append(
        (
            current_start,
            current_end,
        )
    )

    return merged


def split_page_into_chunks(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[dict]:
    """
    Split page text into paragraph-based chunks.
    """
    if not text.strip():
        return []

    segments = _get_segments(text)

    pieces: list[tuple[int, int]] = []

    for segment in segments:
        segment_length = segment[1] - segment[0]

        # Keep normal paragraphs complete.
        if segment_length <= chunk_size:
            pieces.append(segment)

        else:
            pieces.extend(
                _split_oversized(
                    text=text,
                    segment=segment,
                    chunk_size=chunk_size,
                )
            )

    pieces = _merge_pieces(
        pieces=pieces,
        chunk_size=chunk_size,
        overlap=overlap,
    )

    chunks: list[dict] = []

    for start, end in pieces:
        chunk_text = text[start:end].strip()

        if not chunk_text:
            continue

        chunks.append({
            "text": chunk_text,
            "char_start": start,
            "char_end": end,
        })

    return chunks


def chunk_document(
    pages: list[dict],
) -> list[dict]:
    """
    Convert extracted pages into searchable chunks.
    """
    chunks: list[dict] = []

    for page_data in pages:
        page_number = page_data.get("page")
        page_text = page_data.get("text", "")
        page_type = page_data.get(
            "page_type",
            "content",
        )

        if not page_text.strip():
            continue

        page_chunks = split_page_into_chunks(
            text=page_text,
        )

        for chunk_index, chunk in enumerate(
            page_chunks,
            start=1,
        ):
            chunks.append({
                "chunk_id": len(chunks) + 1,
                "page": page_number,
                "chunk_index": chunk_index,
                "is_toc": page_type == "toc",
                "is_cover": page_type == "cover",
                "page_type": page_type,
                **chunk,
            })

    return chunks


# ============================================================================
# PUBLIC ENTRY POINT
# ============================================================================

def extract_document(
    file_path: str,
) -> dict:
    """
    Extract pages and chunks from PDF or DOCX.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Document not found: {file_path}"
        )

    extension = path.suffix.lower()

    if extension == ".pdf":
        pages = extract_pdf_pages(
            file_path=str(path),
        )

    elif extension == ".docx":
        pages = extract_docx_pages(
            file_path=str(path),
        )

    else:
        raise ValueError(
            "Only PDF and DOCX files are supported"
        )

    chunks = chunk_document(
        pages=pages,
    )

    return {
        "pages": pages,
        "chunks": chunks,
    }


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "extract_document",
    "extract_pdf_pages",
    "extract_docx_pages",
    "split_page_into_chunks",
    "chunk_document",
    "classify_page",
]