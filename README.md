# DocuMind AI

DocuMind AI is an advanced AI-powered document intelligence and question-answering application supporting **PDF**, **DOCX**, and **Image (PNG, JPG, JPEG, WEBP)** workflows. Users can upload single or multiple documents, inspect them with an interactive preview viewer, and ask natural language questions to receive grounded answers with precise source references.

DocuMind AI uses a **FastAPI** backend for ingestion, OCR, chunking, and retrieval, and a **Streamlit** frontend for an intuitive UI. LLM completions and document Q&A are powered exclusively by **xAI Grok Cloud API** (`openai/gpt-oss-120b`) via the OpenAI-compatible Python client.

---

## Key Features

- **Multi-Format Document Upload**:
  - PDF documents (`.pdf`) with page-by-page text extraction and PyMuPDF preview.
  - Word documents (`.docx`) with structured paragraph and table extraction.
  - Image files (`.png`, `.jpg`, `.jpeg`, `.webp`) with Tesseract OCR text extraction.
  - Multi-document upload support with batch processing and duplicate prevention (HTTP 409).
- **Intelligent Optical Character Recognition (OCR)**:
  - Automatic preprocessing: bounded aspect-ratio resizing, grayscale conversion, contrast enhancement, and sharpening.
  - Robust multi-path Tesseract binary detection on Windows (`TESSERACT_CMD` environment variable, system `PATH`, `C:\Program Files\Tesseract-OCR\tesseract.exe`, `C:\Program Files (x86)\Tesseract-OCR\tesseract.exe`, and LocalAppData).
  - Clear, user-friendly setup guidance when Tesseract is not installed (prevents backend crashes).
- **Grounded Document Question-Answering**:
  - Powered by **xAI Grok Cloud API** (`https://api.x.ai/v1`) using model `openai/gpt-oss-120b`.
  - Single-document and multi-document synthesis modes.
  - Strict grounding: answers cite document text and return transparent fallback notices when information is absent.
  - Full source attribution including document filename, page number, and preview snippet.
- **Interactive Streamlit Frontend**:
  - File uploader supporting PDF, DOCX, PNG, JPG, JPEG, WEBP.
  - Sidebar document manager displaying file type badges (`PDF`, `DOCX`, `IMAGE`), active document selection, and deletion.
  - Document Viewer: PyMuPDF PDF rendering, high-resolution Image preview, and DOCX text status messages.
  - PDF text highlight synchronization upon clicking source citations.
  - Conversational Q&A chat stream with source cards and citation navigation.

---

## Tech Stack

- **Backend**:
  - FastAPI & Uvicorn (REST API)
  - PyMuPDF (`fitz`) (PDF processing and rendering)
  - `python-docx` (Word processing)
  - Pillow (`PIL`) (Image processing and enhancement)
  - `pytesseract` & Google Tesseract OCR (Optical Character Recognition)
  - OpenAI Python Client (configured for xAI Grok Cloud API)
  - `python-dotenv` (Environment configuration)
  - `pytest` & `pytest-asyncio` (Automated testing)
- **Frontend**:
  - Streamlit (Web UI)
  - Requests (API communication)
- **LLM Provider**:
  - xAI Grok Cloud API (`https://api.x.ai/v1`)
  - Model: `openai/gpt-oss-120b`

---

## Supported File Formats

| Format | Extension | Text Extraction Engine | Frontend Viewer | Source Citations |
| :--- | :--- | :--- | :--- | :--- |
| **PDF** | `.pdf` | PyMuPDF (`fitz`) | Embedded page canvas with search highlights | Page-level citations with highlight jump |
| **Word** | `.docx` | `python-docx` | Informational status view | Paragraph / section citations |
| **Image** | `.png`, `.jpg`, `.jpeg`, `.webp` | Tesseract OCR via `pytesseract` | High-resolution image preview | Image / page citations with OCR snippets |

---

## Project Structure

```text
DocuMind AI/
├── backend/
│   ├── app/
│   │   ├── config.py             # Environment configuration (xAI credentials & model)
│   │   ├── models/               # Pydantic schemas (chat, documents)
│   │   ├── rag/                  # Retrieval-augmented generation components
│   │   ├── routes/
│   │   │   ├── chat.py           # /api/chat endpoints (single & multi-doc)
│   │   │   └── upload.py         # /api/upload, /api/documents endpoints
│   │   ├── services/
│   │   │   ├── chat_service.py   # xAI Grok client & answer generation logic
│   │   │   ├── document_service.py # Ingestion for PDF, DOCX, and Images
│   │   │   ├── ocr_service.py    # Tesseract configuration & image OCR
│   │   │   └── retrieval_service.py # Vector/keyword chunk retrieval
│   │   └── utils/                # Helper functions (highlighting, text sanitization)
│   ├── data/
│   │   ├── chroma/               # Local vector database storage
│   │   ├── documents/            # Extracted document text & metadata
│   │   └── uploads/              # Uploaded source files
│   ├── .env                      # Local environment variables (XAI_API_KEY)
│   ├── .gitignore                # Git exclusions
│   ├── main.py                   # FastAPI application entry point
│   ├── requirements.txt          # Backend Python dependencies
│   └── test_*.py                 # Verification and test suites
├── frontend/
│   └── app.py                    # Streamlit user interface
├── .gitignore
├── LICENSE
└── README.md
```

---

## Prerequisites & Installation

### 1. System Requirements

- **Operating System**: Windows 10/11, macOS, or Linux
- **Python**: Version 3.10, 3.11, or 3.12
- **xAI Grok API Key**: Required for AI answers (`XAI_API_KEY`)
- **Tesseract OCR**: Required for image text extraction

### 2. Installing Tesseract OCR (Windows)

To extract text from images (`.png`, `.jpg`, `.jpeg`, `.webp`), Tesseract OCR must be installed on your system:

1. **Download the Windows Installer**:
   - Download the latest 64-bit installer (`tesseract-ocr-w64-setup-*.exe`) from the official UB-Mannheim repository:  
     👉 [https://github.com/UB-Mannheim/tesseract/wiki](https://github.com/UB-Mannheim/tesseract/wiki)
2. **Run the Installer**:
   - Install to the default directory:
     ```text
     C:\Program Files\Tesseract-OCR
     ```
   - (Optional) Select additional language data packages if processing non-English documents.
3. **Add Tesseract to System PATH**:
   - Press <kbd>Win</kbd> + <kbd>R</kbd>, type `sysdm.cpl`, and press **Enter**.
   - Go to the **Advanced** tab and click **Environment Variables**.
   - Under **System variables**, select `Path` and click **Edit**.
   - Click **New** and add:
     ```text
     C:\Program Files\Tesseract-OCR
     ```
   - Click **OK** to save and apply.
4. **Verify Installation**:
   Open a new PowerShell terminal and run:
   ```powershell
   tesseract --version
   ```
   If Tesseract is installed in a non-standard directory, you can specify its path in `backend/.env`:
   ```env
   TESSERACT_CMD=C:\YourCustomPath\Tesseract-OCR\tesseract.exe
   ```

> **Note**: If Tesseract is not installed, the application will not crash. Uploading images will return a clear message explaining how to install Tesseract, and PDF / DOCX functionality will continue working seamlessly.

---

## Setup Guide

### 1. Clone the Repository

```powershell
git clone <your-repository-url>
cd "DocuMind AI"
```

### 2. Create and Activate a Virtual Environment

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
```

*(If PowerShell script execution is restricted, run: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`)*

### 3. Install Backend Dependencies

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Install Frontend Dependencies

```powershell
pip install streamlit requests
```

### 5. Configure Environment Variables

Create or edit `backend/.env`:

```env
# =====================================================================
# DocuMind AI Environment Configuration
# =====================================================================

# xAI Grok Cloud API Key
XAI_API_KEY=gsk_your_actual_key_here

# LLM Model Name (Do NOT change unless specifying an xAI-supported model)
LLM_MODEL=openai/gpt-oss-120b

# xAI Base URL (OpenAI-compatible endpoint)
XAI_BASE_URL=https://api.x.ai/v1

# Optional: Explicit Tesseract Binary Path (if not in standard location or PATH)
# TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

> **Security Warning**: Never commit your `.env` file or expose your API keys in source control. The `.gitignore` file is configured to exclude `backend/.env` and all uploaded files.

---

## Running the Application

### 1. Start the FastAPI Backend

From the `backend/` directory:

```powershell
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The backend server will start at: `http://127.0.0.1:8000`  
Interactive Swagger API documentation: `http://127.0.0.1:8000/docs`

### 2. Start the Streamlit Frontend

In a separate terminal, from the project root:

```powershell
streamlit run frontend/app.py
```

The frontend application will open in your browser at: `http://localhost:8501`

---

## API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Service health status check |
| `GET` | `/` | Root endpoint returning backend status |
| `POST` | `/api/upload` | Upload one or multiple files (`.pdf`, `.docx`, `.png`, `.jpg`, `.jpeg`, `.webp`) |
| `GET` | `/api/documents` | List all processed documents with metadata |
| `GET` | `/api/documents/{document_id}` | Retrieve metadata and page count for a specific document |
| `GET` | `/api/documents/{document_id}/file` | Stream raw document file content (PDF, image, or DOCX) |
| `DELETE` | `/api/documents/{document_id}` | Delete a document, its extracted text, and its source file |
| `POST` | `/api/chat` | Ask a question against a single active document or all uploaded documents |

### Example Chat Request

```http
POST /api/chat
Content-Type: application/json

{
  "document_id": "receipt_ocr_12345",
  "question": "What is the total amount due shown in this invoice?"
}
```

### Example Chat Response

```json
{
  "answer": "The total amount due shown on the invoice is $1,250.00, due by October 31, 2026.",
  "document_id": "receipt_ocr_12345",
  "question": "What is the total amount due shown in this invoice?",
  "sources": [
    {
      "document_id": "receipt_ocr_12345",
      "document_title": "receipt_ocr_12345.png",
      "page": 1,
      "preview": "INVOICE #9821 ... Total Amount Due: $1,250.00 Due Date: 10/31/2026"
    }
  ]
}
```

---

## Testing & Verification

Run automated test suites to verify backend functionality:

```powershell
# Run conversation management tests
pytest backend/test_conversation_management.py -v

# Run comprehensive end-to-end flow tests (PDF, DOCX, Image OCR, Q&A, Highlighting)
python backend/test_comprehensive_flows.py
```

---

## Troubleshooting

- **Tesseract Not Found Error**:
  - Ensure Tesseract OCR is installed from [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki).
  - Verify that `tesseract` runs in your terminal, or set `TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe` in `backend/.env`.
- **401 Unauthorized / Invalid API Key**:
  - Verify that `XAI_API_KEY` in `backend/.env` is set to a valid xAI Grok API key.
  - Verify that `LLM_MODEL=openai/gpt-oss-120b`.
- **Duplicate Document Upload (HTTP 409)**:
  - If a file with identical content or filename has already been uploaded, DocuMind AI prevents duplicate ingestion. Select the existing document from the sidebar.

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
