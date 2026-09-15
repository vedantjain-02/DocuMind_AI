# DocuMind AI

DocuMind AI is an AI-powered document chatbot built for PDF and DOCX workflows. Users can upload a document, ask questions in natural language, and receive grounded answers with source page references. The application combines a FastAPI backend with a Streamlit frontend to deliver an interactive document Q&A experience.

## Features

- Upload PDF and DOCX files
- Extract and process document text
- Ask questions about the uploaded document
- Generate AI-powered answers grounded in the document content
- View source page references for answers
- Click source references to inspect relevant sections
- PDF preview support in the frontend
- Summary-style queries for document overview
- FastAPI API backend for document upload and chat
- Streamlit user interface
- Groq Cloud API integration for LLM responses

## Tech Stack

The project currently uses the following technologies based on the actual codebase:

- Python 3.12
- FastAPI
- Uvicorn
- Streamlit
- PyMuPDF (`fitz`)
- python-docx
- Pillow
- OpenAI Python client
- python-dotenv
- Requests
- pytest
- Groq Cloud API (OpenAI-compatible endpoint)

## Project Structure

```text
DocuMind AI/
├── backend/
│   ├── app/
│   │   ├── config.py
│   │   ├── models/
│   │   ├── rag/
│   │   ├── routes/
│   │   │   ├── chat.py
│   │   │   └── upload.py
│   │   ├── services/
│   │   │   ├── chat_service.py
│   │   │   ├── document_service.py
│   │   │   └── retrieval_service.py
│   │   └── utils/
│   ├── data/
│   │   ├── chroma/
│   │   ├── documents/
│   │   └── uploads/
│   ├── .env
│   ├── .gitignore
│   ├── main.py
│   ├── test_all_six_questions.py
│   ├── test_api_chat.py
│   ├── test_grok.py
│   ├── test_summary_flow.py
│   └── venv/
├── frontend/
│   └── app.py
├── .gitignore
├── LICENSE
└── README.md
```

> Note: Generated data folders such as uploads, documents, and local virtual environment folders are not intended for public commit content.

## Getting Started

### Prerequisites

- Windows 10 or later
- Python 3.10+
- Git
- Access to a Groq Cloud API key

### 1. Clone the repository

```powershell
git clone <your-repository-url>
cd DocuMind-AI
```

### 2. Create a virtual environment

From the project root or backend folder, create a local virtual environment:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
```

If you are using PowerShell and execution policy blocks activation, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

### 3. Install backend dependencies

The repository currently does not contain a root-level `requirements.txt`, so install the packages used by the app directly:

```powershell
pip install fastapi uvicorn python-dotenv openai pymupdf python-docx pillow python-multipart requests pytest pytest-asyncio
```

### 4. Install frontend dependencies

The frontend uses Streamlit and Requests:

```powershell
pip install streamlit requests
```

If you prefer to keep the app in the same virtual environment, you can install both backend and frontend dependencies in the activated environment.

## Environment Variables

Create a file named `.env` inside the `backend` folder and add the required API key:

```env
GROQ_API_KEY=your_groq_api_key_here
XAI_API_KEY=
```

### Important Notes

- Do not commit real API keys to GitHub.
- The project reads `GROQ_API_KEY` from `backend/.env`.
- `XAI_API_KEY` is also supported in the configuration file but is not required for the current app flow.

## Run the Application

### Start the FastAPI backend

From the `backend` directory:

```powershell
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The backend will run at:

```text
http://127.0.0.1:8000
```

### Start the Streamlit frontend

From the project root or frontend folder:

```powershell
cd frontend
streamlit run app.py
```

The frontend will run at:

```text
http://localhost:8501
```

## Usage

1. Start the backend.
2. Start the frontend.
3. Upload a PDF or DOCX file from the sidebar.
4. Wait for the document to be processed.
5. Ask questions like:
   - "Summarize this document"
   - "What is the main topic of this PDF?"
   - "Explain the uploaded document"
6. Review the generated answer and source references.
7. Click source entries to inspect relevant document sections.

## API Endpoints

The backend exposes the following routes:

### Health Check

```http
GET /health
```

Returns application health status.

### Root

```http
GET /
```

Returns a simple backend status response.

### Upload Document

```http
POST /api/upload
```

Accepts a PDF or DOCX upload and returns a `document_id` plus metadata.

### Chat with Document

```http
POST /api/chat
```

Request body:

```json
{
  "document_id": "<document-id>",
  "question": "What is this document about?"
}
```

Response includes:

- `answer`
- `document_id`
- `question`
- `sources`

## Future Improvements

- Add stronger PDF and DOCX extraction cleanup for edge-case documents
- Improve retrieved source highlighting and page navigation
- Add user authentication and session management
- Support more file formats and OCR fallback improvements
- Add document history and saved chat sessions
- Improve summarization quality and source validation
- Add deployment support for cloud hosting

## Author

- Author: Vedant Jain
- Copyright: 2026

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Disclaimer

This project uses a Groq Cloud API key for AI-powered document analysis. Keep your API credentials private and do not commit them to version control.
