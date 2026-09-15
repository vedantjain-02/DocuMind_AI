import json
import logging
import os
import re
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

DOCUMENT_DIR = BASE_DIR / "data" / "documents"

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

MODEL_NAME = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-120b",
)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"

UNAVAILABLE_MESSAGE = (
    "This information is not available in the uploaded document."
)

MAX_CONTEXT_CHARS = 14000
MAX_SOURCE_TEXT_CHARS = 1800
MAX_PREVIEW_CHARS = 300
MAX_SOURCE_PAGES = 3


client = None
if GROQ_API_KEY:
    client = OpenAI(
        api_key=GROQ_API_KEY,
        base_url=GROQ_BASE_URL,
    )


def require_client() -> Any:
    """Return the configured Groq client or raise a clear error."""
    if client is None:
        raise RuntimeError(
            "GROQ_API_KEY is missing. Please add it to backend/.env"
        )
    return client


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

    source_text = source_text[
        :MAX_SOURCE_TEXT_CHARS
    ]

    # Find the complete paragraph/chunk in page text.
    span = find_text_span(
        page_text=page_text,
        quote=source_text,
    )

    character_start = (
        span[0]
        if span
        else best_chunk.get("char_start")
    )

    character_end = (
        span[1]
        if span
        else best_chunk.get("char_end")
    )

    score = (
        best_chunk.get("relevance_score")
        or best_chunk.get("_score")
        or 0.0
    )

    try:
        score = round(float(score), 4)
    except (TypeError, ValueError):
        score = 0.0

    title = (
        f"Page {page}"
        if page is not None
        else "Document"
    )

    return {
        "page": page,
        "chunk_id": best_chunk.get("chunk_id"),
        "chunk_index": best_chunk.get("chunk_index"),
        "title": title,
        "exact_text": source_text,
        "preview": source_text[:MAX_PREVIEW_CHARS],
        "relevance_score": score,
        "character_start": character_start,
        "character_end": character_end,
    }


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
8. Return supporting quotes copied exactly from the document excerpt.
9. Each quote must belong to one page only.
10. Quotes should preferably contain the complete relevant paragraph.
11. If no exact supporting quote exists, return an empty quotes list.

Return ONLY valid JSON in this format:

{{
  "answer": "answer text",
  "quotes": [
    {{
      "page": 1,
      "text": "exact supporting paragraph from page 1"
    }}
  ]
}}
""".strip()


# ============================================================================
# ANSWER GENERATION
# ============================================================================

def generate_answer(
    question: str,
    document: dict,
    retrieved_chunks: list[dict],
) -> dict:
    """
    Generates grounded answer and source information.
    """
    pages = document.get("pages", [])

    if not retrieved_chunks:
        return {
            "answer": UNAVAILABLE_MESSAGE,
            "sources": [],
        }

    context, page_lookup = build_page_context(
        retrieved_chunks=retrieved_chunks,
        pages=pages,
    )

    if not context.strip():
        return {
            "answer": UNAVAILABLE_MESSAGE,
            "sources": [],
        }

    prompt = build_prompt(
        question=question,
        context=context,
    )

    groq_client = require_client()

    response = groq_client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are DocuMind AI. "
                    "Answer only from the supplied document. "
                    "Return valid JSON only."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        response_format={
            "type": "json_object"
        },
        temperature=0,
        max_tokens=1400,
    )

    content = (
        response.choices[0].message.content
        or ""
    )

    answer, raw_quotes = extract_json_answer(
        content
    )

    # Retry once if model response is invalid.
    if not answer:
        retry_response = groq_client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Return only valid JSON with keys "
                        "answer and quotes."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            response_format={
                "type": "json_object"
            },
            temperature=0,
            max_tokens=1400,
        )

        retry_content = (
            retry_response.choices[0].message.content
            or ""
        )

        answer, raw_quotes = extract_json_answer(
            retry_content
        )

    answer = answer.strip()

    if not answer:
        answer = UNAVAILABLE_MESSAGE

    if answer == UNAVAILABLE_MESSAGE:
        return {
            "answer": UNAVAILABLE_MESSAGE,
            "sources": [],
        }

    # ========================================================================
    # VERIFY MODEL QUOTES
    # ========================================================================

    verified_quotes: list[dict] = []
    used_pages: list[int] = []

    for quote in raw_quotes:
        if not isinstance(quote, dict):
            continue

        quote_page = normalize_page_number(
            quote.get("page")
        )

        quote_text = clean_text(
            quote.get("text", "")
        )

        if quote_page is None:
            continue

        if not quote_text:
            continue

        actual_page_text = page_lookup.get(
            quote_page,
            "",
        )

        if not quote_is_in_page(
            page_text=actual_page_text,
            quote=quote_text,
        ):
            continue

        verified_quotes.append(
            {
                "page": quote_page,
                "text": quote_text,
            }
        )

        if quote_page not in used_pages:
            used_pages.append(quote_page)

    # ========================================================================
    # FALLBACK TO RETRIEVED PAGES
    # ========================================================================

    if not used_pages:
        for chunk in retrieved_chunks:
            page = normalize_page_number(
                chunk.get("page")
            )

            if page is None:
                continue

            if page not in used_pages:
                used_pages.append(page)

    # ========================================================================
    # BUILD FINAL SOURCES
    # ========================================================================

    sources: list[dict] = []

    for page in used_pages[:MAX_SOURCE_PAGES]:
        source = source_from_chunk(
            question=question,
            retrieved_chunks=retrieved_chunks,
            page_lookup=page_lookup,
            page=page,
        )

        if source is None:
            continue

        page_quotes = [
            quote["text"]
            for quote in verified_quotes
            if quote["page"] == page
        ]

        # Prefer the verified complete paragraph from model.
        if page_quotes:
            exact_text = page_quotes[0]

            source["exact_text"] = exact_text
            source["preview"] = (
                exact_text[:MAX_PREVIEW_CHARS]
            )

            exact_span = find_text_span(
                page_text=page_lookup.get(
                    page,
                    "",
                ),
                quote=exact_text,
            )

            source["character_start"] = (
                exact_span[0]
                if exact_span
                else source.get("character_start")
            )

            source["character_end"] = (
                exact_span[1]
                if exact_span
                else source.get("character_end")
            )

        sources.append(source)

    return {
        "answer": answer,
        "sources": sources,
    }


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
    r"(document|pdf|file|paper|text|book|upload)\s+about\b",

    r"\bwhat\s+is\s+it\s+about\b",

    r"\bwhat\s+is\s+(this|the)\s+about\b",

    # Main topic
    r"\b(main\s+topic|main\s+theme|main\s+subject|"
    r"core\s+topic|main\s+idea|key\s+theme)\b",

    # Explain complete document
    r"\bexplain\s+(the\s+)?"
    r"(whole|entire|complete|all\s+of\s+the|uploaded)"
    r"\s*(document|pdf|file|paper|text)?\b",

    r"\bexplain\s+(this|the)\s+"
    r"(document|pdf|file|paper)\b",

    # Give me an overview
    r"\bgive\s+(me\s+)?(an?\s+)?overview\b",

    # Give me the summary
    r"\bgive\s+(me\s+)?(the\s+)?summary\b",

    # Document summary
    r"\b(document|pdf|file|paper)\s+summary\b",

    # Outline and breakdown
    r"\b(outline|breakdown)\s+of\s+"
    r"(this|the)\s+(document|pdf|file|paper)\b",

    # Walkthrough
    r"\b(walk\s+me\s+through|walkthrough\s+of)\s+"
    r"(this|the)\s+(document|pdf|file|paper)\b",
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

        sources.append({
            "page": page,
            "chunk_id": chunk.get("chunk_id"),
            "chunk_index": chunk.get("chunk_index"),
            "title": title,
            "exact_text": exact_text,
            "text": exact_text,
            "preview": preview,
            "relevance_score": 1.0,
            "character_start": chunk.get("char_start"),
            "character_end": chunk.get("char_end"),
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

    groq_client = require_client()

    response = groq_client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are DocuMind AI, an expert document analyst. "
                    "Analyze the provided document and produce a clear, factual, and comprehensive summary. "
                    "Use ONLY information present in the document. Do not hallucinate."
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

        groq_client = require_client()

        response = groq_client.chat.completions.create(
            model=MODEL_NAME,
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

    groq_client = require_client()

    response = groq_client.chat.completions.create(
        model=MODEL_NAME,
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


def summarize_document(document_id: str) -> dict:
    """
    Full-document summarization handler:
    1. Loads all chunks in order for document_id.
    2. Validates document content (handles empty documents safely).
    3. Chooses between direct summary mode (small documents) and map-reduce summary mode (large documents).
    4. Generates structured summary and builds representative sources.
    """
    if not document_id or not str(document_id).strip():
        raise ValueError("document_id is required")

    chunks = get_all_document_chunks(document_id)

    if not chunks:
        logger.info("[DocuMind AI] Empty document encountered for summarization.")
        print("[DocuMind AI] Empty document encountered for summarization.", flush=True)
        return {
            "answer": "The uploaded document contains no readable text or content to summarize.",
            "sources": [],
        }

    total_chars = sum(len(clean_text(c.get("text", ""))) for c in chunks)
    MAX_DIRECT_CHUNKS = 8
    MAX_DIRECT_CHARS = 10000

    if len(chunks) <= MAX_DIRECT_CHUNKS and total_chars <= MAX_DIRECT_CHARS:
        logger.info("[DocuMind AI] Request mode: full-document summary mode")
        print("[DocuMind AI] Request mode: full-document summary mode", flush=True)
        summary_text = summarize_direct(chunks)
    else:
        logger.info("[DocuMind AI] Request mode: map-reduce summary mode")
        print("[DocuMind AI] Request mode: map-reduce summary mode", flush=True)
        summary_text = summarize_chunks_in_batches(chunks)

    sources = build_summary_sources(chunks, max_sources=4)

    return {
        "answer": summary_text,
        "sources": sources,
    }


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
    "UNAVAILABLE_MESSAGE",
]