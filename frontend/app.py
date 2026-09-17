import base64
import hashlib
import html
import json
import logging
import re
from io import BytesIO
from typing import Any

import fitz
from PIL import Image
import requests
import streamlit as st
import streamlit.components.v1 as components


# ============================================================================
# CONFIGURATION
# ============================================================================

LOGGER = logging.getLogger("documind.frontend")

BACKEND_URL = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="DocuMind AI",
    page_icon="📘",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================================
# PROFESSIONAL DARK THEME (navy / indigo palette)
# ============================================================================

APP_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: "Inter", sans-serif;
}

.stApp {
    background:
        radial-gradient(circle at 88% -5%, rgba(99, 102, 241, 0.20), transparent 32%),
        radial-gradient(circle at -5% 100%, rgba(34, 211, 238, 0.10), transparent 28%),
        #080c1a;
    color: #e6eaf5;
}

[data-testid="stHeader"] {
    background: transparent;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0b1020 0%, #0d1328 100%);
    border-right: 1px solid #232c4d;
}

[data-testid="stSidebar"] > div:first-child {
    padding: 18px 14px;
}

[data-testid="stSidebar"] * {
    color: #dfe6f5;
}

.main-title {
    color: #f4f6ff;
    font-size: 40px;
    font-weight: 800;
    letter-spacing: -1.5px;
    margin: 4px 0 2px;
}

.subtitle {
    color: #8f9cc4;
    font-size: 13px;
    margin-bottom: 20px;
}

.brand-chip {
    width: 46px;
    height: 46px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 14px;
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    box-shadow: 0 10px 30px rgba(99, 102, 241, 0.35);
    font-size: 24px;
    margin-bottom: 6px;
}

.sidebar-brand {
    display: flex;
    align-items: center;
    gap: 11px;
    color: #ffffff;
    font-size: 18px;
    font-weight: 800;
    margin-bottom: 4px;
}

.sidebar-brand-icon {
    width: 34px;
    height: 34px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 10px;
    background: linear-gradient(135deg, #6366f1, #06b6d4);
    box-shadow: 0 6px 18px rgba(99, 102, 241, 0.35);
    font-size: 17px;
}

.sidebar-caption {
    color: #7e8bb0;
    font-size: 11px;
    line-height: 1.7;
    margin-bottom: 14px;
}

.sidebar-section {
    color: #6f7da8;
    text-transform: uppercase;
    letter-spacing: 1.4px;
    font-size: 10px;
    font-weight: 800;
    margin: 20px 0 9px;
}

.panel-title {
    color: #f1f3ff;
    font-size: 19px;
    font-weight: 800;
}

.panel-sub {
    color: #7e8bb0;
    font-size: 12px;
    margin: 3px 0 12px;
}

.empty-state {
    text-align: center;
    padding: 96px 18px;
    color: #8290b6;
}

.empty-icon {
    font-size: 42px;
    margin-bottom: 12px;
}

.empty-title {
    color: #dfe6f5;
    font-size: 17px;
    font-weight: 700;
    margin-bottom: 8px;
}

.empty-text {
    color: #8290b6;
    font-size: 12px;
    line-height: 1.9;
}

.source-label {
    color: #818cf8;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.8px;
    margin: 14px 0 7px;
    text-transform: uppercase;
}

.source-preview {
    color: #a2aed0;
    font-size: 11px;
    line-height: 1.7;
    padding: 9px 12px;
    border-left: 3px solid #6366f1;
    background: rgba(16, 23, 46, 0.85);
    border-radius: 0 9px 9px 0;
    margin-bottom: 10px;
}

.doc-card {
    background: #101730;
    border: 1px solid #263055;
    border-radius: 12px;
    padding: 11px 12px;
    margin-bottom: 9px;
}

.doc-card.active {
    border-color: #6366f1;
    box-shadow: 0 0 0 1px rgba(99, 102, 241, 0.25);
}

.doc-name {
    color: #dfe6f5;
    font-size: 12px;
    font-weight: 700;
    line-height: 1.6;
    word-break: break-word;
}

.doc-meta {
    color: #6f7da8;
    font-size: 11px;
    margin-top: 4px;
}

.status-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    color: #86efac;
    background: rgba(22, 101, 52, 0.20);
    border: 1px solid rgba(74, 222, 128, 0.25);
    border-radius: 999px;
    padding: 5px 9px;
    font-size: 11px;
    font-weight: 700;
}

.status-dot {
    width: 7px;
    height: 7px;
    background: #4ade80;
    border-radius: 50%;
    box-shadow: 0 0 10px rgba(74, 222, 128, 0.7);
}

.metric-card {
    background: #101730;
    border: 1px solid #263055;
    border-radius: 12px;
    padding: 10px 12px;
}

.metric-label {
    color: #6f7da8;
    font-size: 10px;
    margin-bottom: 4px;
}

.metric-value {
    color: #f1f3ff;
    font-size: 21px;
    font-weight: 800;
}

.stButton > button {
    background: #111a33;
    color: #dbe3f3;
    border: 1px solid #2a3557;
    border-radius: 10px;
    font-weight: 600;
    min-height: 38px;
    transition: background 0.15s ease, border-color 0.15s ease;
}

.stButton > button:hover {
    background: #1a2547;
    color: #ffffff;
    border-color: #818cf8;
}

.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    border: 1px solid transparent;
    color: #ffffff;
}

.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #4f46e5, #7c3aed);
}

[data-testid="stChatMessage"] {
    background: #10172e;
    border: 1px solid #242e52;
    border-radius: 14px;
    padding: 12px 14px;
}

[data-testid="stChatMessage"] p {
    font-size: 13px;
    line-height: 1.75;
}

[data-testid="stChatInput"] textarea {
    background: #0f1730;
    color: #eef2ff;
    border: 1px solid #2c3961;
    border-radius: 12px;
}

[data-testid="stChatInput"] textarea:focus {
    border-color: #6366f1;
    box-shadow: 0 0 0 1px #6366f1;
}

[data-testid="stFileUploader"] {
    background: #101730;
    border: 1px dashed #38446e;
    border-radius: 12px;
    padding: 6px;
}

[data-testid="stVerticalBlockBorderWrapper"] {
    background: rgba(10, 16, 33, 0.7);
    border-color: #222b4d !important;
    border-radius: 15px !important;
}

hr {
    border-color: #232c4d;
}
"""

st.markdown(
    f"""<style>{APP_CSS}</style>""",
    unsafe_allow_html=True,
)


# ============================================================================
# SESSION STATE
# ============================================================================

DEFAULT_STATE = {
    "document_id": None,
    "filename": None,
    "pdf_bytes": None,
    "image_bytes": None,
    "documents": [],
    "documents_needs_refresh": True,
    "processed_file_fingerprints": set(),
    "upload_statuses": [],
    "messages": [],
    "conversation_id": None,
    "conversation_title": "New chat",
    "conversations": [],
    "current_page": 1,
    "page_input": 1,
    "highlight_text": "",
    "active_source_key": None,
    "pending_page": None,
    "upload_key": 0,
    "total_pages": 0,
    "total_chunks": 0,
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================================
# GENERAL HELPERS
# ============================================================================

def safe_text(value: Any) -> str:
    return str(value or "").strip()


def escape_html(value: Any) -> str:
    return html.escape(str(value or ""))


def compute_file_fingerprint(uploaded_file) -> str:
    file_bytes = uploaded_file.getvalue()
    digest = hashlib.sha256(file_bytes).hexdigest()
    return f"{uploaded_file.name}:{uploaded_file.size}:{digest}"


def truncate_display(text: Any, limit: int = 32) -> str:
    value = " ".join(str(text or "").split())
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + "…"


def auto_title(question: str, limit: int = 40) -> str:
    title = " ".join(str(question or "").split())
    if len(title) > limit:
        title = title[:limit].rstrip() + "…"
    return title if title else "New chat"


def reset_document_viewer():
    st.session_state.pdf_bytes = None
    st.session_state.image_bytes = None
    st.session_state.current_page = 1
    st.session_state.page_input = 1
    st.session_state.pending_page = None
    st.session_state.highlight_text = ""
    st.session_state.active_source_key = None
    st.session_state.selected_source_bbox = None
    st.session_state.selected_source_bboxes = []
    st.session_state.selected_source_dimensions = None
    st.session_state.selected_source_confidence = None
    st.session_state.selected_source_match_type = None
    st.session_state.total_pages = 0
    st.session_state.total_chunks = 0


def clear_highlight():
    st.session_state.highlight_text = ""
    st.session_state.active_source_key = None
    st.session_state.selected_source_bbox = None
    st.session_state.selected_source_bboxes = []
    st.session_state.selected_source_dimensions = None
    st.session_state.selected_source_confidence = None
    st.session_state.selected_source_match_type = None


# ============================================================================
# DOCUMENT API
# ============================================================================

def fetch_selected_document_bytes(document_id: str):
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/documents/{document_id}/file",
            timeout=60,
        )
        response.raise_for_status()
        return response.content
    except requests.exceptions.RequestException:
        return None


def refresh_documents():
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/documents",
            timeout=30,
        )
        response.raise_for_status()

        documents = response.json() or []
        st.session_state.documents = documents
        st.session_state.documents_needs_refresh = False

        if not documents:
            st.session_state.document_id = None
            st.session_state.filename = None
            reset_document_viewer()
            return

        active_ids = {
            item.get("document_id")
            for item in documents
            if isinstance(item, dict)
        }

        if st.session_state.document_id not in active_ids:
            selected = documents[-1]
            st.session_state.document_id = selected.get("document_id")

        selected = next(
            (
                item
                for item in documents
                if item.get("document_id") == st.session_state.document_id
            ),
            documents[-1],
        )

        st.session_state.document_id = selected.get("document_id")
        st.session_state.filename = selected.get("filename")
        st.session_state.total_pages = selected.get("total_pages", 0)
        st.session_state.total_chunks = selected.get("total_chunks", 0)

        if st.session_state.filename and not st.session_state.pdf_bytes and not st.session_state.image_bytes:
            filename_lower = st.session_state.filename.lower()
            if filename_lower.endswith(".pdf"):
                st.session_state.pdf_bytes = fetch_selected_document_bytes(
                    st.session_state.document_id
                )
            elif any(filename_lower.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp")):
                st.session_state.image_bytes = fetch_selected_document_bytes(
                    st.session_state.document_id
                )


    except requests.exceptions.RequestException:
        st.session_state.documents = []
        st.session_state.documents_needs_refresh = False


def delete_document(document_id: str):
    try:
        response = requests.delete(
            f"{BACKEND_URL}/api/documents/{document_id}",
            timeout=30,
        )
        response.raise_for_status()

        if st.session_state.document_id == document_id:
            st.session_state.document_id = None
            st.session_state.filename = None
            reset_document_viewer()

        st.session_state.documents_needs_refresh = True
        refresh_documents()
        st.rerun()

    except requests.exceptions.RequestException as error:
        st.error(f"Document removal failed: {error}")


def clear_all_documents():
    try:
        response = requests.delete(
            f"{BACKEND_URL}/api/documents",
            timeout=30,
        )
        response.raise_for_status()

        st.session_state.document_id = None
        st.session_state.filename = None
        st.session_state.documents = []
        st.session_state.processed_file_fingerprints = set()
        st.session_state.upload_statuses = []
        reset_document_viewer()

        st.session_state.documents_needs_refresh = True
        refresh_documents()
        st.rerun()

    except requests.exceptions.RequestException as error:
        st.error(f"Workspace clear failed: {error}")


def activate_document(document: dict):
    document_id = document.get("document_id")
    filename = document.get("filename", "Document")
    st.session_state.document_id = document_id
    st.session_state.filename = filename
    st.session_state.total_pages = document.get("total_pages", 0)
    st.session_state.total_chunks = document.get("total_chunks", 0)
    reset_document_viewer()

    filename_lower = filename.lower()
    if filename_lower.endswith(".pdf"):
        st.session_state.pdf_bytes = fetch_selected_document_bytes(document_id)
    elif any(filename_lower.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp")):
        st.session_state.image_bytes = fetch_selected_document_bytes(document_id)



# ============================================================================
# CONVERSATION API
# ============================================================================

def load_conversations():
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/conversations",
            timeout=30,
        )
        response.raise_for_status()
        conversations = response.json() or []
        st.session_state.conversations = conversations
        return conversations
    except requests.exceptions.RequestException:
        st.session_state.conversations = []
        return []


def create_conversation_record(title: str = "New chat"):
    document_ids = [
        item.get("document_id")
        for item in st.session_state.documents
        if isinstance(item, dict) and item.get("document_id")
    ]

    payload = {
        "title": title,
        "document_ids": document_ids,
    }

    try:
        response = requests.post(
            f"{BACKEND_URL}/api/conversations",
            json=payload,
            timeout=30,
        )
        response.raise_for_status()

        data = response.json()

        st.session_state.conversation_id = data.get("conversation_id")
        st.session_state.conversation_title = data.get("title", title)
        st.session_state.messages = data.get("messages", [])

        clear_highlight()
        load_conversations()
        return data

    except requests.exceptions.RequestException as error:
        st.error(f"Could not create conversation: {error}")
        return None


def start_new_chat():
    active = st.session_state.get("conversation_id")
    if active:
        current = next(
            (
                conv
                for conv in st.session_state.conversations
                if conv.get("conversation_id") == active
            ),
            None,
        )
        # Reuse an existing empty chat instead of creating duplicates
        # across Streamlit reruns.
        if current and not current.get("messages"):
            st.session_state.messages = []
            st.session_state.conversation_title = (
                current.get("title") or "New chat"
            )
            clear_highlight()
            return

    create_conversation_record(title="New chat")
    clear_highlight()


def open_conversation(conversation_id: str):
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/conversations/{conversation_id}",
            timeout=30,
        )
        response.raise_for_status()

        data = response.json()

        st.session_state.conversation_id = conversation_id
        st.session_state.conversation_title = data.get("title", "New chat")
        st.session_state.messages = data.get("messages", [])
        clear_highlight()

        document_ids = data.get("document_ids") or []

        if document_ids:
            selected_id = document_ids[0]
            selected_document = next(
                (
                    item
                    for item in st.session_state.documents
                    if item.get("document_id") == selected_id
                ),
                None,
            )

            if selected_document:
                activate_document(selected_document)

        return data

    except requests.exceptions.RequestException as error:
        st.error(f"Could not open conversation: {error}")
        return None


def save_current_conversation():
    conversation_id = st.session_state.get("conversation_id")

    if not conversation_id:
        return None

    document_ids = [
        item.get("document_id")
        for item in st.session_state.documents
        if isinstance(item, dict) and item.get("document_id")
    ]

    if (
        st.session_state.document_id
        and st.session_state.document_id not in document_ids
    ):
        document_ids.insert(0, st.session_state.document_id)

    payload = {
        "title": st.session_state.get("conversation_title", "New chat"),
        "messages": st.session_state.get("messages", []),
        "document_ids": document_ids,
    }

    try:
        response = requests.patch(
            f"{BACKEND_URL}/api/conversations/{conversation_id}",
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        load_conversations()
        return response.json()

    except requests.exceptions.RequestException:
        return None


def delete_conversation(conversation_id: str):
    try:
        response = requests.delete(
            f"{BACKEND_URL}/api/conversations/{conversation_id}",
            timeout=30,
        )
        response.raise_for_status()

        input_key = f"rename_input_{conversation_id}"
        if input_key in st.session_state:
            del st.session_state[input_key]

        if st.session_state.conversation_id == conversation_id:
            st.session_state.conversation_id = None
            st.session_state.conversation_title = "New chat"
            st.session_state.messages = []
            clear_highlight()

        load_conversations()
        st.rerun()

    except requests.exceptions.RequestException as error:
        st.error(f"Conversation delete failed: {error}")


def rename_conversation(conversation_id: str, title: str):
    try:
        response = requests.patch(
            f"{BACKEND_URL}/api/conversations/{conversation_id}",
            json={"title": title},
            timeout=30,
        )
        response.raise_for_status()

        input_key = f"rename_input_{conversation_id}"
        if input_key in st.session_state:
            del st.session_state[input_key]

        if st.session_state.conversation_id == conversation_id:
            st.session_state.conversation_title = title

        load_conversations()
        st.rerun()

    except requests.exceptions.RequestException as error:
        st.error(f"Rename failed: {error}")


# ============================================================================
# PDF SECTION HIGHLIGHTING (BLOCK BASED)
# ============================================================================

SECTION_PADDING = 4.0
MIN_ANCHOR_WORDS = 4
MAX_SECTION_BLOCKS = 8
CONFIDENCE_MIN = 0.30
HEADING_LINK_GAP = 45.0
PARAGRAPH_CONTINUATION_GAP = 22.0
PARAGRAPH_REL_GAP = 1.3

_MAJOR_HEADING_RE = re.compile(r"^\d+(\.\d+)*[.`:]\s+\S")
_CHILD_HEADING_RE = re.compile(r"^\d+\.\d+[.`:]*\s+\S")
_QUESTION_HEADING_RE = re.compile(
    r"^(?:q[-.\s]?\d+|question)\b", re.IGNORECASE
)
_CODE_FONT_RE = re.compile(
    r"(?i)(mono|courier|consolas|code|fira|menlo|inconsolata|"
    r"sourcecode|jetbrains|dejavu)"
)

_BULLET_CHARS = "\u25cf\u2022\uf0b7\ufffd\u2219\u25e6\u2023\u2043\u00b7•·►▪*"
_PUNCT_TO_STRIP = ".,;:!?()[]{}<>|\\/\"'`“”‘’…"


def normalize_block_text(text: str) -> str:
    """
    Normalizes a block or the source passage for reliable matching:

    - Collapses line breaks and runs of spaces into single spaces.
    - Removes soft-hyphens and normalizes dash variants.
    - Treats hyphens as space-separated so "multi-agent" and
      "multi-\nagent" (broken across a PDF line) both normalize
      to the same token sequence.
    - Strips bullet markers and punctuation attached to word
      edges (so "step," and "step" both become "step").
    """
    if not text:
        return ""

    value = str(text)
    value = value.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
    value = value.replace("\u00ad", "")
    value = value.replace("\u2010", " ")
    value = value.replace("\u2013", " ")
    value = value.replace("\u2014", " ")
    for marker in _BULLET_CHARS:
        value = value.replace(marker, " ")
    value = value.replace("-", " ")
    value = " ".join(value.split())
    value = " ".join(
        token.strip(_PUNCT_TO_STRIP)
        for token in value.split()
        if token.strip(_PUNCT_TO_STRIP)
    )
    value = value.strip(_PUNCT_TO_STRIP)
    return value.lower()


def _is_title_case_line(text: str) -> bool:
    """
    True for short Title Case / ALL CAPS heading lines such as
    "Memory Management in OS" or "MEMORY MANAGEMENT".
    Sentence-fragment continuation lines ("Edges define which node
    executes next") are rejected because only their first word is
    capitalized.
    """
    compact = " ".join(str(text or "").split())
    words = compact.split()
    if not (1 <= len(words) <= 10):
        return False
    alpha = [w for w in words if any(c.isalpha() for c in w)]
    if not alpha:
        return False
    capitalized = sum(1 for w in alpha if w[0] and w[0].isupper())
    if capitalized / len(alpha) < 0.5:
        return False
    if compact[0] and not compact[0].isupper():
        return False
    return len(compact) <= 70


def is_child_heading(text: str) -> bool:
    """
    True for numbered sub-section headings such as "10.1 Installation",
    "10.2 Minimal Graph" or "11.1 Sequential Research and Review
    Workflow".
    """
    compact = " ".join(str(text or "").split())
    if not compact:
        return False
    return bool(_CHILD_HEADING_RE.match(compact))


def is_heading(text: str) -> bool:
    """
    True when the block text is a section heading:
    - numbered major headings ("10. LangGraph Fundamentals")
    - numbered child headings ("10.1 Installation")
    - question headings ("Q1 ...", "Question 2 ...")
    - short colon lead-ins ("The functions are:")
    - Title Case / ALL CAPS heading lines

    Bullet points and mid-sentence continuation lines are deliberately
    rejected.
    """
    compact = " ".join(str(text or "").split())
    if not compact:
        return False
    if is_child_heading(compact):
        return True
    if compact[0] in _BULLET_CHARS:
        return False
    if _MAJOR_HEADING_RE.match(compact):
        return True
    if _QUESTION_HEADING_RE.match(compact):
        return True
    if 2 <= len(compact) <= 90 and compact.endswith(":"):
        return True
    return _is_title_case_line(compact)


def _is_code_block(raw_text: str) -> bool:
    """
    Textual heuristics used to detect code blocks when the font
    information is inconclusive.
    """
    text = str(raw_text or "")
    if re.search(
        r"(?m)^\s*(def|class|import|from|return|print|"
        r"if __name__|public (static )?|private |const |let |var |"
        r"function |async |await )\b",
        text,
    ):
        return True
    if re.search(r"(?m)^\s*(>>>|\.\.\.)\s", text):
        return True
    stripped = "\n".join(
        line.strip() for line in text.splitlines() if line.strip()
    )
    if ";" in stripped and "{" in stripped:
        return True
    return False


def _extract_text_blocks(page) -> list[dict]:
    """
    Returns a list of text blocks from the page, sorted top-to-bottom,
    left-to-right, each with 'rect', 'raw', 'norm' and 'is_code' keys.

    Uses ``page.get_text("dict")`` so code blocks can be detected from
    monospace fonts in addition to text heuristics.
    """
    try:
        page_dict = page.get_text("dict")
    except Exception:
        return []

    blocks = []
    for block in page_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        lines = block.get("lines") or []
        raw_lines = []
        x0 = y0 = float("inf")
        x1 = y1 = float("-inf")
        code_chars = 0
        total_chars = 0

        for line in lines:
            parts = []
            for span in line.get("spans") or []:
                span_text = span.get("text") or ""
                if not span_text:
                    continue
                parts.append(span_text)
                total_chars += len(span_text)
                if _CODE_FONT_RE.search(span.get("font") or ""):
                    code_chars += len(span_text)
                bbox = span.get("bbox")
                if bbox and len(bbox) >= 4:
                    x0 = min(x0, bbox[0])
                    y0 = min(y0, bbox[1])
                    x1 = max(x1, bbox[2])
                    y1 = max(y1, bbox[3])
            if parts:
                raw_lines.append("".join(parts))

        raw = "\n".join(raw_lines).strip()
        if not raw or total_chars == 0 or x0 > x1:
            continue

        norm = normalize_block_text(raw)
        if not norm:
            continue

        is_code = (code_chars / total_chars) >= 0.6 or _is_code_block(raw)

        blocks.append({
            "rect": fitz.Rect(x0, y0, x1, y1),
            "raw": raw,
            "norm": norm,
            "is_code": is_code,
        })

    blocks.sort(
        key=lambda blk: (round(blk["rect"].y0, 1),
                         round(blk["rect"].x0, 1))
    )
    return blocks


def _overlap_words(source_words: list[str],
                   block_words: list[str]) -> int:
    """
    Number of source words that also occur in the block text
    (bag overlap, order-independent).
    """
    remaining = _word_counts(source_words)
    before = _remaining_count(remaining)
    _consume_words(remaining, " ".join(block_words))
    return before - _remaining_count(remaining)


def _word_counts(words: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for word in words:
        counts[word] = counts.get(word, 0) + 1
    return counts


def _consume_words(remaining: dict[str, int],
                   block_norm: str) -> None:
    for word in block_norm.split():
        if remaining.get(word, 0) > 0:
            remaining[word] -= 1


def _remaining_count(remaining: dict[str, int]) -> int:
    return sum(remaining.values())


def _padded_rect(rect: fitz.Rect, pad: float) -> fitz.Rect:
    return fitz.Rect(rect.x0 - pad, rect.y0 - pad,
                     rect.x1 + pad, rect.y1 + pad)


def find_best_matching_block(page, source_text):
    """
    Finds the block with the highest text overlap against the
    normalized source_text and estimates a confidence score between
    0.0 and 1.0 (min of block coverage and source coverage).

    Returns (blocks, matched_index, confidence).  matched_index is -1
    when no reliable match exists.
    """
    blocks = _extract_text_blocks(page)
    source_norm = normalize_block_text(source_text)
    source_words = source_norm.split() if source_norm else []

    if not source_words:
        return blocks, -1, 0.0

    best_index = -1
    best_score = -1.0
    best_overlap = 0
    best_block_ratio = 0.0
    best_source_ratio = 0.0

    for index, block in enumerate(blocks):
        block_words = block["norm"].split()
        if not block_words:
            continue
        overlap = _overlap_words(source_words, block_words)
        if overlap <= 0:
            continue

        block_ratio = overlap / len(block_words)
        source_ratio = overlap / len(source_words)
        score = (block_ratio + source_ratio) / 2.0

        if score > best_score or (score == best_score
                                  and overlap > best_overlap):
            best_index = index
            best_score = score
            best_overlap = overlap
            best_block_ratio = block_ratio
            best_source_ratio = source_ratio

    if best_index < 0:
        return blocks, -1, 0.0

    confidence = min(best_block_ratio, best_source_ratio)
    matched_is_heading = is_heading(blocks[best_index]["raw"])

    if matched_is_heading:
        reliable = best_overlap >= 2 and best_block_ratio >= 0.6
    else:
        reliable = (best_overlap >= MIN_ANCHOR_WORDS
                    and confidence >= CONFIDENCE_MIN)

    if not reliable:
        return blocks, -1, confidence

    return blocks, best_index, confidence


def get_related_heading(blocks, matched_index):
    """
    Returns the index of the heading block immediately above the
    matched paragraph, or None when there is no directly connected
    heading.

    Only the single previous block is considered: a parent section
    heading is NOT included when a child heading sits in between.
    """
    if matched_index is None or matched_index <= 0:
        return None

    previous = blocks[matched_index - 1]
    if previous.get("is_code"):
        return None
    if not is_heading(previous["raw"]):
        return None

    gap = blocks[matched_index]["rect"].y0 - previous["rect"].y1
    if gap < -2 or gap > HEADING_LINK_GAP:
        return None
    return matched_index - 1


def find_source_rectangles(page,
                           source_text: str) -> list[fitz.Rect]:
    """
    Strict section-level highlight matcher.

    1.  Finds the block with the highest text overlap against the
        source (find_best_matching_block).
    2.  When the matched block is a paragraph, returns its rectangle
        together with the heading directly above it (if any), plus any
        directly connected continuation blocks of the same paragraph
        that still contain source words.
    3.  When the matched block is a heading, returns the heading and
        the directly following paragraph only.

    Returns [] when no reliable match exists; it never falls back to
    whole-page or whole-section highlighting.
    """
    LOGGER.debug("find_source_rectangles start")
    if not source_text or page is None:
        return []

    blocks, matched_index, confidence = find_best_matching_block(
        page, source_text
    )

    if matched_index < 0:
        LOGGER.debug("no reliable matching block "
                     "(confidence_score=%.2f)", confidence)
        LOGGER.debug("selected_block_indices: []")
        LOGGER.debug("selected_rectangle_count: 0")
        return []

    matched = blocks[matched_index]
    selected = [matched_index]

    LOGGER.debug("matched_block_index: %d", matched_index)
    LOGGER.debug("matched_block_text: %r", matched["raw"].strip())
    LOGGER.debug("confidence_score: %.2f", confidence)

    if is_heading(matched["raw"]):
        # Rule: heading + the directly following paragraph only.
        LOGGER.debug("matched block is a heading; adding the "
                     "directly following paragraph")
        if matched_index + 1 < len(blocks):
            following = blocks[matched_index + 1]
            gap = following["rect"].y0 - matched["rect"].y1
            if (not is_heading(following["raw"])
                    and not following.get("is_code")
                    and -2 <= gap <= HEADING_LINK_GAP):
                selected.append(matched_index + 1)
        LOGGER.debug("matched_heading: %r", matched["raw"].strip())
    else:
        related_heading = get_related_heading(blocks, matched_index)
        if related_heading is not None:
            selected.append(related_heading)
            LOGGER.debug("matched_heading: %r",
                         blocks[related_heading]["raw"].strip())
        else:
            LOGGER.debug("matched_heading: None")

        # Directly connected continuation blocks that belong to the same
        # paragraph and still contain source words.
        source_norm = normalize_block_text(source_text)
        remaining = _word_counts(source_norm.split())
        _consume_words(remaining, matched["norm"])
        previous_rect = matched["rect"]

        for index in range(matched_index + 1, len(blocks)):
            if len(selected) >= MAX_SECTION_BLOCKS:
                break
            candidate = blocks[index]
            if is_heading(candidate["raw"]) or candidate.get("is_code"):
                LOGGER.debug("paragraph ends before block %d "
                             "(heading or code)", index)
                break
            if (candidate["raw"].lstrip()
                    and candidate["raw"].lstrip()[0] in _BULLET_CHARS):
                LOGGER.debug("paragraph ends before block %d "
                             "(new bullet point)", index)
                break
            gap = candidate["rect"].y0 - previous_rect.y1
            height = previous_rect.y1 - previous_rect.y0
            max_gap = max(PARAGRAPH_CONTINUATION_GAP,
                          PARAGRAPH_REL_GAP * max(height, 8.0))
            if gap < -2 or gap > max_gap:
                LOGGER.debug("paragraph ends before block %d "
                             "(unrelated block)", index)
                break
            before = _remaining_count(remaining)
            _consume_words(remaining, candidate["norm"])
            added = before - _remaining_count(remaining)
            if added <= 0:
                LOGGER.debug("paragraph ends before block %d "
                             "(no source words added)", index)
                break
            selected.append(index)
            previous_rect = candidate["rect"]

    selected.sort()

    rectangles = [_padded_rect(blocks[index]["rect"], SECTION_PADDING)
                  for index in selected]

    LOGGER.debug("selected_block_indices: %s", selected)
    LOGGER.debug("selected_rectangle_count: %d", len(rectangles))
    LOGGER.debug("find_source_rectangles done")

    return rectangles


# ============================================================================
# PDF RENDERING
# ============================================================================

def render_pdf_page(
    pdf_bytes: bytes,
    page_number: int,
    highlight_text: str = "",
):
    """
    Renders a PDF page as PNG and applies the highlight when a reliable
    match is found.  Returns (image_bytes, highlight_applied).
    """
    if not pdf_bytes:
        return None, False

    pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")

    try:
        total_pages = len(pdf_document)

        if total_pages == 0:
            return None, False

        page_number = max(
            1,
            min(page_number, total_pages),
        )

        page = pdf_document[page_number - 1]

        highlight_applied = False

        if highlight_text:
            rectangles = find_source_rectangles(page, highlight_text)

            for rectangle in rectangles:
                page.draw_rect(
                    rectangle,
                    color=(0.2, 0.7, 1.0),
                    fill=(0.25, 0.65, 1.0),
                    width=1,
                    fill_opacity=0.3,
                    overlay=True,
                )

            highlight_applied = bool(rectangles)

        matrix = fitz.Matrix(1.45, 1.45)
        pixmap = page.get_pixmap(
            matrix=matrix,
            alpha=False,
        )

        return pixmap.tobytes("png"), highlight_applied

    finally:
        pdf_document.close()


# ============================================================================
# SOURCES
# ============================================================================

def open_source(source: dict, source_key: str):
    # Clear the previous highlight first.
    clear_highlight()

    # If this source belongs to another document in workspace, switch to it:
    target_doc_id = source.get("document_id")
    if target_doc_id and target_doc_id != st.session_state.get("document_id"):
        for doc in st.session_state.get("documents", []):
            if doc.get("document_id") == target_doc_id:
                activate_document(doc)
                break

    page = source.get("page")
    if page is None:
        page = source.get("page_number")

    if page is not None:
        try:
            page = int(page)
        except (TypeError, ValueError):
            page = None

    if page is not None:
        st.session_state.pending_page = page

    exact = (
        source.get("exact_text")
        or source.get("text")
        or source.get("preview")
        or ""
    )

    if exact:
        st.session_state.highlight_text = exact
        st.session_state.active_source_key = source_key

    # Save image OCR source highlights
    st.session_state.selected_source_bbox = source.get("bbox")
    st.session_state.selected_source_bboxes = source.get("bboxes", [])
    st.session_state.selected_source_dimensions = (
        source.get("image_width"),
        source.get("image_height"),
    )
    st.session_state.selected_source_confidence = source.get("confidence")
    st.session_state.selected_source_match_type = source.get("match_type")
    if source.get("all_ocr_bboxes"):
        st.session_state.all_ocr_bboxes = source.get("all_ocr_bboxes", [])


def render_sources(sources, message_id):
    if not sources:
        return

    st.markdown(
        '<div class="source-label">📌 Document sources</div>',
        unsafe_allow_html=True,
    )

    for source_index, source in enumerate(sources):
        page_number = source.get("page")
        if page_number is None:
            page_number = source.get("page_number")

        file_type = str(source.get("file_type", "")).lower()
        title = source.get("title")

        if file_type in ("png", "jpg", "jpeg", "webp"):
            btn_label = f"🔍 View Image Source · {source.get('filename') or 'Image'}"
            btn_help = "Highlight the exact source text region in the image"
        elif file_type == "docx":
            btn_label = f"📖 Open source · {title or 'Section'}"
            btn_help = "Inspect source section text"
        else:
            p_label = f"Page {page_number}" if page_number is not None else (title or "Source")
            btn_label = f"📖 Open source · {p_label}"
            btn_help = "Navigate to this page and highlight the exact source text"

        source_key = f"source_{message_id}_{source_index}"
        is_active = (
            st.session_state.get("active_source_key") == source_key
        )

        button_type = "primary" if is_active else "secondary"

        if st.button(
            btn_label,
            key=f"open_{source_key}",
            use_container_width=True,
            type=button_type,
            help=btn_help,
        ):
            open_source(source, source_key)
            st.rerun()

        preview = (
            source.get("preview")
            or source.get("exact_text")
            or source.get("text")
            or ""
        )

        if preview:
            st.markdown(
                f'<div class="source-preview">{escape_html(preview)}</div>',
                unsafe_allow_html=True,
            )


# ============================================================================
# UPLOAD DOCUMENTS
# ============================================================================

def upload_documents(uploaded_files):
    files_to_upload = []

    for uploaded_file in uploaded_files:
        fingerprint = compute_file_fingerprint(uploaded_file)

        if fingerprint not in st.session_state.processed_file_fingerprints:
            files_to_upload.append(uploaded_file)

    if not files_to_upload:
        st.info("These files are already uploaded.")
        return

    st.session_state.upload_statuses = [
        {
            "name": uploaded_file.name,
            "status": "Pending",
        }
        for uploaded_file in files_to_upload
    ]

    uploaded_document_ids = []

    with st.spinner("Processing your documents..."):
        for uploaded_file in files_to_upload:
            try:
                response = requests.post(
                    f"{BACKEND_URL}/api/upload",
                    files={
                        "files": (
                            uploaded_file.name,
                            uploaded_file.getvalue(),
                            uploaded_file.type,
                        )
                    },
                    timeout=240,
                )

                if response.status_code == 409:
                    status = "Already uploaded"
                    document_ids = []

                else:
                    response.raise_for_status()
                    data = response.json()
                    document_ids = []

                    if isinstance(data, dict) and "documents" in data:
                        for item in data["documents"]:
                            document_id = item.get("document_id")
                            if document_id:
                                document_ids.append(document_id)

                    elif isinstance(data, dict):
                        document_id = data.get("document_id")
                        if document_id:
                            document_ids.append(document_id)

                    status = "Uploaded"

                uploaded_document_ids.extend(document_ids)

                fingerprint = compute_file_fingerprint(uploaded_file)
                st.session_state.processed_file_fingerprints.add(fingerprint)

                for item in st.session_state.upload_statuses:
                    if item["name"] == uploaded_file.name:
                        item["status"] = status

            except requests.exceptions.RequestException as error:
                detail_msg = ""
                if getattr(error, "response", None) is not None:
                    try:
                        detail_msg = error.response.json().get("detail", "")
                    except Exception:
                        detail_msg = getattr(error.response, "text", "")
                error_display = detail_msg or str(error)

                for item in st.session_state.upload_statuses:
                    if item["name"] == uploaded_file.name:
                        item["status"] = "Failed"

                st.error(
                    f"Upload failed for {uploaded_file.name}: {error_display}"
                )


    if uploaded_document_ids:
        st.session_state.document_id = uploaded_document_ids[-1]
        st.session_state.filename = files_to_upload[-1].name
        st.session_state.messages = []
        reset_document_viewer()
        st.session_state.documents_needs_refresh = True

    refresh_documents()
    load_conversations()

    if uploaded_document_ids:
        start_new_chat()

    st.success("Document processing completed.")
    st.rerun()


# ============================================================================
# LOAD DATA ON STARTUP
# ============================================================================

if st.session_state.documents_needs_refresh:
    refresh_documents()

load_conversations()


# ============================================================================
# HEADER
# ============================================================================

st.markdown(
    """
    <div class="brand-chip">📘</div>
    <div class="main-title">DocuMind AI</div>
    <div class="subtitle">
        Understand your documents with intelligent AI-powered conversations.
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================================
# SIDEBAR
# ============================================================================

with st.sidebar:
    st.markdown(
        """
        <div class="sidebar-brand">
            <div class="sidebar-brand-icon">📘</div>
            <div>DocuMind AI</div>
        </div>
        <div class="sidebar-caption">
            Your intelligent document workspace.
            Upload files and chat with your knowledge base.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button(
        "＋ New chat",
        use_container_width=True,
    ):
        start_new_chat()
        st.rerun()

    st.markdown(
        '<div class="sidebar-section">Chats</div>',
        unsafe_allow_html=True,
    )

    if st.session_state.conversations:
        with st.container(height=300):
            for conversation in st.session_state.conversations:
                conversation_id = conversation.get("conversation_id")

                if not conversation_id:
                    continue

                title = conversation.get("title") or "New chat"
                display_title = truncate_display(title, 34)
                is_active = (
                    conversation_id == st.session_state.conversation_id
                )

                chat_col, menu_col = st.columns([5, 1])

                with chat_col:
                    if st.button(
                        display_title,
                        key=f"chat_{conversation_id}",
                        use_container_width=True,
                        type="primary" if is_active else "secondary",
                        help=title,
                    ):
                        open_conversation(conversation_id)
                        clear_highlight()
                        st.rerun()

                with menu_col:
                    with st.popover("⋯"):
                        st.caption("Chat options")

                        new_title = st.text_input(
                            "Rename chat",
                            key=f"rename_input_{conversation_id}",
                            value=title,
                        )

                        if st.button(
                            "Rename",
                            key=f"rename_button_{conversation_id}",
                            use_container_width=True,
                        ):
                            if new_title.strip():
                                rename_conversation(
                                    conversation_id,
                                    new_title.strip(),
                                )

                        if st.button(
                            "Delete chat",
                            key=f"delete_button_{conversation_id}",
                            use_container_width=True,
                        ):
                            delete_conversation(conversation_id)
    else:
        st.caption("No chats yet. Start a new conversation.")

    st.markdown(
        '<div class="sidebar-section">Documents</div>',
        unsafe_allow_html=True,
    )

    upload_key = f"file_uploader_{st.session_state.upload_key}"

    uploaded_files = st.file_uploader(
        "Choose PDF, DOCX, or Image (PNG, JPG, WEBP)",
        type=["pdf", "docx", "png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        key=upload_key,
    )

    if uploaded_files:
        if st.button(
            "Upload and process",
            use_container_width=True,
        ):
            upload_documents(uploaded_files)

    if st.session_state.upload_statuses:
        st.markdown(
            '<div class="sidebar-section">Upload status</div>',
            unsafe_allow_html=True,
        )

        for item in st.session_state.upload_statuses:
            status = item.get("status", "Pending")

            status_color = {
                "Uploaded": "#86efac",
                "Already uploaded": "#facc15",
                "Failed": "#fca5a5",
                "Pending": "#cbd5e1",
            }.get(status, "#cbd5e1")

            st.markdown(
                f"""
                <div style="
                    padding:8px 10px;
                    border-left:3px solid {status_color};
                    border-radius:7px;
                    background:rgba(15,23,42,0.55);
                    margin-bottom:7px;
                    font-size:11px;
                ">
                    {escape_html(item.get("name", "Unknown file"))}
                    <br>
                    <strong>{escape_html(status)}</strong>
                </div>
                """,
                unsafe_allow_html=True,
            )

    if st.session_state.documents:
        for document in st.session_state.documents:
            document_id = document.get("document_id")

            if not document_id:
                continue

            filename = document.get("filename", "Document")
            is_active = document_id == st.session_state.document_id
            card_class = "doc-card active" if is_active else "doc-card"

            file_type = str(document.get("file_type", "file")).lower()
            if file_type in ("png", "jpg", "jpeg", "webp"):
                type_badge = f"🖼️ {file_type.upper()} · OCR Ready"
            elif file_type == "docx":
                type_badge = "📝 DOCX · Document"
            else:
                type_badge = f"📄 {file_type.upper()} · {document.get('total_pages', 0)} pages"

            st.markdown(
                f"""
                <div class="{card_class}">
                    <div class="doc-name">
                        {escape_html(filename)}
                    </div>
                    <div class="doc-meta">
                        {escape_html(type_badge)}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


            document_col, remove_col = st.columns([1, 1])

            with document_col:
                if st.button(
                    "Use",
                    key=f"use_document_{document_id}",
                    use_container_width=True,
                ):
                    activate_document(document)
                    st.rerun()

            with remove_col:
                if st.button(
                    "Remove",
                    key=f"remove_document_{document_id}",
                    use_container_width=True,
                ):
                    delete_document(document_id)

        if st.button(
            "Clear all documents",
            use_container_width=True,
        ):
            clear_all_documents()

    if st.session_state.document_id:
        st.markdown(
            '<div class="sidebar-section">Workspace</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div class="status-badge">
                <span class="status-dot"></span>
                Document ready
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.caption(st.session_state.filename)

        metric_col1, metric_col2 = st.columns(2)

        with metric_col1:
            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-label">Pages</div>
                    <div class="metric-value">
                        {st.session_state.total_pages or "—"}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with metric_col2:
            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-label">Chunks</div>
                    <div class="metric-value">
                        {st.session_state.total_chunks or "—"}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        if st.button(
            "Clear chat",
            use_container_width=True,
        ):
            st.session_state.messages = []
            clear_highlight()
            st.session_state.pending_page = None
            save_current_conversation()
            st.rerun()

        if st.button(
            "Reset workspace",
            use_container_width=True,
        ):
            st.session_state.document_id = None
            st.session_state.filename = None
            st.session_state.documents = []
            st.session_state.upload_key += 1
            st.session_state.upload_statuses = []
            st.session_state.processed_file_fingerprints = set()
            reset_document_viewer()
            st.session_state.documents_needs_refresh = True
            st.rerun()

    st.divider()

    st.caption("DocuMind AI")
    st.caption("Powered by xAI Grok + FastAPI")


# ============================================================================
# MAIN LAYOUT
# ============================================================================

left_column, right_column = st.columns(
    [1.08, 0.92],
    gap="large",
)


# ============================================================================
# DOCUMENT VIEWER
# ============================================================================

with left_column:
    st.markdown(
        '<div class="panel-title">📄 Document Viewer</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="panel-sub">Read, navigate and inspect source references.</div>',
        unsafe_allow_html=True,
    )

    with st.container(height=760, border=True):
        if st.session_state.pdf_bytes:
            pdf_document = fitz.open(
                stream=st.session_state.pdf_bytes,
                filetype="pdf",
            )
            total_pages = len(pdf_document)
            pdf_document.close()

            if st.session_state.pending_page is not None:
                requested_page = int(st.session_state.pending_page)
                requested_page = max(
                    1,
                    min(requested_page, total_pages),
                )
                st.session_state.current_page = requested_page
                st.session_state.page_input = requested_page
                st.session_state.pending_page = None

            current_page = max(
                1,
                min(
                    st.session_state.current_page,
                    total_pages,
                ),
            )

            nav_col, page_col, action_col = st.columns([1, 1.4, 1])

            with nav_col:
                st.write("")

                if st.button(
                    "◀ Prev",
                    key="prev_page",
                    use_container_width=True,
                    disabled=current_page <= 1,
                ):
                    st.session_state.page_input = max(1, current_page - 1)
                    st.rerun()

            with page_col:
                selected_page = st.number_input(
                    "Page",
                    min_value=1,
                    max_value=total_pages,
                    step=1,
                    key="page_input",
                )
                st.session_state.current_page = int(selected_page)

            with action_col:
                st.write("")

                if st.button(
                    "Next ▶",
                    key="next_page",
                    use_container_width=True,
                    disabled=current_page >= total_pages,
                ):
                    st.session_state.page_input = min(
                        total_pages,
                        current_page + 1,
                    )
                    st.rerun()

            if st.session_state.highlight_text:
                if st.button(
                    "Clear highlight",
                    key="clear_highlight_btn",
                    use_container_width=True,
                ):
                    clear_highlight()
                    st.rerun()

            page_image, highlight_applied = render_pdf_page(
                pdf_bytes=st.session_state.pdf_bytes,
                page_number=st.session_state.current_page,
                highlight_text=st.session_state.highlight_text,
            )

            if page_image:
                st.image(
                    page_image,
                    use_container_width=True,
                )

            if st.session_state.highlight_text:
                if highlight_applied:
                    st.caption(
                        f"✓ Source highlighted on page "
                        f"{st.session_state.current_page}"
                    )
                else:
                    st.caption(
                        "The source section could not be located "
                        "on this page."
                    )

        elif st.session_state.image_bytes or (
            st.session_state.filename
            and any(st.session_state.filename.lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp"))
        ):
            if not st.session_state.image_bytes and st.session_state.document_id:
                st.session_state.image_bytes = fetch_selected_document_bytes(
                    st.session_state.document_id
                )

            if st.session_state.image_bytes:
                has_active_highlight = bool(
                    st.session_state.get("highlight_text")
                    or st.session_state.get("selected_source_bbox")
                    or st.session_state.get("selected_source_bboxes")
                )
                if has_active_highlight:
                    if st.button(
                        "Clear highlight",
                        key="clear_image_highlight_btn",
                        use_container_width=True,
                    ):
                        clear_highlight()
                        st.rerun()

                show_all_ocr = st.checkbox(
                    "Show all detected text regions",
                    value=st.session_state.get("show_all_ocr_regions", False),
                    key="toggle_all_ocr_regions",
                )
                st.session_state.show_all_ocr_regions = show_all_ocr

                orig_dims = st.session_state.get("selected_source_dimensions")
                orig_w, orig_h = (None, None)
                if orig_dims and isinstance(orig_dims, (list, tuple)) and len(orig_dims) == 2:
                    orig_w, orig_h = orig_dims[0], orig_dims[1]

                if not orig_w or not orig_h:
                    try:
                        with Image.open(BytesIO(st.session_state.image_bytes)) as pil_img:
                            orig_w, orig_h = pil_img.size
                    except Exception:
                        orig_w, orig_h = 1000, 1000

                fname_lower = (st.session_state.filename or "").lower()
                if fname_lower.endswith(".jpg") or fname_lower.endswith(".jpeg"):
                    mime_type = "image/jpeg"
                elif fname_lower.endswith(".webp"):
                    mime_type = "image/webp"
                else:
                    mime_type = "image/png"

                img_b64 = base64.b64encode(st.session_state.image_bytes).decode("utf-8")

                all_boxes = st.session_state.get("all_ocr_bboxes", [])
                selected_box = st.session_state.get("selected_source_bbox")
                selected_boxes = st.session_state.get("selected_source_bboxes", [])

                selected_boxes_json = json.dumps(selected_boxes or ([selected_box] if selected_box else []))
                overall_box_json = json.dumps(selected_box or {})
                all_ocr_boxes_json = json.dumps(all_boxes if show_all_ocr else [])

                LOGGER.info("[DocuMind Frontend Image Viewer] Filename: %s, Dimensions: %sx%s", st.session_state.filename, orig_w, orig_h)
                LOGGER.info("[DocuMind Frontend Image Viewer] Selected bbox: %s", selected_box)
                LOGGER.info("[DocuMind Frontend Image Viewer] Selected bboxes count: %d", len(selected_boxes))

                aspect_ratio = orig_h / max(1, orig_w)
                estimated_height = int(680 * aspect_ratio) + 25
                viewer_height = min(900, max(280, estimated_height))

                component_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: transparent;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    overflow-x: hidden;
  }}
  .image-container {{
    position: relative;
    width: 100%;
    display: inline-block;
    border-radius: 8px;
    overflow: hidden;
    background: #080c1a;
    border: 1px solid rgba(99, 102, 241, 0.25);
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
  }}
  .doc-image {{
    display: block;
    width: 100%;
    height: auto;
    user-select: none;
  }}
  .highlight-overlay {{
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
  }}
  .ocr-box {{
    fill: rgba(56, 189, 248, 0.08);
    stroke: rgba(56, 189, 248, 0.5);
    stroke-width: 1.5px;
    stroke-dasharray: 4,2;
    rx: 2px;
  }}
  .source-box {{
    fill: rgba(99, 102, 241, 0.38);
    stroke: #818cf8;
    stroke-width: 2.5px;
    rx: 4px;
    filter: drop-shadow(0 0 6px rgba(99, 102, 241, 0.7));
  }}
  .enclosing-box {{
    fill: none;
    stroke: #c084fc;
    stroke-width: 2px;
    stroke-dasharray: 6,3;
    rx: 6px;
    filter: drop-shadow(0 0 8px rgba(192, 132, 252, 0.6));
  }}
</style>
</head>
<body>

<div class="image-container" id="container">
  <img id="doc-image" class="doc-image" src="data:{mime_type};base64,{img_b64}" alt="Document Image" />
  <svg id="svg-overlay" class="highlight-overlay" xmlns="http://www.w3.org/2000/svg">
  </svg>
</div>

<script>
  const origW = {orig_w};
  const origH = {orig_h};
  const selectedBoxes = {selected_boxes_json};
  const overallBox = {overall_box_json};
  const allOcrBoxes = {all_ocr_boxes_json};

  const img = document.getElementById('doc-image');
  const svg = document.getElementById('svg-overlay');
  const container = document.getElementById('container');

  function renderHighlights() {{
    const dispW = img.clientWidth || img.offsetWidth;
    const dispH = img.clientHeight || img.offsetHeight;
    if (!dispW || !dispH || !origW || !origH) return;

    const scaleX = dispW / origW;
    const scaleY = dispH / origH;

    console.log('[DocuMind Client] Original dimensions:', origW, origH);
    console.log('[DocuMind Client] Displayed dimensions:', dispW, dispH);
    console.log('[DocuMind Client] Scale factors: scaleX=' + scaleX + ', scaleY=' + scaleY);
    console.log('[DocuMind Client] Selected boxes:', selectedBoxes);

    svg.innerHTML = '';
    svg.setAttribute('viewBox', '0 0 ' + dispW + ' ' + dispH);

    // 1. Draw all OCR boxes if toggled on
    if (allOcrBoxes && allOcrBoxes.length > 0) {{
      allOcrBoxes.forEach(function(b) {{
        const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        rect.setAttribute('x', (b.x * scaleX));
        rect.setAttribute('y', (b.y * scaleY));
        rect.setAttribute('width', Math.max(2, b.width * scaleX));
        rect.setAttribute('height', Math.max(2, b.height * scaleY));
        rect.setAttribute('class', 'ocr-box');
        svg.appendChild(rect);
      }});
    }}

    let firstSourceEl = null;

    // 2. Draw individual matched source boxes
    if (selectedBoxes && selectedBoxes.length > 0) {{
      selectedBoxes.forEach(function(b, idx) {{
        const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        const sx = b.x * scaleX;
        const sy = b.y * scaleY;
        const sw = Math.max(3, b.width * scaleX);
        const sh = Math.max(3, b.height * scaleY);
        rect.setAttribute('x', sx);
        rect.setAttribute('y', sy);
        rect.setAttribute('width', sw);
        rect.setAttribute('height', sh);
        rect.setAttribute('class', 'source-box');
        rect.id = 'source-rect-' + idx;
        svg.appendChild(rect);
        if (!firstSourceEl) firstSourceEl = rect;
      }});

      // 3. Enclosing border if multiple boxes
      if (overallBox && overallBox.x !== undefined && selectedBoxes.length > 1) {{
        const enc = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        const padX = 4 * scaleX;
        const padY = 4 * scaleY;
        enc.setAttribute('x', Math.max(0, overallBox.x * scaleX - padX));
        enc.setAttribute('y', Math.max(0, overallBox.y * scaleY - padY));
        enc.setAttribute('width', overallBox.width * scaleX + padX * 2);
        enc.setAttribute('height', overallBox.height * scaleY + padY * 2);
        enc.setAttribute('class', 'enclosing-box');
        svg.appendChild(enc);
      }}
    }}

    // 4. Scroll to highlighted region smoothly
    if (firstSourceEl) {{
      const targetY = parseFloat(firstSourceEl.getAttribute('y')) || 0;
      window.scrollTo({{ top: Math.max(0, targetY - 60), behavior: 'smooth' }});
    }}
  }}

  img.addEventListener('load', renderHighlights);
  if (img.complete) renderHighlights();

  window.addEventListener('resize', renderHighlights);
  if (window.ResizeObserver) {{
    new ResizeObserver(renderHighlights).observe(container);
  }}
</script>
</body>
</html>"""
                components.html(component_html, height=viewer_height, scrolling=True)

                if selected_box or selected_boxes:
                    conf = st.session_state.get("selected_source_confidence")
                    conf_badge = f" · Confidence: {int(conf * 100)}%" if conf else ""
                    match_type = st.session_state.get("selected_source_match_type")
                    type_badge = f" ({match_type} match)" if match_type else ""
                    st.markdown(
                        f"""
                        <div style="
                            margin-top: 4px;
                            margin-bottom: 12px;
                            padding: 9px 13px;
                            border-radius: 8px;
                            background: rgba(99, 102, 241, 0.14);
                            border: 1px solid rgba(99, 102, 241, 0.35);
                            font-size: 12.5px;
                            color: #c7d2fe;
                        ">
                            ✓ <strong>Answer source highlighted in image</strong>{type_badge}{conf_badge}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                elif st.session_state.get("highlight_text"):
                    st.markdown(
                        """
                        <div style="
                            margin-top: 4px;
                            margin-bottom: 12px;
                            padding: 9px 13px;
                            border-radius: 8px;
                            background: rgba(239, 68, 68, 0.12);
                            border: 1px solid rgba(239, 68, 68, 0.35);
                            font-size: 12.5px;
                            color: #fca5a5;
                        ">
                            ⚠️ <strong>Source location could not be identified in this image.</strong>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        """
                        <div style="
                            margin-top: 4px;
                            margin-bottom: 12px;
                            padding: 9px 13px;
                            border-radius: 8px;
                            background: rgba(99, 102, 241, 0.10);
                            border: 1px solid rgba(99, 102, 241, 0.25);
                            font-size: 12px;
                            color: #c7d2fe;
                        ">
                            ✓ <strong>OCR text extracted & ready for chat</strong>: Click any source citation or ask questions about this image in the AI Assistant panel.
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown(
                    """
                    <div class="empty-state">
                        <div class="empty-icon">🖼️</div>
                        <div class="empty-title">Image preview unavailable</div>
                        <div class="empty-text">
                            Preview unavailable / OCR text available.<br>
                            You can ask questions about this image in the chat panel.
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        elif st.session_state.filename and st.session_state.filename.lower().endswith(".docx"):
            st.markdown(
                """
                <div class="empty-state">
                    <div class="empty-icon">📄</div>
                    <div class="empty-title">DOCX preview unavailable</div>
                    <div class="empty-text">
                        Preview unavailable / document text available.<br>
                        Ask questions about this DOCX document in the chat panel.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        elif st.session_state.filename:
            st.markdown(
                """
                <div class="empty-state">
                    <div class="empty-icon">📄</div>
                    <div class="empty-title">Document ready</div>
                    <div class="empty-text">
                        Preview unavailable / text available.<br>
                        This file is ready for chat.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        else:
            st.markdown(
                """
                <div class="empty-state">
                    <div class="empty-icon">📚</div>
                    <div class="empty-title">Your document workspace</div>
                    <div class="empty-text">
                        Upload a PDF, DOCX, or Image (PNG, JPG, WEBP) from the sidebar<br>
                        to start reading and asking questions.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )



# ============================================================================
# AI CHAT
# ============================================================================

with right_column:
    st.markdown(
        '<div class="panel-title">🤖 AI Assistant</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="panel-sub">Ask questions and explore your documents.</div>',
        unsafe_allow_html=True,
    )

    with st.container(height=760, border=True):
        if not st.session_state.document_id:
            st.markdown(
                """
                <div class="empty-state">
                    <div class="empty-icon">✨</div>
                    <div class="empty-title">Start a conversation</div>
                    <div class="empty-text">
                        Upload your document and ask anything about it.<br>
                        Try: "Give me a summary of this document."
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        else:
            for message_index, message in enumerate(
                st.session_state.messages
            ):
                role = message.get("role", "assistant")
                content = message.get("content", "")

                with st.chat_message(role):
                    st.markdown(escape_html(content))

                    render_sources(
                        sources=message.get("sources", []),
                        message_id=message_index,
                    )

    question = st.chat_input(
        "Ask about your document...",
        disabled=not bool(st.session_state.document_id),
    )

    if question:
        question = question.strip()

        if not question:
            st.stop()

        # ------------------------------------------------------------
        # 1. Ensure a conversation exists (no duplicates on reruns).
        # ------------------------------------------------------------
        if not st.session_state.get("conversation_id"):
            create_conversation_record(title=auto_title(question))
        elif (
            not st.session_state.get("conversation_title")
            or st.session_state.conversation_title == "New chat"
        ):
            new_title = auto_title(question)
            st.session_state.conversation_title = new_title

            try:
                requests.patch(
                    f"{BACKEND_URL}/api/conversations/{st.session_state.conversation_id}",
                    json={"title": new_title},
                    timeout=30,
                ).raise_for_status()
            except requests.exceptions.RequestException:
                pass

            load_conversations()

        # Clear any previous highlight from an earlier question.
        clear_highlight()

        # ------------------------------------------------------------
        # 2. Store the user message.
        # ------------------------------------------------------------
        current_count = len(st.session_state.messages)
        user_message_id = current_count + 1

        st.session_state.messages.append(
            {
                "id": user_message_id,
                "role": "user",
                "content": question,
                "sources": [],
            }
        )

        save_current_conversation()

        with st.chat_message("user"):
            st.markdown(escape_html(question))

        # ------------------------------------------------------------
        # 3. Ask the backend and store the assistant message.
        # ------------------------------------------------------------
        assistant_message_id = current_count + 2

        with st.chat_message("assistant"):
            with st.spinner("Analyzing your document..."):
                payload = {
                    "question": question,
                }

                if st.session_state.document_id:
                    payload["document_id"] = st.session_state.document_id

                document_ids = [
                    doc.get("document_id")
                    for doc in st.session_state.documents
                    if isinstance(doc, dict) and doc.get("document_id")
                ]

                if document_ids:
                    payload["document_ids"] = document_ids

                if getattr(st.session_state, "conversation_id", None):
                    payload["conversation_id"] = st.session_state.conversation_id

                try:
                    response = requests.post(
                        f"{BACKEND_URL}/api/chat",
                        json=payload,
                        timeout=240,
                    )
                    response.raise_for_status()

                    data = response.json()

                    answer = (
                        data.get("answer")
                        or data.get("response")
                        or data.get("message")
                        or ""
                    )

                    sources = data.get("sources", [])

                    if not answer:
                        raise RuntimeError(
                            "Backend returned an empty answer."
                        )

                    st.markdown(escape_html(answer))

                    render_sources(
                        sources=sources,
                        message_id=assistant_message_id,
                    )

                    st.session_state.messages.append(
                        {
                            "id": assistant_message_id,
                            "role": "assistant",
                            "content": answer,
                            "sources": sources,
                        }
                    )

                except Exception as error:
                    server_detail = None
                    if hasattr(error, "response") and getattr(error, "response", None) is not None:
                        try:
                            error_json = error.response.json()
                            server_detail = error_json.get("detail")
                        except Exception:
                            server_detail = getattr(error.response, "text", None)

                    if server_detail:
                        error_message = f"I couldn't get an answer: {server_detail}"
                    else:
                        error_message = f"I couldn't get an answer: {error}"

                    st.error(error_message)

                    st.session_state.messages.append(
                        {
                            "id": assistant_message_id,
                            "role": "assistant",
                            "content": error_message,
                            "sources": [],
                        }
                    )

                save_current_conversation()

        st.rerun()