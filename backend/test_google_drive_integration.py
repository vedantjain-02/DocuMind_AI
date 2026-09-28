import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from main import app
from app.services.google_drive_mcp_client import (
    GoogleDriveMCPClient,
    MCPAuthenticationError,
    MCPConnectionError,
    MCPDownloadError,
    MCPError,
    get_google_drive_mcp_client,
)
from app.routes.google_drive import (
    DOCUMENT_DIR,
    UPLOAD_DIR,
    find_document_by_drive_file_id,
)

client = TestClient(app)


# ============================================================================
# 1. MCP CLIENT PARSING & SECURITY UNIT TESTS
# ============================================================================

def test_mcp_client_parse_file_list_text():
    """Verify that file list lines from search tool are parsed accurately with metadata."""
    mcp_client = GoogleDriveMCPClient()

    sample_output = """
Found 3 files (ordered by modifiedTime desc):
Annual_Report_2026.pdf (application/pdf) [id: gdrive_file_101, path: Reports] [created: 2026-01-10T10:00:00Z, modified: 2026-01-15T12:00:00Z] [size: 245000 bytes]
Meeting_Notes (application/vnd.google-apps.document) [id: gdrive_file_102, path: /] [created: 2026-02-01T08:00:00Z, modified: 2026-02-02T09:30:00Z]
Project_Spec.docx (application/vnd.openxmlformats-officedocument.wordprocessingml.document) [id: gdrive_file_103, path: Docs] [created: 2026-03-01T14:00:00Z, modified: 2026-03-05T16:00:00Z] [size: 51200 bytes]
Archived_Folder (application/vnd.google-apps.folder) [id: folder_999, path: /]
Unsupported_Audio.mp3 (audio/mp3) [id: gdrive_file_104, path: Music] [size: 1048576 bytes]

More results available. Use pageToken: next_token_abc123
"""
    files, next_token = mcp_client._parse_file_list_text(sample_output)

    assert next_token == "next_token_abc123"
    assert len(files) == 4  # Folders excluded

    # File 1: PDF
    pdf_file = next(f for f in files if f["id"] == "gdrive_file_101")
    assert pdf_file["name"] == "Annual_Report_2026.pdf"
    assert pdf_file["is_supported"] is True
    assert pdf_file["file_type"] == "pdf"
    assert "245000" in pdf_file["size"]

    # File 2: Google Doc
    gdoc_file = next(f for f in files if f["id"] == "gdrive_file_102")
    assert gdoc_file["name"] == "Meeting_Notes"
    assert gdoc_file["is_supported"] is True
    assert gdoc_file["is_gdoc"] is True
    assert gdoc_file["file_type"] == "gdoc"

    # File 3: DOCX
    docx_file = next(f for f in files if f["id"] == "gdrive_file_103")
    assert docx_file["name"] == "Project_Spec.docx"
    assert docx_file["is_supported"] is True
    assert docx_file["file_type"] == "docx"

    # File 4: Unsupported
    audio_file = next(f for f in files if f["id"] == "gdrive_file_104")
    assert audio_file["name"] == "Unsupported_Audio.mp3"
    assert audio_file["is_supported"] is False


def test_mcp_client_check_status_does_not_expose_tokens():
    """Verify check_status parses user identity without leaking token secrets or paths."""
    mcp_client = GoogleDriveMCPClient()

    fake_auth_response = {
        "content": [
            {
                "type": "text",
                "text": json.dumps({
                    "authMode": "oauth",
                    "identity": {
                        "emailAddress": "user@example.com",
                        "displayName": "Test User",
                    },
                    "tokenFilePath": "C:\\Secret\\path\\tokens.json",
                    "hasAccessToken": True,
                    "hasRefreshToken": True,
                    "accessToken": "ya29.secret_access_token_should_not_leak",
                    "refreshToken": "1//secret_refresh_token_should_not_leak",
                }),
            }
        ]
    }

    with patch.object(mcp_client, "call_tool", return_value=fake_auth_response):
        status = mcp_client.check_status()

    assert status["connected"] is True
    assert status["authenticated"] is True
    assert status["identity"] == "user@example.com"
    # Ensure no tokens or secret paths exist anywhere in the status dict
    status_str = json.dumps(status)
    assert "secret_access_token" not in status_str
    assert "secret_refresh_token" not in status_str
    assert "C:\\Secret" not in status_str


# ============================================================================
# 2. FASTAPI ENDPOINT TESTS: GET /api/drive/status
# ============================================================================

def test_get_drive_status_endpoint():
    """Test GET /api/drive/status endpoint."""
    response = client.get("/api/drive/status")
    assert response.status_code == 200
    data = response.json()
    assert "connected" in data
    assert "authenticated" in data
    assert "message" in data


# ============================================================================
# 3. FASTAPI ENDPOINT TESTS: GET /api/drive/files
# ============================================================================

def test_list_drive_files_endpoint_with_mock():
    """Test GET /api/drive/files with duplicate annotation."""
    fake_files = [
        {
            "id": "mock_file_id_001",
            "name": "sample_gdrive_doc.pdf",
            "mime_type": "application/pdf",
            "file_type": "pdf",
            "path": "/",
            "created": "2026-01-01",
            "modified": "2026-01-02",
            "size": "1000",
            "is_supported": True,
            "is_gdoc": False,
        }
    ]

    mock_client = get_google_drive_mcp_client()
    with patch.object(mock_client, "list_files", return_value={"files": fake_files, "next_page_token": None}):
        response = client.get("/api/drive/files")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["files"][0]["id"] == "mock_file_id_001"
        assert data["files"][0]["name"] == "sample_gdrive_doc.pdf"
        assert data["files"][0]["is_supported"] is True
        assert data["files"][0]["is_imported"] is False


# ============================================================================
# 4. FASTAPI ENDPOINT TESTS: POST /api/drive/import & DUPLICATE PREVENTION
# ============================================================================

def test_import_drive_file_pipeline_and_duplicate_prevention(tmp_path):
    """
    Comprehensive test of the Google Drive import pipeline:
    1. Downloads file via MCP mock
    2. Feeds through extract_document and chunking
    3. Saves metadata to DOCUMENT_DIR
    4. Re-importing same file ID returns duplicate without re-extraction
    5. Works with chat endpoint and returns grounded sources
    """
    import fitz  # PyMuPDF

    test_drive_file_id = f"test_drive_id_{uuid4().hex[:8]}"
    test_filename = f"sample_drive_policy_{uuid4().hex[:4]}.pdf"

    # Create a real test PDF file
    doc = fitz.open()
    page1 = doc.new_page()
    page1.insert_text(
        (50, 72),
        "Company Security Policy Document.\n\nAll employees must enable multi-factor authentication (MFA) on their accounts.",
    )
    page2 = doc.new_page()
    page2.insert_text(
        (50, 72),
        "Data Retention Guidelines.\n\nFinancial records must be retained for seven years under compliance regulations.",
    )
    pdf_bytes = doc.write()
    doc.close()

    mock_client = get_google_drive_mcp_client()

    def fake_download(file_id, target_path, export_mime_type=None):
        target_path.write_bytes(pdf_bytes)
        return target_path

    with patch.object(mock_client, "download_file", side_effect=fake_download):
        # 1. First import
        res1 = client.post(
            "/api/drive/import",
            json={
                "file_id": test_drive_file_id,
                "filename": test_filename,
                "mime_type": "application/pdf",
            },
        )
        assert res1.status_code == 200, res1.text
        data1 = res1.json()
        assert data1["upload_status"] == "processed"
        assert data1["is_duplicate"] is False
        assert data1["google_drive_file_id"] == test_drive_file_id
        assert data1["total_pages"] == 2
        assert data1["total_chunks"] >= 2
        document_id = data1["document_id"]

        # Verify document JSON was written and contains Google Drive metadata
        doc_json_file = DOCUMENT_DIR / f"{document_id}.json"
        assert doc_json_file.exists()
        saved_data = json.loads(doc_json_file.read_text(encoding="utf-8"))
        assert saved_data["google_drive_file_id"] == test_drive_file_id
        assert saved_data["source_type"] == "google_drive"
        assert saved_data["filename"] == test_filename
        assert all(c.get("google_drive_file_id") == test_drive_file_id for c in saved_data["chunks"])

        # 2. Second import of the SAME file ID (duplicate prevention)
        res2 = client.post(
            "/api/drive/import",
            json={
                "file_id": test_drive_file_id,
                "filename": test_filename,
                "mime_type": "application/pdf",
            },
        )
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["is_duplicate"] is True
        assert data2["document_id"] == document_id
        assert "already in workspace" in data2["message"].lower()

        # 3. Verify it is visible in GET /api/documents with Drive metadata
        list_res = client.get("/api/documents")
        assert list_res.status_code == 200
        workspace_docs = list_res.json()
        matching = [d for d in workspace_docs if d["document_id"] == document_id]
        assert len(matching) == 1
        assert matching[0]["google_drive_file_id"] == test_drive_file_id
        assert matching[0]["source_type"] == "google_drive"

        # 4. Verify file retrieval via /api/documents/{document_id}/file
        file_res = client.get(f"/api/documents/{document_id}/file")
        assert file_res.status_code == 200
        assert len(file_res.content) == len(pdf_bytes)

        # 5. Clean up test document
        client.delete(f"/api/documents/{document_id}")
        assert not doc_json_file.exists()


def test_import_unsupported_file_type_rejected():
    """Verify that unsupported file formats are cleanly rejected with HTTP 400."""
    response = client.post(
        "/api/drive/import",
        json={
            "file_id": "file_video_123",
            "filename": "meeting_recording.mp4",
            "mime_type": "video/mp4",
        },
    )
    assert response.status_code == 400
    assert "unsupported file type" in response.json()["detail"].lower()


# ============================================================================
# 5. REGRESSION: LOCAL UPLOAD CONTINUES WORKING UNCHANGED
# ============================================================================

def test_local_upload_regression():
    """Verify that local PDF upload continues working exactly as before."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), "Local upload regression test document content.")
    pdf_bytes = doc.write()
    doc.close()

    local_filename = f"local_test_{uuid4().hex[:6]}.pdf"

    response = client.post(
        "/api/upload",
        files={"files": (local_filename, pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    document_id = data.get("document_id") or data.get("documents", [{}])[0].get("document_id")
    assert document_id

    # Verify document has source_type local
    doc_file = DOCUMENT_DIR / f"{document_id}.json"
    assert doc_file.exists()
    doc_json = json.loads(doc_file.read_text(encoding="utf-8"))
    assert doc_json.get("source_type") == "local"

    # Cleanup
    client.delete(f"/api/documents/{document_id}")


# ============================================================================
# 6. RAG CHAT & SOURCE CITATION WITH GOOGLE DRIVE DOCUMENT
# ============================================================================

def test_rag_chat_with_imported_drive_document():
    """
    Verify complete flow:
    Drive Document Import -> RAG Retrieval -> Chat Answer -> Source Citation with Drive File ID & Page.
    """
    import fitz

    drive_file_id = f"gdrive_policy_{uuid4().hex[:8]}"
    filename = f"cybersecurity_guide_{uuid4().hex[:4]}.pdf"

    # Create a 2-page test PDF with distinct policy text
    doc = fitz.open()
    page1 = doc.new_page()
    page1.insert_text(
        (50, 72),
        "Cybersecurity Policy Overview.\n\nAll staff must undergo phishing awareness training every quarter.",
    )
    page2 = doc.new_page()
    page2.insert_text(
        (50, 72),
        "Password Complexity Requirements.\n\nPasswords must be at least sixteen characters in length and include symbols.",
    )
    pdf_bytes = doc.write()
    doc.close()

    mock_client = get_google_drive_mcp_client()

    def fake_download(file_id, target_path, export_mime_type=None):
        target_path.write_bytes(pdf_bytes)
        return target_path

    with patch.object(mock_client, "download_file", side_effect=fake_download):
        import_res = client.post(
            "/api/drive/import",
            json={
                "file_id": drive_file_id,
                "filename": filename,
                "mime_type": "application/pdf",
            },
        )
        assert import_res.status_code == 200
        doc_id = import_res.json()["document_id"]

    try:
        # Mock LLM generation to return structured JSON answer
        with patch("app.services.chat_service._ask_for_answer", return_value="All staff must undergo phishing awareness training every quarter."):
            chat_res = client.post(
                "/api/chat",
                json={
                    "document_id": doc_id,
                    "document_ids": [doc_id],
                    "question": "How often must staff undergo phishing awareness training?",
                },
            )
            assert chat_res.status_code == 200, chat_res.text
            chat_data = chat_res.json()

            # Verify answer
            assert "phishing awareness training" in chat_data["answer"].lower()

            # Verify sources citation
            assert len(chat_data["sources"]) > 0
            primary_source = chat_data["sources"][0]
            assert primary_source["document_id"] == doc_id
            assert primary_source["filename"] == filename
            assert primary_source["page"] == 1
            assert primary_source["google_drive_file_id"] == drive_file_id
            assert primary_source["source_type"] == "google_drive"
            assert "phishing awareness" in (primary_source["text"] or primary_source["exact_text"]).lower()

    finally:
        client.delete(f"/api/documents/{doc_id}")


# ============================================================================
# 7. IMAGE IMPORT PRESERVES OCR BOUNDING BOX METADATA
# ============================================================================

def test_import_drive_image_preserves_ocr_metadata():
    """
    Verify that images imported from Google Drive preserve image dimensions and OCR metadata
    so that frontend image source highlighting continues to work.
    """
    from PIL import Image, ImageDraw
    from io import BytesIO

    drive_file_id = f"gdrive_img_{uuid4().hex[:8]}"
    filename = f"scanned_receipt_{uuid4().hex[:4]}.png"

    # Create a small valid test PNG image
    img = Image.new("RGB", (400, 200), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((20, 30), "INVOICE #98765 Total Due: $150.00", fill="black")

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    img_bytes = buffer.getvalue()

    mock_client = get_google_drive_mcp_client()

    def fake_download(file_id, target_path, export_mime_type=None):
        target_path.write_bytes(img_bytes)
        return target_path

    with patch.object(mock_client, "download_file", side_effect=fake_download):
        import_res = client.post(
            "/api/drive/import",
            json={
                "file_id": drive_file_id,
                "filename": filename,
                "mime_type": "image/png",
            },
        )
        assert import_res.status_code == 200
        doc_id = import_res.json()["document_id"]

    try:
        doc_file = DOCUMENT_DIR / f"{doc_id}.json"
        assert doc_file.exists()
        doc_data = json.loads(doc_file.read_text(encoding="utf-8"))

        assert doc_data["file_type"] == "png"
        assert doc_data["google_drive_file_id"] == drive_file_id
        assert doc_data["source_type"] == "google_drive"
        # Verify image dimensions are preserved
        assert doc_data.get("image_width") == 400
        assert doc_data.get("image_height") == 200
        assert "all_ocr_bboxes" in doc_data

        # Verify chunks contain image dimensions
        chunks = doc_data.get("chunks", [])
        if chunks:
            assert chunks[0].get("image_width") == 400
            assert chunks[0].get("image_height") == 200

    finally:
        client.delete(f"/api/documents/{doc_id}")

