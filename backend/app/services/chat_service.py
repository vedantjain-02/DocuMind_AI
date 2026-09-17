import json
import logging
import os
import re
from datetime import datetime, timezone
from functools import lru_cache
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI


logger = logging.getLogger("documind.chat")


# ============================================================================
# ENVIRONMENT AND CONFIGURATION
# ============================================================================

load_dotenv()

# backend/app/services/chat_service.py
# parents[0] = services
# parents[1] = app
# parents[2] = backend
BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")
load_dotenv()

from app.config import get_llm_config

DOCUMENT_DIR = BASE_DIR / "data" / "documents"

_api_key, _base_url, _model_name = get_llm_config()
if _api_key and _api_key != "gsk_your_actual_key_here":
    try:
        client = OpenAI(api_key=_api_key, base_url=_base_url)
    except Exception:
        client = None
else:
    client = None
llm_client = client

model = _model_name
MODEL_NAME = model

UNAVAILABLE_MESSAGE = (
    "This information is not available in the uploaded document."
)

MAX_CONTEXT_CHARS = 14000
MAX_SOURCE_TEXT_CHARS = 1800
MAX_PREVIEW_CHARS = 300
MAX_SOURCE_PAGES = 3


def require_client() -> OpenAI:
    """Return the configured OpenAI-compatible client or raise a clear error."""
    global client, llm_client
    api_key, base_url, _ = get_llm_config()
    if not api_key or api_key == "gsk_your_actual_key_here":
        raise RuntimeError(
            "XAI_API_KEY is missing. Please add your API key (XAI_API_KEY or GROQ_API_KEY) to backend/.env"
        )
    if client is None or getattr(client, "base_url", None) != base_url:
        client = OpenAI(api_key=api_key, base_url=base_url)
        llm_client = client
    return client


def _first_sentence(text: str) -> str:
    cleaned = clean_text(text)
    if not cleaned:
        return "This document contains no readable text."

    match = re.split(r"(?<=[.!?])\s+", cleaned)
    sentence = match[0].strip()
    if sentence:
        return sentence[:240]
    return cleaned[:240]


def _normalize_summary_entry(value: str) -> str:
    cleaned = clean_text(value or "")
    if not cleaned:
        return ""
    cleaned = cleaned.replace("**", "").replace("##", "")
    return cleaned.strip()


def _section_lines(section_text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in section_text.splitlines():
        line = _normalize_summary_entry(raw_line)
        if not line:
            continue
        if line.startswith("- ") or line.startswith("* "):
            lines.append(line[2:].strip())
        else:
            lines.append(line)
    unique: list[str] = []
    seen: set[str] = set()
    for item in lines:
        item = item.strip()
        if not item or item in seen:
            continue
        unique.append(item)
        seen.add(item)
    return unique[:8]


def _build_structured_summary(summary_text: str, filename: str, document_id: str) -> dict:
    raw_summary = (summary_text or "").strip()
    if not raw_summary:
        return {
            "document_id": document_id,
            "filename": filename,
            "overview": "This document contains no readable text.",
            "main_topics": [],
            "important_points": [],
            "key_takeaways": [],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_count": 0,
            "status": "empty",
        }

    sections: dict[str, list[str]] = {
        "overview": [],
        "main_topics": [],
        "important_points": [],
        "key_takeaways": [],
    }

    current_section = "overview"
    section_pattern = re.compile(r"^##\s*(.+?)\s*$", re.IGNORECASE)
    for raw_line in raw_summary.splitlines():
        heading_match = section_pattern.match(raw_line.strip())
        if heading_match:
            heading = heading_match.group(1).strip().lower()
            if "overview" in heading or "main topic" in heading:
                current_section = "overview"
            elif "important section" in heading or "key concept" in heading or "important definitions" in heading:
                current_section = "important_points"
            elif "main findings" in heading or "conclusion" in heading:
                current_section = "key_takeaways"
            else:
                current_section = "main_topics"
            continue

        value = _normalize_summary_entry(raw_line)
        if not value:
            continue
        if value.startswith("- ") or value.startswith("* "):
            value = value[2:].strip()
        if value:
            sections[current_section].append(value)

    overview = " ".join(sections["overview"]) or _first_sentence(raw_summary)
    main_topics = sections["main_topics"] or _section_lines(raw_summary)[:3]
    important_points = sections["important_points"] or _section_lines(raw_summary)[3:6] or [overview]
    key_takeaways = sections["key_takeaways"] or _section_lines(raw_summary)[6:9] or [overview]

    return {
        "document_id": document_id,
        "filename": filename,
        "overview": overview[:600],
        "main_topics": main_topics[:6],
        "important_points": important_points[:6],
        "key_takeaways": key_takeaways[:6],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "processed",
    }


@lru_cache(maxsize=128)
def generate_document_summary(document_id: str) -> dict:
    """Build a concise structured summary from the stored document text."""
    document_id = str(document_id).strip()
    if not document_id:
        raise ValueError("document_id is required")

    document = load_document(document_id)
    chunks = get_all_document_chunks(document_id)
    if not chunks:
        return {
            "document_id": document_id,
            "filename": document.get("filename", "Document"),
            "overview": "This document contains no readable text.",
            "main_topics": [],
            "important_points": [],
            "key_takeaways": [],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_count": 0,
            "status": "empty",
        }

    result = summarize_document(document_id=document_id)
    summary_text = (result.get("answer") or "").strip()
    summary = _build_structured_summary(summary_text, document.get("filename", "Document"), document_id)
    summary["source_count"] = len(result.get("sources") or [])
    return summary


# ============================================================================
# BASIC TEXT HELPERS
# ============================================================================


def normalize_whitespace(text: str) -> str:
    """
    Converts multiple spaces, tabs and line breaks into single spaces.
    This is useful for OCR/PDF text matching.
    """
    if not text:
        return ""

    return " ".join(str(text).split()).strip()


def clean_text(text: str) -> str:
    """
    Cleans extracted PDF/OCR text.
    """
    if not text:
        return ""

    value = str(text)

    value = value.replace("\x00", " ")
    value = value.replace("\ufeff", " ")
    value = value.replace("\ufffd", " ")

    return normalize_whitespace(value)


def normalize_page_number(page: Any) -> int | None:
    """
    Converts:
        1
        "1"
        "Page 1"
        "page: 1"
    into:
        1
    """
    if page is None:
        return None

    if isinstance(page, bool):
        return None

    if isinstance(page, int):
        return page

    if isinstance(page, float):
        return int(page)

    value = str(page).strip()

    if not value:
        return None

    match = re.search(r"\d+", value)

    if not match:
        return None

    try:
        return int(match.group())
    except ValueError:
        return None


def tokenize(text: str) -> set[str]:
    """
    Returns lowercase word tokens.
    """
    return set(
        re.findall(
            r"[a-zA-Z0-9]+",
            clean_text(text).lower(),
        )
    )


def split_sentences(text: str) -> list[str]:
    """
    Splits text into sentences.
    """
    value = clean_text(text)

    if not value:
        return []

    parts = re.split(
        r"(?<=[.!?])\s+|(?<=:)\s+(?=[A-Z0-9])",
        value,
    )

    return [
        clean_text(part)
        for part in parts
        if clean_text(part)
    ]


# ============================================================================
# DOCUMENT LOADING
# ============================================================================

def load_document(document_id: str) -> dict:
    """
    Loads the JSON document generated during upload.
    """
    document_id = str(document_id).strip()

    document_path = DOCUMENT_DIR / f"{document_id}.json"

    if not document_path.exists():
        raise FileNotFoundError(
            f"Document not found: {document_path}"
        )

    return json.loads(
        document_path.read_text(
            encoding="utf-8"
        )
    )


def load_documents(document_ids: list[str]) -> list[dict]:
    """Load multiple documents in order while preserving unique IDs."""
    if not document_ids:
        return []

    unique_ids: list[str] = []
    seen: set[str] = set()

    for document_id in document_ids:
        value = str(document_id).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        unique_ids.append(value)

    documents: list[dict] = []
    for document_id in unique_ids:
        documents.append(load_document(document_id))

    return documents


# ============================================================================
# TEXT MATCHING
# ============================================================================

def find_text_span(
    page_text: str,
    quote: str,
) -> tuple[int, int] | None:
    """
    Finds quote inside page text after whitespace normalization.

    Returned offsets are relative to normalized page text.

    Example:

        page_text = "Operating   system manages processes."
        quote = "Operating system manages processes."

    Returns the matching character range.
    """
    if not page_text or not quote:
        return None

    normalized_page = normalize_whitespace(page_text)
    normalized_quote = normalize_whitespace(quote)

    if not normalized_page or not normalized_quote:
        return None

    start = normalized_page.lower().find(
        normalized_quote.lower()
    )

    if start == -1:
        return None

    return (
        start,
        start + len(normalized_quote),
    )


def quote_is_in_page(
    page_text: str,
    quote: str,
) -> bool:
    """
    Checks whether a quote exists in page text.

    Short quotes are ignored because they can create false highlights.
    """
    if not page_text or not quote:
        return False

    normalized_quote = normalize_whitespace(quote)

    if len(normalized_quote) < 12:
        return False

    normalized_page = normalize_whitespace(page_text)

    return (
        normalized_quote.lower()
        in normalized_page.lower()
    )


# ============================================================================
# PAGE CONTEXT
# ============================================================================

def build_page_context(
    retrieved_chunks: list[dict],
    pages: list[dict],
) -> tuple[str, dict]:
    """
    Groups retrieved chunks by page and builds model context.

    Returns:

        context_text

        page_lookup:
        {
            1: "complete page text",
            2: "complete page text"
        }
    """

    page_chunks: dict[int | None, list[dict]] = {}
    page_order: list[int | None] = []

    for chunk in retrieved_chunks:
        page = normalize_page_number(
            chunk.get("page")
        )

        if page not in page_chunks:
            page_chunks[page] = []
            page_order.append(page)

        page_chunks[page].append(chunk)

    context_parts: list[str] = []
    page_lookup: dict[int | None, str] = {}

    for page in page_order:
        chunk_texts: list[str] = []

        for chunk in page_chunks[page]:
            text = clean_text(
                chunk.get("text", "")
            )

            if text:
                chunk_texts.append(text)

        page_text = "\n\n".join(
            chunk_texts
        ).strip()

        if not page_text:
            continue

        page_lookup[page] = page_text

        label = (
            f"Page {page}"
            if page is not None
            else "Document"
        )

        context_parts.append(
            f"--- {label} ---\n{page_text}"
        )

    # Add complete page text for source verification.
    for page_data in pages or []:
        page_number = normalize_page_number(
            page_data.get("page")
        )

        page_text = clean_text(
            page_data.get("text", "")
        )

        if not page_text:
            continue

        if page_number not in page_lookup:
            page_lookup[page_number] = page_text

    context = "\n\n".join(context_parts)

    if len(context) > MAX_CONTEXT_CHARS:
        context = context[:MAX_CONTEXT_CHARS]

    return context, page_lookup


# ============================================================================
# JSON RESPONSE PARSING
# ============================================================================

def extract_json_answer(
    content: str,
) -> tuple[str, list[dict]]:
    """
    Extracts model response in this format:

    {
        "answer": "...",
        "quotes": [
            {
                "page": 1,
                "text": "..."
            }
        ]
    }
    """
    if not content:
        return "", []

    raw = content.strip()

    # Remove markdown fences if model returns them.
    fenced_match = re.search(
        r"```(?:json)?\s*(.*?)```",
        raw,
        flags=re.DOTALL | re.IGNORECASE,
    )

    if fenced_match:
        raw = fenced_match.group(1).strip()

    object_start = raw.find("{")
    object_end = raw.rfind("}")

    if (
        object_start != -1
        and object_end > object_start
    ):
        raw = raw[
            object_start:object_end + 1
        ]

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return "", []

    if not isinstance(data, dict):
        return "", []

    answer = data.get("answer", "")
    quotes = data.get("quotes", [])

    if not isinstance(answer, str):
        answer = str(answer)

    if not isinstance(quotes, list):
        quotes = []

    return answer.strip(), quotes


# ============================================================================
# SOURCE TEXT SELECTION
# ============================================================================

def sentence_relevance_score(
    question: str,
    sentence: str,
) -> int:
    """
    Calculates basic keyword overlap.
    """
    question_tokens = tokenize(question)
    sentence_tokens = tokenize(sentence)

    if not question_tokens or not sentence_tokens:
        return 0

    return len(
        question_tokens.intersection(
            sentence_tokens
        )
    )


def extract_relevant_text(
    question: str,
    text: str,
    max_chars: int = MAX_SOURCE_TEXT_CHARS,
) -> str:
    """
    Returns a complete paragraph or a group of nearby sentences.

    Important:
    We do NOT return only one short sentence because the frontend
    should highlight a complete paragraph.
    """
    cleaned = clean_text(text)

    if not cleaned:
        return ""

    # If the chunk is already a reasonable paragraph, return the complete
    # chunk. This creates paragraph-level highlighting.
    if len(cleaned) <= max_chars:
        return cleaned

    sentences = split_sentences(cleaned)

    if not sentences:
        return cleaned[:max_chars]

    scored_sentences: list[dict] = []

    for index, sentence in enumerate(sentences):
        scored_sentences.append(
            {
                "index": index,
                "sentence": sentence,
                "score": sentence_relevance_score(
                    question=question,
                    sentence=sentence,
                ),
            }
        )

    best = max(
        scored_sentences,
        key=lambda item: (
            item["score"],
            -item["index"],
        ),
    )

    selected_indexes: set[int] = {
        best["index"]
    }

    # Add nearby sentences to preserve paragraph meaning.
    for item in scored_sentences:
        if item["index"] == best["index"]:
            continue

        if abs(
            item["index"] - best["index"]
        ) <= 2:
            selected_indexes.add(
                item["index"]
            )

    selected_sentences = [
        sentences[index]
        for index in sorted(selected_indexes)
    ]

    result = clean_text(
        " ".join(selected_sentences)
    )

    return result[:max_chars]


# ============================================================================
# FALLBACK SOURCE
# ============================================================================

def fallback_source_text(
    question: str,
    retrieved_chunks: list[dict],
    page: int | None,
) -> tuple[dict | None, str]:
    """
    Selects the best chunk for a page.

    The complete chunk is preferred so that the frontend can highlight
    a paragraph instead of a single sentence.
    """
    page_chunks: list[dict] = []

    for chunk in retrieved_chunks:
        chunk_page = normalize_page_number(
            chunk.get("page")
        )

        if chunk_page == page:
            page_chunks.append(chunk)

    if not page_chunks:
        return None, ""

    def chunk_score(chunk: dict) -> float:
        value = (
            chunk.get("relevance_score")
            or chunk.get("_score")
            or 0.0
        )

        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    best_chunk = max(
        page_chunks,
        key=chunk_score,
    )

    chunk_text = clean_text(
        best_chunk.get("text", "")
    )

    if not chunk_text:
        return best_chunk, ""

    # Prefer complete paragraph/chunk.
    if len(chunk_text) <= MAX_SOURCE_TEXT_CHARS:
        return best_chunk, chunk_text

    # For very large chunks, select nearby sentences.
    relevant_text = extract_relevant_text(
        question=question,
        text=chunk_text,
        max_chars=MAX_SOURCE_TEXT_CHARS,
    )

    return best_chunk, relevant_text


# ============================================================================
# SOURCE CREATION
# ============================================================================

def source_from_chunk(
    question: str,
    retrieved_chunks: list[dict],
    page_lookup: dict,
    page: int | None,
    document: dict | None = None,
) -> dict | None:
    """
    Creates the source object expected by frontend/app.py.
    """
    page = normalize_page_number(page)

    page_text = page_lookup.get(page, "")

    if not page_text:
        return None

    best_chunk, source_text = fallback_source_text(
        question=question,
        retrieved_chunks=retrieved_chunks,
        page=page,
    )

    if best_chunk is None:
        return None

    if not source_text:
        source_text = clean_text(
            best_chunk.get("text", "")
        )

    source_text = source_text[:MAX_SOURCE_TEXT_CHARS]

    span = find_text_span(
        page_text=page_text,
        quote=source_text,
    )

    character_start = span[0] if span else best_chunk.get("char_start")
    character_end = span[1] if span else best_chunk.get("char_end")

    score = best_chunk.get("relevance_score") or best_chunk.get("_score") or 0.0
    try:
        score = round(float(score), 4)
    except (TypeError, ValueError):
        score = 0.0

    source = {
        "page": page,
        "chunk_id": best_chunk.get("chunk_id"),
        "chunk_index": best_chunk.get("chunk_index"),
        "title": f"Page {page}" if page is not None else "Document",
        "exact_text": source_text,
        "preview": source_text[:MAX_PREVIEW_CHARS],
        "relevance_score": score,
        "character_start": character_start,
        "character_end": character_end,
    }

    if document:
        source["document_id"] = document.get("document_id")
        source["filename"] = document.get("filename")
        source["file_type"] = document.get("file_type")
        if source.get("title") == "Document":
            source["title"] = document.get("filename") or "Document"

    return source


# ============================================================================
# FRESH SOURCE CREATION (RETRIEVAL ONLY)
# ============================================================================

def _document_page_text(
    document: dict | None,
    page: int | None,
) -> str:
    """
    Returns the normalized text of a page that belongs to a document record.
    Used only to sanity-check that a chunk really lives on the page.
    """
    if not isinstance(document, dict):
        return ""

    for page_data in document.get("pages", []) or []:
        if normalize_page_number(page_data.get("page")) == page:
            return clean_text(page_data.get("text", ""))

    return ""


def normalize_text_for_matching(text: str) -> str:
    """Normalize text by lowercasing, stripping punctuation, and collapsing whitespace."""
    if not text:
        return ""
    no_punct = re.sub(r"[^\w\s]", " ", str(text).lower())
    return " ".join(no_punct.split())


STOPWORDS = {
    "a", "an", "the", "in", "on", "at", "to", "for", "of", "and", "or", "is",
    "are", "was", "were", "be", "been", "by", "as", "it", "its", "this", "that",
    "these", "those", "with", "from", "into", "can", "could", "will", "would",
    "should", "have", "has", "had", "do", "does", "did", "but", "not", "what",
    "which", "who", "whom", "how", "when", "where", "why", "we", "you", "they",
    "i", "he", "she", "our", "your", "their", "my", "his", "her", "all", "so",
    "such", "also", "than", "then", "just", "very", "any", "some"
}


def match_ocr_boxes(
    target_text: str,
    ocr_lines: list[dict],
    ocr_words: list[dict] | None = None,
    secondary_text: str | None = None,
) -> tuple[str, dict | None, list[dict], float | None, str]:
    """
    Robust multi-stage matcher between target/source text and OCR regions.
    Returns:
        (matched_ocr_text, overall_bbox, merged_bboxes, confidence, match_type)
    """
    if not ocr_lines:
        return "", None, [], None, "none"

    norm_target = normalize_text_for_matching(target_text)
    norm_secondary = normalize_text_for_matching(secondary_text or "")

    logger.info("[DocuMind Matcher] Input target_text: %s", (target_text or "")[:120])
    logger.info("[DocuMind Matcher] Normalized target: %s", norm_target[:120])
    logger.info("[DocuMind Matcher] Total OCR lines: %d", len(ocr_lines))

    norm_lines = [
        {
            "line": line,
            "norm_text": normalize_text_for_matching(line.get("text", "")),
            "tokens": set(normalize_text_for_matching(line.get("text", "")).split()),
            "block_num": line.get("block_num", 0),
            "line_num": line.get("line_num", 0),
        }
        for line in ocr_lines
        if line.get("text", "").strip()
    ]

    matched_lines: list[dict] = []
    match_type = "exact"

    # STAGE 1: Exact line or substring match in target_text or secondary_text
    for item in norm_lines:
        nt = item["norm_text"]
        if not nt:
            continue
        if len(nt) >= 5 and (nt in norm_target or norm_target in nt):
            matched_lines.append(item["line"])
        elif norm_secondary and len(nt) >= 5 and (nt in norm_secondary or norm_secondary in nt):
            matched_lines.append(item["line"])

    # Check joined neighboring OCR items (pairs of adjacent lines)
    if not matched_lines:
        for i in range(len(norm_lines) - 1):
            joined = norm_lines[i]["norm_text"] + " " + norm_lines[i+1]["norm_text"]
            if len(joined) >= 8 and (joined in norm_target or norm_target in joined):
                if norm_lines[i]["line"] not in matched_lines:
                    matched_lines.append(norm_lines[i]["line"])
                if norm_lines[i+1]["line"] not in matched_lines:
                    matched_lines.append(norm_lines[i+1]["line"])

    # STAGE 2: Phrase / Shingle window matching (4-word, 3-word shingles)
    if not matched_lines:
        target_words = norm_target.split()
        if norm_secondary:
            target_words = target_words + [w for w in norm_secondary.split() if w not in target_words]

        shingles = []
        for n in (4, 3):
            for i in range(len(target_words) - n + 1):
                phrase = " ".join(target_words[i:i+n])
                if phrase:
                    shingles.append(phrase)

        for shingle in shingles:
            for item in norm_lines:
                if shingle in item["norm_text"]:
                    if item["line"] not in matched_lines:
                        matched_lines.append(item["line"])
            if len(matched_lines) >= 3:
                break

        if matched_lines:
            match_type = "phrase"

    # STAGE 3: Meaningful keyword matching
    if not matched_lines:
        keywords = set()
        for text_source in (norm_target, norm_secondary):
            for word in text_source.split():
                if len(word) >= 3 and word not in STOPWORDS:
                    keywords.add(word)

        if keywords:
            scored_lines = []
            for item in norm_lines:
                overlap = item["tokens"].intersection(keywords)
                if overlap:
                    score = len(overlap)
                    scored_lines.append((score, item["line"]))

            if scored_lines:
                scored_lines.sort(key=lambda x: x[0], reverse=True)
                max_score = scored_lines[0][0]
                min_threshold = max(1, max_score // 2)
                for score, line in scored_lines:
                    if score >= min_threshold:
                        matched_lines.append(line)
                    if len(matched_lines) >= 5:
                        break
                if matched_lines:
                    match_type = "keyword"

    # STAGE 4: Word-level matching fallback
    matched_words_list: list[dict] = []
    if not matched_lines and ocr_words:
        keywords = set()
        for text_source in (norm_target, norm_secondary):
            for word in text_source.split():
                if len(word) >= 3 and word not in STOPWORDS:
                    keywords.add(word)

        if keywords:
            for w in ocr_words:
                wt = normalize_text_for_matching(w.get("text", ""))
                if wt in keywords:
                    matched_words_list.append(w)
            if matched_words_list:
                match_type = "keyword"

    # STAGE 5: Box Merging & Output Construction
    if not matched_lines and not matched_words_list:
        logger.info("[DocuMind Matcher] No OCR regions matched target text.")
        return "", None, [], None, "none"

    if matched_lines:
        sorted_items = sorted(matched_lines, key=lambda l: (l["bbox"]["y"], l["bbox"]["x"]))
        raw_boxes = [item["bbox"] for item in sorted_items]
        confs = [item.get("confidence", 0.9) for item in sorted_items]
        matched_ocr_text = " ".join(item["text"].strip() for item in sorted_items if item.get("text"))
    else:
        sorted_items = sorted(matched_words_list, key=lambda w: (w["bbox"]["y"], w["bbox"]["x"]))
        raw_boxes = [item["bbox"] for item in sorted_items]
        confs = [item.get("confidence", 0.9) for item in sorted_items]
        matched_ocr_text = " ".join(item["text"].strip() for item in sorted_items if item.get("text"))

    merged_bboxes: list[dict] = []
    current_box = dict(raw_boxes[0])

    for next_box in raw_boxes[1:]:
        vert_gap = next_box["y"] - (current_box["y"] + current_box["height"])
        avg_h = (current_box["height"] + next_box["height"]) / 2.0
        horiz_overlap = (
            min(current_box["x"] + current_box["width"], next_box["x"] + next_box["width"])
            - max(current_box["x"], next_box["x"])
        )

        if vert_gap <= avg_h * 1.8 and (horiz_overlap > -60 or abs(next_box["x"] - current_box["x"]) < 100):
            new_x = min(current_box["x"], next_box["x"])
            new_y = min(current_box["y"], next_box["y"])
            new_right = max(current_box["x"] + current_box["width"], next_box["x"] + next_box["width"])
            new_bottom = max(current_box["y"] + current_box["height"], next_box["y"] + next_box["height"])
            current_box = {
                "x": new_x,
                "y": new_y,
                "width": max(1, new_right - new_x),
                "height": max(1, new_bottom - new_y),
            }
        else:
            merged_bboxes.append(current_box)
            current_box = dict(next_box)

    merged_bboxes.append(current_box)

    min_x = min(b["x"] for b in raw_boxes)
    min_y = min(b["y"] for b in raw_boxes)
    max_x = max(b["x"] + b["width"] for b in raw_boxes)
    max_y = max(b["y"] + b["height"] for b in raw_boxes)

    overall_bbox = {
        "x": min_x,
        "y": min_y,
        "width": max(1, max_x - min_x),
        "height": max(1, max_y - min_y),
    }

    avg_conf = round(sum(confs) / max(1, len(confs)), 3)

    logger.info("[DocuMind Matcher] Match successful (type: %s)", match_type)
    logger.info("[DocuMind Matcher] Matched OCR text: %s", matched_ocr_text[:120])
    logger.info("[DocuMind Matcher] Overall bbox: %s", overall_bbox)
    logger.info("[DocuMind Matcher] Merged boxes count: %d", len(merged_bboxes))

    return matched_ocr_text, overall_bbox, merged_bboxes, avg_conf, match_type


def build_document_sources(
    retrieved_chunks: list[dict],
    document_map: dict[str, dict],
    max_sources: int = MAX_SOURCE_PAGES,
    answer_text: str | None = None,
) -> list[dict]:
    """
    Builds fresh source records directly from the retrieval result.

    The source text is the exact chunk text stored in the document JSON.
    Page numbers come from the chunk metadata, never from the LLM.

    Rules enforced here:

    - One source per (document_id, page).
    - Chunks that do not belong to an uploaded document are dropped.
    - Sources without usable text are skipped.
    - No LLM-generated quote is ever used as source text.
    - For image documents, computes matching bounding box coordinates and dimensions.
    """
    if not retrieved_chunks or not document_map:
        return []

    page_groups: dict[tuple[str, int], list[dict]] = {}
    page_order: list[tuple[str, int]] = []

    for chunk in retrieved_chunks:
        page = normalize_page_number(chunk.get("page"))
        if page is None:
            page = 1

        text = clean_text(chunk.get("text", ""))
        if not text:
            continue

        document_id = str(chunk.get("document_id") or "").strip()
        if not document_id or document_id not in document_map:
            continue

        page_text = _document_page_text(
            document_map.get(document_id),
            page,
        )
        if not page_text:
            doc_pages = document_map.get(document_id, {}).get("pages", [])
            if doc_pages:
                page_text = clean_text(doc_pages[0].get("text", ""))

        if not page_text:
            continue

        if not find_text_span(page_text=page_text, quote=text) and text.lower() not in page_text.lower():
            continue

        try:
            score = float(
                chunk.get("relevance_score")
                or chunk.get("_score")
                or 0.0
            )
        except (TypeError, ValueError):
            score = 0.0

        key = (document_id, page)
        if key not in page_groups:
            page_groups[key] = []
            page_order.append(key)
        page_groups[key].append({"chunk": chunk, "score": score})

    if not page_order:
        return []

    ranked_pages = sorted(
        page_order,
        key=lambda key: max(
            item["score"]
            for item in page_groups[key]
        ),
        reverse=True,
    )

    sources: list[dict] = []
    seen_key: set[tuple[str, int]] = set()

    for key in ranked_pages:
        if key in seen_key:
            continue
        seen_key.add(key)

        document_id, page = key
        document = document_map.get(document_id)
        if document is None:
            continue

        best = max(
            page_groups[key],
            key=lambda item: item["score"],
        )
        chunk = best["chunk"]

        exact_text = clean_text(chunk.get("text", ""))
        if not exact_text:
            continue
        exact_text = exact_text[:MAX_SOURCE_TEXT_CHARS]

        file_type = str(document.get("file_type", "")).lower()
        bbox = None
        bboxes = []
        img_w = None
        img_h = None
        conf = None
        all_ocr = []
        match_type = None
        matched_text = ""

        if file_type in ("png", "jpg", "jpeg", "webp"):
            source_title = f"{document.get('filename', 'Image')} · Image"
            ocr_lines = chunk.get("ocr_lines")
            ocr_words = chunk.get("ocr_words")
            img_w = chunk.get("image_width") or document.get("image_width")
            img_h = chunk.get("image_height") or document.get("image_height")
            all_ocr = chunk.get("all_ocr_bboxes") or document.get("all_ocr_bboxes") or []

            doc_pages = document.get("pages", [])
            if doc_pages and (not ocr_lines or not img_w):
                first_p = doc_pages[0]
                ocr_lines = ocr_lines or first_p.get("ocr_lines", [])
                ocr_words = ocr_words or first_p.get("ocr_words", [])
                img_w = img_w or first_p.get("image_width")
                img_h = img_h or first_p.get("image_height")
                all_ocr = all_ocr or first_p.get("all_ocr_bboxes", [])

            # Lazy extraction fallback: If document was saved before OCR bounding boxes were stored,
            # load the image from disk and extract them right now!
            if not ocr_lines and document.get("file_path"):
                try:
                    from app.services.ocr_service import extract_ocr_data
                    fp = Path(document["file_path"])
                    if fp.exists():
                        fresh_ocr = extract_ocr_data(fp.read_bytes())
                        ocr_lines = fresh_ocr.get("lines", [])
                        ocr_words = fresh_ocr.get("words", [])
                        img_w = fresh_ocr.get("image_width")
                        img_h = fresh_ocr.get("image_height")
                        all_ocr = fresh_ocr.get("all_ocr_bboxes", [])
                        document["ocr_lines"] = ocr_lines
                        document["ocr_words"] = ocr_words
                        document["image_width"] = img_w
                        document["image_height"] = img_h
                        document["all_ocr_bboxes"] = all_ocr
                        if doc_pages:
                            doc_pages[0]["ocr_lines"] = ocr_lines
                            doc_pages[0]["ocr_words"] = ocr_words
                            doc_pages[0]["image_width"] = img_w
                            doc_pages[0]["image_height"] = img_h
                            doc_pages[0]["all_ocr_bboxes"] = all_ocr
                        doc_json_path = DOCUMENT_DIR / f"{document_id}.json"
                        if doc_json_path.exists():
                            doc_json_path.write_text(
                                json.dumps(document, ensure_ascii=False, indent=2),
                                encoding="utf-8",
                            )
                except Exception as ex:
                    logger.warning("[DocuMind AI] Lazy OCR extraction failed for %s: %s", document_id, ex)

            if ocr_lines:
                matched_text, bbox, bboxes, conf, match_type = match_ocr_boxes(
                    target_text=exact_text,
                    ocr_lines=ocr_lines,
                    ocr_words=ocr_words,
                    secondary_text=answer_text,
                )

        elif file_type == "docx":
            source_title = f"{document.get('filename', 'Document')} · Section"
        else:
            source_title = f"{document.get('filename', 'Document')} · Page {page}"

        final_source_text = matched_text if matched_text else exact_text

        source = {
            "page": page,
            "document_id": document.get("document_id"),
            "filename": document.get("filename"),
            "file_type": document.get("file_type"),
            "chunk_id": chunk.get("chunk_id"),
            "chunk_index": chunk.get("chunk_index"),
            "title": source_title,
            "exact_text": final_source_text,
            "text": final_source_text,
            "preview": final_source_text[:MAX_PREVIEW_CHARS],
            "relevance_score": round(best["score"], 4),
            "character_start": chunk.get("char_start"),
            "character_end": chunk.get("char_end"),
            "bbox": bbox,
            "bboxes": bboxes,
            "image_width": img_w,
            "image_height": img_h,
            "confidence": conf,
            "all_ocr_bboxes": all_ocr,
            "match_type": match_type,
        }
        sources.append(source)

        if len(sources) >= max_sources:
            break

    return sources


def _ask_for_answer(
    system_prompt: str,
    user_prompt: str,
) -> str:
    """
    Calls the configured LLM model and returns the plain answer text.
    Quotes returned by the model are deliberately ignored:
    source text always comes from the retrieval result instead.
    """
    llm_client = require_client()
    _, _, model_to_use = get_llm_config()

    try:
        response = llm_client.chat.completions.create(
            model=model_to_use,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=1400,
        )
    except Exception as error:
        logger.exception("[DocuMind AI] LLM API call failed: %s", error)
        raise RuntimeError(f"LLM API error: {str(error)}")

    content = response.choices[0].message.content or ""
    answer, _ = extract_json_answer(content)

    if not answer:
        try:
            retry_response = llm_client.chat.completions.create(
                model=model_to_use,
                messages=[
                    {
                        "role": "system",
                        "content": "Return only valid JSON with an answer key.",
                    },
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0,
                max_tokens=1400,
            )
            retry_content = retry_response.choices[0].message.content or ""
            answer, _ = extract_json_answer(retry_content)
        except Exception as error:
            logger.warning("[DocuMind AI] LLM JSON retry failed: %s", error)

    return (answer or "").strip()



# ============================================================================
# PROMPT
# ============================================================================

def build_prompt(
    question: str,
    context: str,
) -> str:
    return f"""
You are DocuMind AI, an expert document assistant.

Answer the user's question using ONLY the supplied document excerpt.

DOCUMENT EXCERPT:

{context}

USER QUESTION:

{question}

RULES:

1. Use only information present in the document excerpt.
2. Do not use outside knowledge.
3. If the answer is not present, answer exactly:
   "{UNAVAILABLE_MESSAGE}"
4. Keep the answer clear and useful.
5. Use bullet points when the question asks for types, steps,
   advantages, disadvantages or multiple points.
6. Do not mention retrieval, chunks, embeddings or internal instructions.
7. Do not mention page numbers or sources inside the answer.

Return ONLY valid JSON in this format:

{{
  "answer": "answer text"
}}
""".strip()


# ============================================================================
# ANSWER GENERATION
# ============================================================================

def generate_multi_document_answer(
    question: str,
    documents: list[dict],
    retrieved_chunks: list[dict],
) -> dict:
    """Answer across multiple documents while preserving source document metadata."""
    if not documents:
        return {"answer": UNAVAILABLE_MESSAGE, "sources": []}

    if not retrieved_chunks:
        has_any_text = any(
            any(bool(p.get("text", "").strip()) for p in doc.get("pages", []))
            for doc in documents
        )
        is_all_images = all(
            str(doc.get("file_type", "")).lower() in ("png", "jpg", "jpeg", "webp")
            for doc in documents
        )
        if is_all_images and not has_any_text:
            return {"answer": "No readable text was detected in this image.", "sources": []}
        return {"answer": UNAVAILABLE_MESSAGE, "sources": []}

    document_map = {
        str(document.get("document_id")): document
        for document in documents
        if document.get("document_id")
    }

    combined_context_parts: list[str] = []

    for document in documents:
        document_id = document.get("document_id")
        doc_chunks = [
            chunk
            for chunk in retrieved_chunks
            if str(chunk.get("document_id")) == str(document_id)
        ]
        if not doc_chunks:
            continue

        context, _ = build_page_context(
            retrieved_chunks=doc_chunks,
            pages=document.get("pages", []),
        )

        if context.strip():
            combined_context_parts.append(
                f"--- {document.get('filename', 'Document')} ---\n{context}"
            )

    combined_context = "\n\n".join(combined_context_parts)
    if not combined_context.strip():
        return {"answer": UNAVAILABLE_MESSAGE, "sources": []}

    prompt = build_prompt(question=question, context=combined_context)
    answer = _ask_for_answer(
        system_prompt="You are DocuMind AI. Answer only from the supplied documents and return valid JSON only.",
        user_prompt=prompt,
    )
    answer = answer or UNAVAILABLE_MESSAGE

    if answer == UNAVAILABLE_MESSAGE:
        return {"answer": UNAVAILABLE_MESSAGE, "sources": []}

    sources = build_document_sources(
        retrieved_chunks=retrieved_chunks,
        document_map=document_map,
        answer_text=answer,
    )

    return {"answer": answer, "sources": sources}


def generate_answer(
    question: str,
    document: dict | list[dict],
    retrieved_chunks: list[dict],
    document_ids: list[str] | None = None,
    documents: list[dict] | None = None,
) -> dict:
    """
    Generates a grounded answer with sources.

    Sources are always built from the retrieval result using real chunk text.
    LLM-generated quotes are never used as source text.
    """
    if isinstance(document, list):
        documents = document or documents or []
        if len(documents) > 1:
            return generate_multi_document_answer(
                question=question,
                documents=documents,
                retrieved_chunks=retrieved_chunks,
            )
        document = documents[0] if documents else {}

    if document_ids and documents and len(documents) > 1:
        return generate_multi_document_answer(
            question=question,
            documents=documents,
            retrieved_chunks=retrieved_chunks,
        )

    pages = document.get("pages", []) if isinstance(document, dict) else []

    if not retrieved_chunks:
        has_any_text = any(bool(p.get("text", "").strip()) for p in pages)
        is_image = str(document.get("file_type", "")).lower() in ("png", "jpg", "jpeg", "webp")
        if is_image and not has_any_text:
            return {"answer": "No readable text was detected in this image.", "sources": []}
        return {"answer": UNAVAILABLE_MESSAGE, "sources": []}

    context, _page_lookup = build_page_context(
        retrieved_chunks=retrieved_chunks,
        pages=pages,
    )

    if not context.strip():
        has_any_text = any(bool(p.get("text", "").strip()) for p in pages)
        is_image = str(document.get("file_type", "")).lower() in ("png", "jpg", "jpeg", "webp")
        if is_image and not has_any_text:
            return {"answer": "No readable text was detected in this image.", "sources": []}
        return {"answer": UNAVAILABLE_MESSAGE, "sources": []}

    prompt = build_prompt(question=question, context=context)
    answer = _ask_for_answer(
        system_prompt=(
            "You are DocuMind AI. Answer only from the supplied "
            "document and return valid JSON only."
        ),
        user_prompt=prompt,
    )

    answer = answer or UNAVAILABLE_MESSAGE

    if answer == UNAVAILABLE_MESSAGE:
        return {"answer": UNAVAILABLE_MESSAGE, "sources": []}

    document_map: dict[str, dict] = {}
    if isinstance(document, dict) and document.get("document_id"):
        document_map[str(document["document_id"])] = document
    for doc in documents or []:
        if doc.get("document_id"):
            document_map.setdefault(
                str(doc["document_id"]),
                doc,
            )

    sources = build_document_sources(
        retrieved_chunks=retrieved_chunks,
        document_map=document_map,
        answer_text=answer,
    )

    return {"answer": answer, "sources": sources}


# ============================================================================
# FULL-DOCUMENT SUMMARIZATION
# ============================================================================

def is_summary_request(question: str) -> bool:
    """
    Detects whether a user query is asking for a full-document summary or overview
    before performing normal RAG retrieval.
    """
    if not question or not isinstance(question, str):
        return False

    q = question.strip().lower()

    clean_q = re.sub(
        r"[^\w\s-]",
        " ",
        q,
    )

    clean_q = " ".join(
        clean_q.split()
    )

    # Specific section/chapter/page queries should go through normal RAG
    if re.search(r"\b(section|chapter|part|page)\s+\d+\b", clean_q):
        return False

    summary_patterns = [
    # Correct spellings
    r"\b(summarize|summarise|summary)\b",

    # Common spelling mistakes
    r"\b(summerize|summerise|summery)\b",

    # Overview and recap
    r"\b(overview|synopsis|tldr|tl\s*dr|recap)\b",

    # What is the document about?
    r"\bwhat\s+(is|are)\s+(this|the)\s+"
    r"(document|pdf|file|paper|text|book|upload|image|photo|picture)\s+about\b",

    r"\bwhat\s+is\s+it\s+about\b",

    r"\bwhat\s+is\s+(this|the)\s+about\b",

    # Main topic
    r"\b(main\s+topic|main\s+theme|main\s+subject|"
    r"core\s+topic|main\s+idea|key\s+theme)\b",

    # Explain complete document
    r"\bexplain\s+(the\s+)?"
    r"(whole|entire|complete|all\s+of\s+the|uploaded)"
    r"\s*(document|pdf|file|paper|text|image)?\b",

    r"\bexplain\s+(this|the)\s+"
    r"(document|pdf|file|paper|image|picture)\b",

    # Give me an overview
    r"\bgive\s+(me\s+)?(an?\s+)?overview\b",

    # Give me the summary
    r"\bgive\s+(me\s+)?(the\s+)?summary\b",

    # Document summary
    r"\b(document|pdf|file|paper|image|picture)\s+summary\b",

    # Outline and breakdown
    r"\b(outline|breakdown)\s+of\s+"
    r"(this|the)\s+(document|pdf|file|paper|image)\b",

    # Walkthrough
    r"\b(walk\s+me\s+through|walkthrough\s+of)\s+"
    r"(this|the)\s+(document|pdf|file|paper|image)\b",
]


    for pattern in summary_patterns:
        if re.search(pattern, clean_q):
            return True

    return False


def get_all_document_chunks(document_id: str) -> list[dict]:
    """
    Fetches all chunks for a document sorted strictly in original document order:
    1. By page number (ascending)
    2. By chunk_index / chunk_id (ascending)
    """
    if not document_id or not str(document_id).strip():
        raise ValueError("document_id is required")

    document = load_document(document_id)
    chunks = document.get("chunks", [])

    # If no chunks exist but pages exist, build chunk objects from pages
    if not chunks and document.get("pages"):
        chunks = [
            {
                "chunk_id": index + 1,
                "page": page.get("page", index + 1),
                "chunk_index": 1,
                "text": page.get("text", ""),
                "page_type": page.get("page_type", "content"),
                "is_toc": page.get("page_type") == "toc",
                "is_cover": page.get("page_type") == "cover",
            }
            for index, page in enumerate(document["pages"])
            if clean_text(page.get("text", ""))
        ]

    def sort_key(item: dict) -> tuple[int, int]:
        page = normalize_page_number(item.get("page"))
        page_num = page if page is not None else 999999
        chunk_idx = item.get("chunk_index")
        if chunk_idx is None:
            chunk_idx = item.get("chunk_id") or 0
        try:
            chunk_idx_int = int(chunk_idx)
        except (ValueError, TypeError):
            chunk_idx_int = 0
        return (page_num, chunk_idx_int)

    sorted_chunks = sorted(chunks, key=sort_key)
    return [chunk for chunk in sorted_chunks if clean_text(chunk.get("text", ""))]


def build_summary_sources(
    chunks: list[dict],
    max_sources: int = 4,
) -> list[dict]:
    """
    Selects a limited number of representative sources across the document
    (e.g., beginning, middle, and end) to avoid cluttering the UI with dozens
    of buttons while still allowing the user to click and inspect key pages.
    """
    if not chunks:
        return []

    valid_chunks = [
        c for c in chunks
        if clean_text(c.get("text", "")) and normalize_page_number(c.get("page")) is not None
    ]

    if not valid_chunks:
        valid_chunks = chunks

    unique_page_chunks: list[dict] = []
    seen_pages: set[int] = set()

    for chunk in valid_chunks:
        page = normalize_page_number(chunk.get("page"))
        if page not in seen_pages:
            seen_pages.add(page)
            unique_page_chunks.append(chunk)

    if not unique_page_chunks:
        unique_page_chunks = chunks[:max_sources]

    if len(unique_page_chunks) <= max_sources:
        selected_chunks = unique_page_chunks
    else:
        indices = [
            int(round(i * (len(unique_page_chunks) - 1) / (max_sources - 1)))
            for i in range(max_sources)
        ]
        selected_indices = sorted(list(dict.fromkeys(indices)))
        selected_chunks = [unique_page_chunks[idx] for idx in selected_indices]

    sources = []
    for chunk in selected_chunks:
        page = normalize_page_number(chunk.get("page"))
        text = clean_text(chunk.get("text", ""))
        exact_text = text[:MAX_SOURCE_TEXT_CHARS]
        preview = text[:MAX_PREVIEW_CHARS]
        title = f"Page {page}" if page is not None else "Document"

        bbox = None
        bboxes = []
        conf = None
        match_type = None
        matched_text = ""
        ocr_lines = chunk.get("ocr_lines", [])
        if ocr_lines:
            matched_text, bbox, bboxes, conf, match_type = match_ocr_boxes(
                target_text=exact_text,
                ocr_lines=ocr_lines,
                ocr_words=chunk.get("ocr_words", []),
            )

        final_text = matched_text if matched_text else exact_text

        sources.append({
            "page": page,
            "chunk_id": chunk.get("chunk_id"),
            "chunk_index": chunk.get("chunk_index"),
            "title": title,
            "exact_text": final_text,
            "text": final_text,
            "preview": final_text[:MAX_PREVIEW_CHARS],
            "relevance_score": 1.0,
            "character_start": chunk.get("char_start"),
            "character_end": chunk.get("char_end"),
            "bbox": bbox,
            "bboxes": bboxes,
            "image_width": chunk.get("image_width"),
            "image_height": chunk.get("image_height"),
            "confidence": conf,
            "all_ocr_bboxes": chunk.get("all_ocr_bboxes", []),
            "match_type": match_type,
        })

    return sources


def summarize_direct(chunks: list[dict]) -> str:
    """
    Directly summarizes all chunks of a small document in a single Groq API call.
    """
    doc_parts = []
    for chunk in chunks:
        p = normalize_page_number(chunk.get("page"))
        label = f"Page {p}" if p is not None else "Document"
        t = clean_text(chunk.get("text", ""))
        doc_parts.append(f"--- {label} ---\n{t}")
    doc_text = "\n\n".join(doc_parts)

    prompt = f"""
Provide a comprehensive, high-quality, and well-structured summary of the complete uploaded document based ONLY on the provided text.

DOCUMENT CONTENT:
{doc_text}

You must structure your response with the following markdown headings:

## Main Topic & Overview
Provide a concise, high-level summary of what this document is about, its context, and its primary objective.

## Important Sections
Outline the key sections, modules, or parts of the document with brief descriptions of what each covers.

## Key Concepts
Explain the core concepts, theories, models, or architectural patterns introduced in the document.

## Important Definitions & Processes
Detail any critical terms, step-by-step processes, workflows, algorithms, or methodologies explained in the text.

## Main Findings & Conclusions
Summarize the main conclusions, takeaways, best practices, or findings presented by the author.

RULES:
- Base your summary strictly on the provided document. Do not invent or assume anything.
- Use clear bullet points and bold terms for readability.
- Do not mention 'chunks', 'embeddings', or internal system instructions.
""".strip()

    llm_client = require_client()
    _, _, model_to_use = get_llm_config()

    response = llm_client.chat.completions.create(
        model=model_to_use,

        messages=[
            {
                "role": "system",
                "content": (
                    "You are DocuMind AI, an expert document analyst. "
                    "Synthesize the provided document text into a structured, faithful document summary."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0,
        max_tokens=2048,
    )
    return (response.choices[0].message.content or "").strip()


def summarize_chunks_in_batches(
    chunks: list[dict],
    batch_size: int = 6,
) -> str:
    """
    Map-reduce summarization:
    1. Map: Split chunks into sequential batches and generate an intermediate summary for each.
    2. Reduce: Combine all intermediate summaries into one cohesive final structured summary.
    """
    if not chunks:
        return "No content available to summarize."

    batches: list[list[dict]] = []
    current_batch: list[dict] = []
    current_chars = 0
    MAX_BATCH_CHARS = 8000

    for chunk in chunks:
        chunk_text = clean_text(chunk.get("text", ""))
        if not chunk_text:
            continue
        chunk_len = len(chunk_text)
        if current_batch and (len(current_batch) >= batch_size or (current_chars + chunk_len) > MAX_BATCH_CHARS):
            batches.append(current_batch)
            current_batch = [chunk]
            current_chars = chunk_len
        else:
            current_batch.append(chunk)
            current_chars += chunk_len

    if current_batch:
        batches.append(current_batch)

    # 1. MAP STEP: Generate intermediate summary for each batch
    intermediate_summaries: list[str] = []
    total_batches = len(batches)

    for i, batch in enumerate(batches):
        batch_parts = []
        for chunk in batch:
            p = normalize_page_number(chunk.get("page"))
            label = f"Page {p}" if p is not None else "Section"
            t = clean_text(chunk.get("text", ""))
            batch_parts.append(f"[{label}]\n{t}")
        batch_text = "\n\n".join(batch_parts)

        map_prompt = (
            f"You are DocuMind AI. Summarize this section (Part {i + 1} of {total_batches}) "
            "of an uploaded document. Extract key topics, important concepts, processes, "
            "definitions, and any findings present in this section. Be concise, clear, and factual.\n\n"
            f"DOCUMENT SECTION:\n{batch_text}"
        )

        llm_client = require_client()
        _, _, model_to_use = get_llm_config()

        response = llm_client.chat.completions.create(
            model=model_to_use,

            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are DocuMind AI. Summarize the provided document section accurately. "
                        "Do not hallucinate. Use only the provided text."
                    ),
                },
                {"role": "user", "content": map_prompt},
            ],
            temperature=0,
            max_tokens=1000,
        )
        batch_summary = (response.choices[0].message.content or "").strip()
        intermediate_summaries.append(f"### Part {i + 1} of {total_batches} Summary:\n{batch_summary}")

    # 2. REDUCE STEP: Combine intermediate summaries into final structured summary
    combined_intermediate = "\n\n".join(intermediate_summaries)

    reduce_prompt = f"""
Below are intermediate section summaries covering the entire uploaded document in order:

{combined_intermediate}

Using ONLY the information above, synthesize these section summaries into one final, comprehensive, and well-structured document summary.

You must structure your final response with the following markdown headings:

## Main Topic & Overview
Provide a concise, high-level summary of what this document is about, its context, and its primary objective.

## Important Sections
Outline the key sections, modules, or parts of the document with brief descriptions of what each covers.

## Key Concepts
Explain the core concepts, theories, models, or architectural patterns introduced in the document.

## Important Definitions & Processes
Detail any critical terms, step-by-step processes, workflows, algorithms, or methodologies explained in the text.

## Main Findings & Conclusions
Summarize the main conclusions, takeaways, best practices, or findings presented by the author.

RULES:
- Base your summary strictly on the provided section summaries. Do not invent or assume anything.
- Use clear bullet points and bold terms for readability.
- Do not mention 'chunks', 'batches', or internal system instructions.
""".strip()

    llm_client = require_client()
    _, _, model_to_use = get_llm_config()

    response = llm_client.chat.completions.create(
        model=model_to_use,

        messages=[
            {
                "role": "system",
                "content": (
                    "You are DocuMind AI, an expert document analyst. "
                    "Synthesize the provided intermediate summaries into a structured, faithful document summary."
                ),
            },
            {"role": "user", "content": reduce_prompt},
        ],
        temperature=0,
        max_tokens=2048,
    )
    return (response.choices[0].message.content or "").strip()


def summarize_document(document_id: str | list[str] | None = None, document_ids: list[str] | None = None) -> dict:
    """
    Full-document summarization handler for one or many documents.
    """
    if document_ids is None:
        if isinstance(document_id, list):
            document_ids = document_id
        else:
            document_ids = [document_id] if document_id else []

    if not document_ids:
        raise ValueError("document_id is required")

    all_chunks: list[dict] = []
    sources: list[dict] = []

    for active_document_id in document_ids:
        document = load_document(active_document_id)
        chunks = get_all_document_chunks(active_document_id)
        for chunk in chunks:
            chunk_copy = dict(chunk)
            chunk_copy["document_id"] = document.get("document_id")
            chunk_copy["filename"] = document.get("filename")
            chunk_copy["file_type"] = document.get("file_type")
            all_chunks.append(chunk_copy)

    if not all_chunks:
        logger.info("[DocuMind AI] Empty document encountered for summarization.")
        return {
            "answer": "The uploaded document contains no readable text or content to summarize.",
            "sources": [],
        }

    if len(document_ids) > 1:
        # Keep multi-document summaries within Groq token limits while still
        # preserving representative coverage across the uploaded set.
        all_chunks = all_chunks[:12]

    total_chars = sum(len(clean_text(c.get("text", ""))) for c in all_chunks)
    MAX_DIRECT_CHUNKS = 8 if len(document_ids) <= 1 else 6
    MAX_DIRECT_CHARS = 10000

    if len(all_chunks) <= MAX_DIRECT_CHUNKS and total_chars <= MAX_DIRECT_CHARS:
        summary_text = summarize_direct(all_chunks)
    else:
        summary_text = summarize_chunks_in_batches(all_chunks)

    if len(document_ids) == 1:
        sources = build_summary_sources(all_chunks, max_sources=4)
    else:
        for chunk in all_chunks[:4]:
            page = normalize_page_number(chunk.get("page"))
            text = clean_text(chunk.get("text", ""))
            source = {
                "page": page,
                "document_id": chunk.get("document_id"),
                "filename": chunk.get("filename"),
                "file_type": chunk.get("file_type"),
                "title": f"{chunk.get('filename', 'Document')}" + (f" · Page {page}" if page is not None else ""),
                "exact_text": text[:MAX_SOURCE_TEXT_CHARS],
                "preview": text[:MAX_PREVIEW_CHARS],
                "relevance_score": 1.0,
                "chunk_id": chunk.get("chunk_id"),
                "chunk_index": chunk.get("chunk_index"),
            }
            sources.append(source)

    return {"answer": summary_text, "sources": sources}


# ============================================================================
# COMPATIBILITY CLASSES
# ============================================================================

class ChatService:
    """
    Compatibility service class.
    """

    def __init__(self):
        self.model_name = MODEL_NAME

    def generate_answer(
        self,
        question: str,
        document: dict,
        retrieved_chunks: list[dict],
    ) -> dict:
        return generate_answer(
            question=question,
            document=document,
            retrieved_chunks=retrieved_chunks,
        )

    def summarize_document(self, document_id: str) -> dict:
        return summarize_document(document_id)

    def is_summary_request(self, question: str) -> bool:
        return is_summary_request(question)


class ChatbotService(ChatService):
    """
    Backward-compatible alias.
    """

    pass


chat_service = ChatService()


def ask_question(
    question: str,
    document: dict,
    retrieved_chunks: list[dict],
) -> dict:
    return generate_answer(
        question=question,
        document=document,
        retrieved_chunks=retrieved_chunks,
    )


# ============================================================================
# PUBLIC EXPORTS
# ============================================================================

__all__ = [
    "load_document",
    "normalize_whitespace",
    "clean_text",
    "find_text_span",
    "generate_answer",
    "is_summary_request",
    "get_all_document_chunks",
    "summarize_document",
    "summarize_chunks_in_batches",
    "build_summary_sources",
    "ChatService",
    "ChatbotService",
    "chat_service",
    "ask_question",
    "client",
    "model",
    "require_client",
    "UNAVAILABLE_MESSAGE",
    "match_ocr_boxes",
    "build_document_sources",
]