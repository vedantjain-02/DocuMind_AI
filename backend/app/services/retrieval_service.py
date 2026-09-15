import math
import re
from collections import Counter
from typing import Optional

import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

# ---------------------------------------------------------------------------
# Configuration (tunable)
# ---------------------------------------------------------------------------

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

SEMANTIC_WEIGHT = 0.45
LEXICAL_WEIGHT = 0.15
OVERLAP_WEIGHT = 0.40

MAX_CANDIDATES = 24      # recall list handed to the re-rank stage
SEMANTIC_FLOOR = 0.33    # below this the page does not answer the question
PRE_FLOOR = 0.0          # loose floor applied to the combined score
RELATIVE_GAP_FLOOR = 0.60
NEXT_PAGE_SEMANTIC_FLOOR = 0.30

MAX_RESULTS = 4
MAX_CHUNKS_PER_PAGE = 3
INFORMATIVE_IDF_THRESHOLD = 1.55

STOPWORDS = {
    "the", "and", "are", "was", "were", "this", "that", "these", "those",
    "with", "from", "into", "have", "has", "had", "for", "how", "why",
    "when", "where", "does", "did", "their", "there", "they", "them",
    "then", "than", "also", "only", "using", "used", "use", "what",
    "which", "about", "will", "would", "should", "could", "can", "its",
    "it's", "whose", "your", "you", "you're", "not", "but", "all",
    "each", "some", "any", "our", "who", "whom", "is", "a", "an", "to",
    "of", "in", "on", "at", "by", "be", "been", "being", "do", "does",
    "as", "or", "if", "because", "while", "via", "such", "etc", "eg",
    "please", "tell", "explain", "describe", "about", "does", "the",
    "here", "there",
    # Generic tokens that should never act as heading discriminators
    "ai", "llm", "rag", "api", "pdf", "mas", "url", "sql",
}

_MODEL: Optional[SentenceTransformer] = None
_EMBED_CACHE: dict[str, dict[int, np.ndarray]] = {}

# Re-rank weights for the final relevance number
RERANK_SEMANTIC_WEIGHT = 0.65
RERANK_OVERLAP_WEIGHT = 0.35


# ---------------------------------------------------------------------------
# Text utilities
# ---------------------------------------------------------------------------

def tokenize(text: str) -> list[str]:
    """Lowercased alphanumeric tokens, stopwords removed, digits kept."""
    words = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return [
        word
        for word in words
        if word not in STOPWORDS and len(word) >= 2
    ]


def _compute_idf(tokens_per_document: list[list[str]]) -> dict[str, float]:
    document_count = max(len(tokens_per_document), 1)
    frequencies: Counter = Counter()

    for tokens in tokens_per_document:
        for token in set(tokens):
            frequencies[token] += 1

    return {
        token: math.log(1.0 + document_count / (1.0 + count))
        for token, count in frequencies.items()
    }


def _informative_query_tokens(
    query_tokens: list[str],
    idf: dict[str, float],
) -> list[str]:
    """Keeps only tokens that distinguish one chunk from another, so common
    words like 'agent', 'system', 'AI' cannot dominate the match score."""
    if len(query_tokens) <= 2:
        return query_tokens

    informative = [token for token in query_tokens if idf.get(token, 0.0) >= INFORMATIVE_IDF_THRESHOLD]

    if not informative:
        ranked = sorted(
            query_tokens,
            key=lambda token: idf.get(token, 0.0),
            reverse=True,
        )
        informative = ranked[: max(1, len(ranked) // 2 + 1)]

    return informative


def _tf_idf_overlap_score(
    chunk_tokens: list[str],
    query_tokens: list[str],
    idf: dict[str, float],
) -> float:
    informative = _informative_query_tokens(query_tokens, idf)

    if not informative:
        return 0.0

    chunk_counter = Counter(chunk_tokens)

    query_weight = sum(idf.get(token, 1.0) for token in set(informative))

    if query_weight <= 0:
        return 0.0

    overlap_weight = 0.0

    for token in set(informative):
        count = chunk_counter.get(token, 0)
        if count > 0:
            overlap_weight += idf.get(token, 1.0) * math.log(1.0 + count)

    return min(1.0, overlap_weight / query_weight)


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------

def _embedder() -> SentenceTransformer:
    global _MODEL
    if _MODEL is None:
        _MODEL = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _MODEL


def _get_chunk_embeddings(
    chunks: list[dict],
    document_id: str,
) -> np.ndarray:
    cached = _EMBED_CACHE.get(document_id)

    if cached is not None and len(cached) == len(chunks):
        expected_ids = [chunk["chunk_id"] for chunk in chunks]
        if all(cid in cached for cid in expected_ids):
            return np.vstack([cached[cid] for cid in expected_ids])

    model = _embedder()
    texts = [chunk.get("text", "") for chunk in chunks]
    vectors = model.encode(
        texts,
        normalize_embeddings=True,
        batch_size=32,
        show_progress_bar=False,
    )

    _EMBED_CACHE[document_id] = {
        chunk["chunk_id"]: vectors[index]
        for index, chunk in enumerate(chunks)
    }

    return vectors


def _compute_semantic_scores(
    chunks: list[dict],
    question: str,
    document_id: str,
) -> list[float]:
    if not chunks:
        return []

    vectors = _get_chunk_embeddings(chunks, document_id)
    model = _embedder()
    question_vector = model.encode(
        question,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    similarities = vectors @ question_vector
    return [max(0.0, float(value)) for value in similarities]


def _compute_lexical_scores(
    chunks: list[dict],
    question: str,
) -> list[float]:
    if not chunks:
        return []

    chunk_token_lists = [tokenize(chunk.get("text", "")) for chunk in chunks]
    question_tokens = tokenize(question)

    if not question_tokens:
        return [0.0] * len(chunks)

    bm25 = BM25Okapi(chunk_token_lists)
    raw_scores = np.asarray(bm25.get_scores(question_tokens), dtype=float)
    maximum = float(raw_scores.max()) if len(raw_scores) else 0.0

    if maximum <= 1e-9:
        return [0.0] * len(chunks)

    return (raw_scores / maximum).tolist()


# ---------------------------------------------------------------------------
# Stage A: hybrid candidate scoring (recall + re-rank features)
# ---------------------------------------------------------------------------

def _score_all_chunks(
    chunks: list[dict],
    question: str,
    document_id: str,
) -> list[dict]:
    if not chunks or not question.strip():
        return []

    semantic_scores = _compute_semantic_scores(chunks, question, document_id)
    lexical_scores = _compute_lexical_scores(chunks, question)

    tokens_per_chunk = [tokenize(chunk.get("text", "")) for chunk in chunks]
    idf = _compute_idf(tokens_per_chunk)
    query_tokens = tokenize(question)

    scored: list[dict] = []

    for index, chunk in enumerate(chunks):
        semantic = semantic_scores[index]
        lexical = lexical_scores[index]
        overlap = _tf_idf_overlap_score(tokens_per_chunk[index], query_tokens, idf)

        combined = (
            SEMANTIC_WEIGHT * semantic
            + LEXICAL_WEIGHT * lexical
            + OVERLAP_WEIGHT * overlap
        )

        if chunk.get("is_toc") or chunk.get("is_cover"):
            combined *= 0.20

        # Store the informative query tokens on every chunk for the locator
        chunk_with_scores = {
            **chunk,
            "semantic_score": round(semantic, 4),
            "lexical_score": round(lexical, 4),
            "overlap_score": round(overlap, 4),
            "relevance_score": round(combined, 4),
            "_informative_tokens": _informative_query_tokens(query_tokens, idf),
        }
        scored.append(chunk_with_scores)

    scored.sort(key=lambda item: item["relevance_score"], reverse=True)
    return scored


# ---------------------------------------------------------------------------
# Stage B: topic / section heading locator
# ---------------------------------------------------------------------------

_SECTION_QUESTION = re.compile(
    r"(?:section|chapter|part)\s+(\d+(?:\.\d+)*)",
    re.IGNORECASE,
)

_NUMBERED_HEADING = re.compile(r"^\s*\d+(\.\d+)*[.)]\s+[A-Z0-9]")


def _is_numbered_heading(line: str) -> bool:
    return bool(_NUMBERED_HEADING.match(line)) and (
        2 <= len(line.split()) <= 10
    )


def _line_after_number(line: str) -> str:
    return re.sub(r"^\s*\d+(\.\d+)*[.)]?\s*", "", line).strip()


def _find_heading_chunk(
    chunks: list[dict],
    informative_tokens: list[str],
) -> Optional[dict]:
    """Finds the best chunk whose numbered heading line mentions an
    informative query token (e.g. '6. Memory, State, and Knowledge')."""
    best_candidate = None
    best_score = -1.0

    for chunk in chunks:
        chunk_text = chunk.get("text", "")

        for line in chunk_text.splitlines():
            stripped = line.strip()

            if not _is_numbered_heading(stripped):
                continue

            lowered = stripped.lower()
            hits = [token for token in informative_tokens if token in lowered]

            if not hits:
                continue

            # Prefer a content page over a TOC / cover page
            page_penalty = 1.0
            if chunk.get("is_toc") or chunk.get("is_cover"):
                page_penalty = 0.2

            # Prefer headings that match more informative query tokens
            hit_bonus = 1.0 + 0.5 * (len(hits) - 1)

            score = chunk.get("relevance_score", 0.0) * page_penalty * hit_bonus

            if score > best_score:
                best_score = score
                best_candidate = chunk

    return best_candidate


def _gather_heading_context(
    all_chunks: list[dict],
    heading_chunk: dict,
    scored_by_id: dict[int, dict],
    max_per_page: int = MAX_CHUNKS_PER_PAGE,
) -> list[dict]:
    """Collects the heading chunk plus the chunks that follow it on the same
    page so the section's actual content is included. If the heading is the
    last chunk of its page, the heading content continues on the next page."""
    page_number = heading_chunk.get("page")

    if page_number is None:
        return [heading_chunk]

    page_chunks = sorted(
        [
            scored_by_id[chunk["chunk_id"]]
            for chunk in all_chunks
            if chunk.get("page") == page_number
        ],
        key=lambda chunk: chunk.get("chunk_index", 0),
    )

    if not page_chunks:
        return [heading_chunk]

    heading_index = next(
        (
            index
            for index, chunk in enumerate(page_chunks)
            if chunk["chunk_id"] == heading_chunk["chunk_id"]
        ),
        -1,
    )

    selected = []
    start = heading_index if heading_index >= 0 else 0
    tail = page_chunks[start: start + max_per_page]

    for chunk in tail:
        if chunk["chunk_id"] == heading_chunk["chunk_id"] or (
            chunk.get("relevance_score", 0.0) > 0.0
        ):
            selected.append(chunk)

    # The heading ends this page: content continues on the next page
    if page_chunks and heading_index == len(page_chunks) - 1:
        next_page_chunks = sorted(
            [
                scored_by_id[chunk["chunk_id"]]
                for chunk in all_chunks
                if chunk.get("page") == page_number + 1
            ],
            key=lambda chunk: chunk.get("chunk_index", 0),
        )
        if next_page_chunks:
            best_next = next_page_chunks[0]
            if best_next.get("semantic_score", 0.0) >= NEXT_PAGE_SEMANTIC_FLOOR:
                selected.append(best_next)

    return selected


# ---------------------------------------------------------------------------
# Stage C: selection
# ---------------------------------------------------------------------------

def _best_rerank(chunk: dict) -> float:
    """Query-specific re-rank number used for the final ordering."""
    return (
        RERANK_SEMANTIC_WEIGHT * chunk.get("semantic_score", 0.0)
        + RERANK_OVERLAP_WEIGHT * chunk.get("overlap_score", 0.0)
    )


def _select_pages(
    scored_chunks: list[dict],
    max_results: int,
) -> list[dict]:
    """Selects the strongest page(s) from the candidate chunks."""
    if not scored_chunks:
        return []

    by_page: dict = {}

    for chunk in scored_chunks:
        page_key = chunk.get("page")

        if page_key is None:
            page_key = ("unnumbered", chunk["chunk_id"])

        if page_key not in by_page or _best_rerank(chunk) > _best_rerank(by_page[page_key]):
            by_page[page_key] = chunk

    pages = sorted(by_page.values(), key=_best_rerank, reverse=True)

    if not pages:
        return []

    best_score = _best_rerank(pages[0])

    # If a second page is almost as strong as the best page, the answer may
    # genuinely span both pages.
    selected = [pages[0]]
    if len(pages) > 1 and best_score > 0:
        second = pages[1]
        if second.get("semantic_score", 0.0) >= SEMANTIC_FLOOR:
            if _best_rerank(second) >= best_score * 0.92:
                selected.append(second)

    selected.sort(key=_best_rerank, reverse=True)

    result: list[dict] = []

    for page_chosen in selected:
        page_number = page_chosen.get("page")
        page_chunks = [
            chunk
            for chunk in scored_chunks
            if chunk.get("page") == page_number
        ]
        page_chunks.sort(
            key=lambda chunk: chunk.get("chunk_index", 0)
        )
        page_chunks.sort(
            key=lambda chunk: chunk.get("relevance_score", 0.0),
            reverse=True,
        )

        if page_chunks and page_chunks[0]["chunk_id"] == page_chosen["chunk_id"]:
            pass

        result.append(page_chosen)

        # Optionally keep a second strong chunk from the same page so the
        # model can see surrounding context without adding new pages.
        for extra in page_chunks:
            if len(result) >= max_results:
                break
            if extra["chunk_id"] == page_chosen["chunk_id"]:
                continue
            if extra.get("relevance_score", 0.0) >= page_chosen.get("relevance_score", 0.0) * 0.6:
                result.append(extra)

    return result[:max_results]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def score_chunks(
    chunks: list[dict],
    question: str,
    document_id: str,
) -> list[dict]:
    """Exposes the hybrid candidate scores (recall features included)."""
    return _score_all_chunks(chunks, question, document_id)


def retrieve_relevant_chunks(
    document: dict,
    question: str,
    document_id: str,
    max_results: int = MAX_RESULTS,
) -> list[dict]:
    """Three-stage retrieval:

    1. hybrid recall (BM25 + embeddings + TF-IDF overlap)
    2. topic/section heading locator (number-based headings)
    3. page-level selection with a semantic relevance floor

    Returns the most relevant chunks for answer generation.
    """
    chunks = document.get("chunks", [])

    if not chunks or not question.strip():
        return []

    # --- Stage A: score every chunk ---------------------------------------
    all_scored = _score_all_chunks(chunks, question, document_id)
    scored_by_id = {chunk["chunk_id"]: chunk for chunk in all_scored}

    # Exclude TOC / cover pages when scanning section headings
    heading_scan_pool = [
        chunk
        for chunk in all_scored
        if not (chunk.get("is_toc") or chunk.get("is_cover"))
    ]

    if not heading_scan_pool:
        heading_scan_pool = all_scored

    # --- Section-number question ("what is the content of section 7?") -----
    number_match = _SECTION_QUESTION.search(question)

    if number_match:
        section_number = number_match.group(1)
        heading_chunk = None

        for chunk in heading_scan_pool:
            for line in chunk.get("text", "").splitlines():
                stripped = line.strip()
                if not _is_numbered_heading(stripped):
                    continue
                section_prefix = re.match(
                    r"^\s*" + re.escape(section_number) + r"[.)]\s+", stripped
                )
                if section_prefix:
                    heading_chunk = chunk
                    break
            if heading_chunk:
                break

        if heading_chunk:
            context = _gather_heading_context(
                chunks,
                heading_chunk,
                scored_by_id,
                MAX_CHUNKS_PER_PAGE,
            )
            for index, chunk in enumerate(context):
                chunk_relevance = max(0.05, 1.0 - index * 0.15)
                chunk["relevance_score"] = chunk_relevance
                chunk["semantic_score"] = chunk.get("semantic_score", 0.0)
            return context[:max_results]

    # --- Topic heading locator ----------------------------------------------
    if not number_match:
        informative_tokens: set = set()
        for chunk in all_scored[:MAX_CANDIDATES]:
            informative_tokens.update(chunk.get("_informative_tokens", []))

        informative_tokens = [token for token in informative_tokens if token]

        heading_chunk = _find_heading_chunk(
            heading_scan_pool,
            informative_tokens,
        )

        if heading_chunk:
            context = _gather_heading_context(
                chunks,
                heading_chunk,
                scored_by_id,
                MAX_CHUNKS_PER_PAGE,
            )
            # Re-rank the heading context by the query-specific score
            context.sort(
                key=lambda chunk: (
                    chunk.get("semantic_score", 0.0),
                    chunk.get("relevance_score", 0.0),
                ),
                reverse=True,
            )

            # Only accept the locator result if it is reasonably relevant
            if context[0].get("semantic_score", 0.0) >= SEMANTIC_FLOOR - 0.05:
                return context[:max_results]

    # --- Standard path: selection over the candidate list -------------------
    candidates = all_scored[:MAX_CANDIDATES]

    candidates = [
        chunk
        for chunk in candidates
        if chunk.get("semantic_score", 0.0) >= SEMANTIC_FLOOR
        and chunk.get("relevance_score", 0.0) >= PRE_FLOOR
    ]

    return _select_pages(candidates, max_results)


__all__ = [
    "tokenize",
    "score_chunks",
    "retrieve_relevant_chunks",
]