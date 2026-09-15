import re
from io import BytesIO

import fitz
import requests
import streamlit as st


# ============================================================
# CONFIGURATION
# ============================================================

BACKEND_URL = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="DocuMind AI",
    page_icon="📘",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# CUSTOM THEME
# ============================================================

st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
        }

        .stApp {
            background:
                radial-gradient(
                    circle at top right,
                    rgba(37, 99, 235, 0.13),
                    transparent 32%
                ),
                linear-gradient(
                    135deg,
                    #07111f 0%,
                    #0b1729 48%,
                    #101c31 100%
                );
            color: #e5edf8;
        }

        [data-testid="stHeader"] {
            background: transparent;
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(
                180deg,
                #091525 0%,
                #0d1b30 100%
            );
            border-right: 1px solid rgba(148, 163, 184, 0.16);
        }

        [data-testid="stSidebar"] * {
            color: #dbeafe;
        }

        .main-title {
            font-size: 42px;
            font-weight: 800;
            letter-spacing: -1.8px;
            line-height: 1.1;
            margin-top: 8px;
            margin-bottom: 8px;
            background: linear-gradient(
                90deg,
                #ffffff,
                #93c5fd,
                #60a5fa
            );
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .subtitle {
            color: #94a3b8;
            font-size: 14px;
            margin-bottom: 26px;
        }

        .brand-mark {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 42px;
            height: 42px;
            border-radius: 13px;
            background: linear-gradient(
                135deg,
                #2563eb,
                #38bdf8
            );
            box-shadow: 0 8px 25px rgba(37, 99, 235, 0.35);
            font-size: 22px;
            margin-bottom: 14px;
        }

        .section-title {
            font-size: 19px;
            font-weight: 700;
            color: #f8fafc;
            margin-bottom: 4px;
        }

        .section-subtitle {
            font-size: 12px;
            color: #94a3b8;
            margin-bottom: 14px;
        }

        .status-badge {
            display: inline-flex;
            align-items: center;
            gap: 7px;
            background: rgba(34, 197, 94, 0.12);
            border: 1px solid rgba(34, 197, 94, 0.28);
            color: #86efac;
            border-radius: 999px;
            padding: 7px 12px;
            font-size: 12px;
            font-weight: 600;
        }

        .status-dot {
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background: #22c55e;
            box-shadow: 0 0 10px rgba(34, 197, 94, 0.8);
        }

        .empty-state {
            text-align: center;
            padding: 80px 20px;
            color: #94a3b8;
        }

        .empty-icon {
            font-size: 48px;
            margin-bottom: 16px;
        }

        .empty-title {
            color: #e2e8f0;
            font-size: 18px;
            font-weight: 700;
            margin-bottom: 8px;
        }

        .empty-text {
            font-size: 13px;
            line-height: 1.7;
        }

        .source-label {
            color: #93c5fd;
            font-size: 12px;
            font-weight: 700;
            margin-top: 12px;
            margin-bottom: 6px;
        }

        .source-preview {
            color: #94a3b8;
            font-size: 11px;
            line-height: 1.5;
            padding: 8px 10px;
            border-left: 2px solid #2563eb;
            background: rgba(37, 99, 235, 0.07);
            border-radius: 4px;
            margin-bottom: 8px;
        }

        .stButton > button {
            border-radius: 9px;
            border: 1px solid rgba(96, 165, 250, 0.24);
            background: rgba(30, 64, 175, 0.18);
            color: #dbeafe;
            font-weight: 600;
            transition: all 0.2s ease;
        }

        .stButton > button:hover {
            border-color: #60a5fa;
            background: rgba(37, 99, 235, 0.35);
            color: white;
        }

        .stDownloadButton > button {
            border-radius: 9px;
        }

        [data-testid="stChatMessage"] {
            background: rgba(15, 23, 42, 0.58);
            border: 1px solid rgba(148, 163, 184, 0.12);
            border-radius: 14px;
            margin-bottom: 10px;
        }

        [data-testid="stChatMessageContent"] {
            color: #dbeafe;
        }

        [data-testid="stFileUploader"] {
            background: rgba(15, 23, 42, 0.55);
            border: 1px dashed rgba(96, 165, 250, 0.35);
            border-radius: 12px;
            padding: 8px;
        }

        [data-testid="stVerticalBlockBorderWrapper"] {
            border: 1px solid rgba(148, 163, 184, 0.16);
            border-radius: 16px;
            background: rgba(8, 18, 33, 0.48);
        }

        .stTextInput input,
        .stNumberInput input {
            background: rgba(15, 23, 42, 0.8);
            color: #e2e8f0;
            border: 1px solid rgba(96, 165, 250, 0.25);
            border-radius: 9px;
        }

        .stSelectbox div[data-baseweb="select"] {
            background: rgba(15, 23, 42, 0.8);
            border-radius: 9px;
        }

        hr {
            border-color: rgba(148, 163, 184, 0.15);
        }

        .metric-card {
            background: rgba(15, 23, 42, 0.62);
            border: 1px solid rgba(96, 165, 250, 0.15);
            border-radius: 12px;
            padding: 12px;
            margin-bottom: 12px;
        }

        .metric-label {
            color: #94a3b8;
            font-size: 11px;
        }

        .metric-value {
            color: #e0f2fe;
            font-size: 20px;
            font-weight: 800;
            margin-top: 3px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SESSION STATE
# ============================================================

DEFAULT_STATE = {
    "document_id": None,
    "filename": None,
    "pdf_bytes": None,
    "messages": [],
    "current_page": 1,
    "page_input": 1,
    "highlight_text": "",
    "pending_page": None,
    "upload_key": 0,
    "total_pages": 0,
    "total_chunks": 0,
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# TEXT HELPERS
# ============================================================

def normalize_text(text: str) -> str:
    if not text:
        return ""

    return " ".join(str(text).split()).strip()


def clean_word_text(text: str) -> str:
    if not text:
        return ""

    text = str(text).strip()

    bullet_pattern = re.compile(
        r"^[\u25cf\u2022\uf0b7\ufffd\u2219\u25e6\u2023\u2043\u00b7\s]+$"
    )

    if bullet_pattern.fullmatch(text):
        return ""

    return text


# ============================================================
# PDF TEXT MATCHING
# ============================================================

def get_pdf_words(page):
    words = page.get_text("words")

    if not words:
        return []

    result = []

    for word in words:
        if len(word) < 5:
            continue

        x0, y0, x1, y1, text = word[:5]
        text = clean_word_text(text)

        if not text:
            continue

        result.append(
            {
                "x0": x0,
                "y0": y0,
                "x1": x1,
                "y1": y1,
                "text": text,
            }
        )

    return result


def find_paragraph_rectangles(page, source_text: str):
    """
    Source text jis PDF text block ke andar milta hai,
    us complete paragraph/text block ko highlight karta hai.
    """

    if not source_text:
        return []

    normalized_source = normalize_text(source_text).lower()

    if len(normalized_source) < 10:
        return []

    blocks = page.get_text("blocks")

    if not blocks:
        return []

    for block in blocks:
        if len(block) < 5:
            continue

        x0, y0, x1, y1, block_text = block[:5]

        if not block_text:
            continue

        normalized_block = normalize_text(block_text).lower()

        if normalized_source in normalized_block:
            return [
                fitz.Rect(
                    x0 - 3,
                    y0 - 3,
                    x1 + 3,
                    y1 + 3,
                )
            ]

    source_words = normalized_source.split()

    for phrase_length in [20, 16, 12, 10, 8, 6]:
        if len(source_words) < phrase_length:
            continue

        phrase = " ".join(source_words[:phrase_length])

        if len(phrase) < 25:
            continue

        for block in blocks:
            if len(block) < 5:
                continue

            x0, y0, x1, y1, block_text = block[:5]

            if not block_text:
                continue

            normalized_block = normalize_text(block_text).lower()

            if phrase in normalized_block:
                return [
                    fitz.Rect(
                        x0 - 3,
                        y0 - 3,
                        x1 + 3,
                        y1 + 3,
                    )
                ]

    return []


def find_word_rectangles(page, source_text: str):
    normalized_source = normalize_text(source_text).lower()

    if len(normalized_source) < 10:
        return []

    words = get_pdf_words(page)

    if not words:
        return []

    joined_text = " ".join(
        word["text"]
        for word in words
    ).lower()

    start_index = joined_text.find(normalized_source)

    if start_index == -1:
        return []

    end_index = start_index + len(normalized_source)

    boundaries = []
    cursor = 0

    for word in words:
        word_text = word["text"]

        word_start = cursor
        word_end = cursor + len(word_text)

        boundaries.append(
            (
                word_start,
                word_end,
                word,
            )
        )

        cursor = word_end + 1

    rectangles = []

    for word_start, word_end, word in boundaries:
        if word_end <= start_index:
            continue

        if word_start >= end_index:
            continue

        rectangles.append(
            fitz.Rect(
                word["x0"],
                word["y0"],
                word["x1"],
                word["y1"],
            )
        )

    return rectangles


def find_partial_rectangles(page, source_text: str):
    normalized_source = normalize_text(source_text)

    if not normalized_source:
        return []

    words = normalized_source.split()

    if len(words) < 5:
        return []

    for phrase_length in [18, 14, 12, 10, 8, 6]:
        phrase = " ".join(words[:phrase_length])

        if len(phrase) < 20:
            continue

        rectangles = page.search_for(
            phrase,
            quads=False,
        )

        if rectangles:
            return rectangles

    return []


def find_source_rectangles(page, source_text: str):
    if not source_text:
        return []

    rectangles = find_paragraph_rectangles(
        page=page,
        source_text=source_text,
    )

    if rectangles:
        return rectangles

    rectangles = find_word_rectangles(
        page=page,
        source_text=source_text,
    )

    if rectangles:
        return rectangles

    return find_partial_rectangles(
        page=page,
        source_text=source_text,
    )


# ============================================================
# PDF RENDERING
# ============================================================

def render_pdf_page(
    pdf_bytes: bytes,
    page_number: int,
    highlight_text: str = "",
):
    if not pdf_bytes:
        return None

    pdf_document = fitz.open(
        stream=pdf_bytes,
        filetype="pdf",
    )

    try:
        total_pages = len(pdf_document)

        if total_pages == 0:
            return None

        page_number = max(
            1,
            min(page_number, total_pages),
        )

        page = pdf_document[page_number - 1]

        if highlight_text:
            rectangles = find_source_rectangles(
                page=page,
                source_text=highlight_text,
            )

            for rectangle in rectangles:
                page.draw_rect(
                    rectangle,
                    color=(0.1, 0.55, 1.0),
                    fill=(0.2, 0.65, 1.0),
                    width=1,
                    fill_opacity=0.28,
                    overlay=True,
                )

        zoom = 1.45
        matrix = fitz.Matrix(zoom, zoom)

        pixmap = page.get_pixmap(
            matrix=matrix,
            alpha=False,
        )

        return pixmap.tobytes("png")

    finally:
        pdf_document.close()


# ============================================================
# SOURCE NAVIGATION
# ============================================================

def open_source(source: dict):
    page_number = source.get("page")

    if page_number is None:
        page_number = source.get("page_number")

    if page_number is None:
        return

    try:
        page_number = int(page_number)
    except (TypeError, ValueError):
        return

    st.session_state.pending_page = page_number

    st.session_state.highlight_text = (
        source.get("exact_text")
        or source.get("text")
        or source.get("preview")
        or ""
    )


def clear_highlight():
    st.session_state.highlight_text = ""


# ============================================================
# SOURCE RENDERER
# ============================================================

def render_sources(
    sources: list[dict],
    message_id: int,
):
    if not sources:
        return

    st.markdown(
        '<div class="source-label">📌 DOCUMENT SOURCES</div>',
        unsafe_allow_html=True,
    )

    for source_index, source in enumerate(sources):
        page_number = source.get("page")

        if page_number is None:
            page_number = source.get("page_number")

        if page_number is None:
            continue

        source_key = (
            f"source_{message_id}_"
            f"{source.get('chunk_id', source_index)}_"
            f"{source_index}"
        )

        if st.button(
            f"Open source · Page {page_number}",
            key=source_key,
            use_container_width=True,
        ):
            open_source(source)
            st.rerun()

        preview = source.get("preview", "")

        if preview:
            st.markdown(
                f'<div class="source-preview">{preview}</div>',
                unsafe_allow_html=True,
            )


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="brand-mark">📘</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="main-title">DocuMind AI</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="subtitle">Understand your documents with intelligent AI-powered conversations.</div>',
    unsafe_allow_html=True,
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.markdown("## 📁 Workspace")
    st.caption("Upload a document to start your AI session.")

    uploaded_file = st.file_uploader(
        "Choose PDF or DOCX",
        type=["pdf", "docx"],
        key=f"file_uploader_{st.session_state.upload_key}",
    )

    if uploaded_file:
        st.markdown(
            f"**Selected file:** `{uploaded_file.name}`"
        )

        if st.button(
            "Upload and Process",
            use_container_width=True,
        ):
            with st.spinner("Processing your document..."):
                try:
                    file_bytes = uploaded_file.getvalue()

                    response = requests.post(
                        f"{BACKEND_URL}/api/upload",
                        files={
                            "file": (
                                uploaded_file.name,
                                file_bytes,
                                uploaded_file.type,
                            )
                        },
                        timeout=180,
                    )

                    response.raise_for_status()
                    data = response.json()

                    st.session_state.document_id = data.get(
                        "document_id"
                    )

                    st.session_state.filename = data.get(
                        "filename",
                        uploaded_file.name,
                    )

                    st.session_state.messages = []
                    st.session_state.current_page = 1
                    st.session_state.page_input = 1
                    st.session_state.pending_page = None
                    st.session_state.highlight_text = ""

                    st.session_state.total_pages = data.get(
                        "total_pages",
                        0,
                    )

                    st.session_state.total_chunks = data.get(
                        "total_chunks",
                        0,
                    )

                    if uploaded_file.name.lower().endswith(".pdf"):
                        st.session_state.pdf_bytes = file_bytes
                    else:
                        st.session_state.pdf_bytes = None

                    st.success("Document processed successfully.")
                    st.rerun()

                except requests.exceptions.RequestException as error:
                    st.error(f"Upload failed: {error}")

    if st.session_state.document_id:
        st.divider()

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
            "Clear Chat",
            use_container_width=True,
        ):
            st.session_state.messages = []
            st.session_state.highlight_text = ""
            st.session_state.pending_page = None
            st.rerun()

        if st.button(
            "Reset Workspace",
            use_container_width=True,
        ):
            st.session_state.document_id = None
            st.session_state.filename = None
            st.session_state.pdf_bytes = None
            st.session_state.messages = []
            st.session_state.current_page = 1
            st.session_state.page_input = 1
            st.session_state.highlight_text = ""
            st.session_state.pending_page = None
            st.session_state.total_pages = 0
            st.session_state.total_chunks = 0
            st.session_state.upload_key += 1
            st.rerun()

    st.divider()

    st.caption("DocuMind AI")
    st.caption("Powered by Groq + FastAPI")


# ============================================================
# MAIN LAYOUT
# ============================================================

left_column, right_column = st.columns(
    [1.08, 0.92],
    gap="large",
)


# ============================================================
# LEFT PANEL - DOCUMENT VIEWER
# ============================================================

with left_column:
    st.markdown(
        '<div class="section-title">📄 Document Viewer</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="section-subtitle">Read, navigate and inspect source references.</div>',
        unsafe_allow_html=True,
    )

    with st.container(
        height=760,
        border=True,
    ):
        if st.session_state.pdf_bytes:
            pdf_document = fitz.open(
                stream=st.session_state.pdf_bytes,
                filetype="pdf",
            )

            total_pages = len(pdf_document)
            pdf_document.close()

            if st.session_state.pending_page is not None:
                requested_page = st.session_state.pending_page

                requested_page = max(
                    1,
                    min(requested_page, total_pages),
                )

                st.session_state.current_page = requested_page
                st.session_state.page_input = requested_page
                st.session_state.pending_page = None

            page_col, action_col = st.columns(
                [1.2, 1],
            )

            with page_col:
                selected_page = st.number_input(
                    "Page",
                    min_value=1,
                    max_value=total_pages,
                    step=1,
                    key="page_input",
                )

                st.session_state.current_page = int(
                    selected_page
                )

            with action_col:
                st.write("")

                if st.session_state.highlight_text:
                    if st.button(
                        "Clear highlight",
                        use_container_width=True,
                    ):
                        clear_highlight()
                        st.rerun()

            page_image = render_pdf_page(
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
                st.caption(
                    f"Source highlighted on page "
                    f"{st.session_state.current_page}"
                )

        elif st.session_state.filename:
            st.markdown(
                """
                <div class="empty-state">
                    <div class="empty-icon">📄</div>
                    <div class="empty-title">Document uploaded</div>
                    <div class="empty-text">
                        This file is ready for chat.<br>
                        PDF preview is available for PDF files.
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
                        Upload a PDF or DOCX from the sidebar<br>
                        to start reading and asking questions.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ============================================================
# RIGHT PANEL - AI CHAT
# ============================================================

with right_column:
    st.markdown(
        '<div class="section-title">🤖 AI Assistant</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="section-subtitle">Ask questions, generate summaries and explore your document.</div>',
        unsafe_allow_html=True,
    )

    with st.container(
        height=760,
        border=True,
    ):
        if not st.session_state.document_id:
            st.markdown(
                """
                <div class="empty-state">
                    <div class="empty-icon">✨</div>
                    <div class="empty-title">Start a conversation</div>
                    <div class="empty-text">
                        Upload your document and ask anything about it.<br>
                        Try: "Please give me the summary of this document."
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        else:
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

                    render_sources(
                        sources=message.get("sources", []),
                        message_id=message["id"],
                    )

    question = st.chat_input(
        "Ask about your document...",
        disabled=not bool(
            st.session_state.document_id
        ),
    )

    if question:
        user_message_id = len(
            st.session_state.messages
        )

        st.session_state.messages.append(
            {
                "id": user_message_id,
                "role": "user",
                "content": question,
            }
        )

        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("Analyzing your document..."):
                try:
                    response = requests.post(
                        f"{BACKEND_URL}/api/chat",
                        json={
                            "document_id": st.session_state.document_id,
                            "question": question,
                        },
                        timeout=240,
                    )

                    response.raise_for_status()
                    data = response.json()

                    answer = data.get(
                        "answer",
                        "No answer received.",
                    )

                    sources = data.get(
                        "sources",
                        [],
                    )

                    st.markdown(answer)

                    render_sources(
                        sources=sources,
                        message_id=user_message_id + 1,
                    )

                    st.session_state.messages.append(
                        {
                            "id": user_message_id + 1,
                            "role": "assistant",
                            "content": answer,
                            "sources": sources,
                        }
                    )

                except requests.exceptions.RequestException as error:
                    error_message = f"Chat request failed: {error}"

                    st.error(error_message)

                    st.session_state.messages.append(
                        {
                            "id": user_message_id + 1,
                            "role": "assistant",
                            "content": error_message,
                            "sources": [],
                        }
                    )

                except Exception as error:
                    error_message = f"Unexpected error: {error}"

                    st.error(error_message)

                    st.session_state.messages.append(
                        {
                            "id": user_message_id + 1,
                            "role": "assistant",
                            "content": error_message,
                            "sources": [],
                        }
                    )

        st.rerun()