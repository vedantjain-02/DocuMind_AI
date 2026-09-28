import json
import logging
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.document_service import extract_document
from app.services.google_drive_mcp_client import (
    GOOGLE_DOCS_MIME,
    IMAGE_EXTENSIONS,
    MIME_TYPE_EXTENSIONS,
    SUPPORTED_EXTENSIONS,
    MCPAuthenticationError,
    MCPConnectionError,
    MCPDownloadError,
    MCPError,
    get_google_drive_mcp_client,
)

logger = logging.getLogger("documind.google_drive")

router = APIRouter(
    prefix="/api/drive",
    tags=["Google Drive"],
)

BASE_DIR = Path(__file__).resolve().parents[2]
UPLOAD_DIR = BASE_DIR / "data" / "uploads"
DOCUMENT_DIR = BASE_DIR / "data" / "documents"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DOCUMENT_DIR.mkdir(parents=True, exist_ok=True)


class DriveStatusResponse(BaseModel):
    connected: bool
    authenticated: bool
    identity: str | None = None
    display_name: str | None = None
    message: str


class DriveFileItem(BaseModel):
    id: str
    name: str
    mime_type: str
    file_type: str
    path: str = ""
    created: str = ""
    modified: str = ""
    size: str = ""
    is_supported: bool
    is_gdoc: bool = False
    is_imported: bool = False
    imported_document_id: str | None = None


class DriveFileListResponse(BaseModel):
    files: list[DriveFileItem] = Field(default_factory=list)
    count: int = 0
    next_page_token: str | None = None


class DriveImportRequest(BaseModel):
    file_id: str
    filename: str
    mime_type: str = ""


class DriveImportResponse(BaseModel):
    document_id: str
    filename: str
    file_type: str
    message: str
    total_pages: int
    total_chunks: int
    upload_status: str = "processed"
    google_drive_file_id: str
    is_duplicate: bool = False


def find_document_by_drive_file_id(drive_file_id: str) -> dict | None:
    """Finds an existing workspace document by its Google Drive file ID."""
    if not drive_file_id:
        return None
    for path in DOCUMENT_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("google_drive_file_id") == drive_file_id:
                return data
        except Exception:
            continue
    return None


@router.get("/status", response_model=DriveStatusResponse)
async def get_drive_status():
    """
    Checks the status of the Google Drive MCP server and OAuth authentication.
    Does not expose private tokens or credentials.
    """
    client = get_google_drive_mcp_client()
    status = client.check_status()
    return DriveStatusResponse(**status)


@router.get("/files", response_model=DriveFileListResponse)
async def list_drive_files(
    query: str = Query("", description="Optional filename search term"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    page_token: str | None = Query(None, description="Pagination token"),
):
    """
    Lists files accessible in Google Drive using the MCP server.
    Enriches each item with format support and duplicate import detection.
    """
    client = get_google_drive_mcp_client()

    try:
        result = client.list_files(
            query=query,
            page_size=page_size,
            page_token=page_token,
        )
    except MCPConnectionError as err:
        logger.error("[GoogleDrive] Connection error listing files: %s", err)
        raise HTTPException(
            status_code=503,
            detail=f"Google Drive MCP server is unavailable: {str(err)}",
        )
    except MCPAuthenticationError as err:
        logger.warning("[GoogleDrive] Authentication error listing files: %s", err)
        raise HTTPException(
            status_code=401,
            detail=f"Google Drive authentication error: {str(err)}",
        )
    except MCPError as err:
        logger.error("[GoogleDrive] MCP error listing files: %s", err)
        raise HTTPException(
            status_code=502,
            detail=f"Google Drive error: {str(err)}",
        )
    except Exception as err:
        logger.exception("[GoogleDrive] Unexpected error listing files: %s", err)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list Google Drive files: {str(err)}",
        )

    # Annotate items with duplicate import status from DocuMind workspace
    enriched_files: list[DriveFileItem] = []
    for item in result.get("files", []):
        file_id = item.get("id")
        existing_doc = find_document_by_drive_file_id(file_id)

        item["is_imported"] = existing_doc is not None
        item["imported_document_id"] = (
            existing_doc.get("document_id") if existing_doc else None
        )
        enriched_files.append(DriveFileItem(**item))

    return DriveFileListResponse(
        files=enriched_files,
        count=len(enriched_files),
        next_page_token=result.get("next_page_token"),
    )


@router.post("/import", response_model=DriveImportResponse)
async def import_drive_file(request: DriveImportRequest):
    """
    Imports a Google Drive file into DocuMind AI.
    - Prevents duplicate imports using Google Drive file ID.
    - Downloads file via MCP downloadFile tool.
    - Ingests via existing document_service extraction, chunking, and metadata storage.
    - Makes it immediately available to the RAG chat and document viewer.
    """
    if not request.file_id or not request.file_id.strip():
        raise HTTPException(status_code=400, detail="Google Drive file ID is required.")

    file_id = request.file_id.strip()
    filename = (request.filename or "").strip() or f"Drive_Doc_{file_id[:8]}"
    mime_type = (request.mime_type or "").strip().lower()

    # 1. Duplicate detection: if already imported, return existing record immediately
    existing_doc = find_document_by_drive_file_id(file_id)
    if existing_doc:
        logger.info(
            "[GoogleDrive] File %s (%s) is already imported as %s",
            file_id,
            filename,
            existing_doc.get("document_id"),
        )
        return DriveImportResponse(
            document_id=existing_doc.get("document_id", ""),
            filename=existing_doc.get("filename", filename),
            file_type=existing_doc.get("file_type", "unknown"),
            message=f"Document '{existing_doc.get('filename', filename)}' is already in workspace.",
            total_pages=len(existing_doc.get("pages", [])),
            total_chunks=len(existing_doc.get("chunks", [])),
            upload_status="already_imported",
            google_drive_file_id=file_id,
            is_duplicate=True,
        )

    # 2. File type and format validation
    ext = Path(filename).suffix.lower()
    is_gdoc = mime_type == GOOGLE_DOCS_MIME
    export_mime_type: str | None = None

    if is_gdoc:
        ext = ".pdf"
        export_mime_type = "application/pdf"
        if not filename.lower().endswith(".pdf"):
            filename = f"{filename}.pdf"
    elif ext in SUPPORTED_EXTENSIONS:
        export_mime_type = None
    elif mime_type in MIME_TYPE_EXTENSIONS:
        ext = MIME_TYPE_EXTENSIONS[mime_type]
        export_mime_type = None
        if not filename.lower().endswith(ext):
            filename = f"{filename}{ext}"
    else:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type for '{filename}'. "
                "DocuMind supports PDF, DOCX, PNG, JPG, JPEG, WEBP, and Google Docs."
            ),
        )

    document_id = str(uuid4())
    file_path = UPLOAD_DIR / f"{document_id}{ext}"
    document_json_path = DOCUMENT_DIR / f"{document_id}.json"

    client = get_google_drive_mcp_client()

    # 3. Download via MCP
    try:
        client.download_file(
            file_id=file_id,
            target_path=file_path,
            export_mime_type=export_mime_type,
        )
    except MCPDownloadError as err:
        file_path.unlink(missing_ok=True)
        logger.error("[GoogleDrive] Download error for %s: %s", file_id, err)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to download '{filename}' from Google Drive: {str(err)}",
        )
    except MCPConnectionError as err:
        file_path.unlink(missing_ok=True)
        logger.error("[GoogleDrive] Connection error downloading %s: %s", file_id, err)
        raise HTTPException(
            status_code=503,
            detail=f"Google Drive MCP server is unavailable: {str(err)}",
        )
    except Exception as err:
        file_path.unlink(missing_ok=True)
        logger.exception("[GoogleDrive] Unexpected error downloading %s: %s", file_id, err)
        raise HTTPException(
            status_code=500,
            detail=f"Download failed for '{filename}': {str(err)}",
        )

    # 4. Ingest using the existing DocuMind extraction & chunking pipeline
    try:
        document_data = extract_document(str(file_path))

        pages = document_data.get("pages", [])
        chunks = document_data.get("chunks", [])

        # Tag chunks with Drive metadata
        for chunk in chunks:
            chunk["document_id"] = document_id
            chunk["filename"] = filename
            chunk["file_type"] = ext.lstrip(".")
            chunk["google_drive_file_id"] = file_id
            chunk["source_type"] = "google_drive"

        saved_document = {
            "document_id": document_id,
            "filename": filename,
            "google_drive_file_id": file_id,
            "source_type": "google_drive",
            "file_path": str(file_path),
            "file_type": ext.lstrip("."),
            "upload_status": "processed",
            "pages": pages,
            "chunks": chunks,
            "image_width": document_data.get("image_width"),
            "image_height": document_data.get("image_height"),
            "all_ocr_bboxes": document_data.get("all_ocr_bboxes", []),
        }

        document_json_path.write_text(
            json.dumps(saved_document, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        logger.info(
            "[GoogleDrive] Successfully ingested %s as %s (%d pages, %d chunks)",
            filename,
            document_id,
            len(pages),
            len(chunks),
        )

        return DriveImportResponse(
            document_id=document_id,
            filename=filename,
            file_type=ext.lstrip("."),
            message="Document imported from Google Drive successfully",
            total_pages=len(pages),
            total_chunks=len(chunks),
            upload_status="processed",
            google_drive_file_id=file_id,
            is_duplicate=False,
        )

    except ValueError as err:
        file_path.unlink(missing_ok=True)
        document_json_path.unlink(missing_ok=True)
        logger.warning("[GoogleDrive] Extraction value error for '%s': %s", filename, err)
        raise HTTPException(
            status_code=400,
            detail=f"Document extraction failed for '{filename}': {str(err)}",
        )
    except RuntimeError as err:
        file_path.unlink(missing_ok=True)
        document_json_path.unlink(missing_ok=True)
        logger.error("[GoogleDrive] Extraction runtime error for '%s': %s", filename, err)
        raise HTTPException(
            status_code=503,
            detail=f"Extraction service error for '{filename}': {str(err)}",
        )
    except Exception as err:
        file_path.unlink(missing_ok=True)
        document_json_path.unlink(missing_ok=True)
        logger.exception("[GoogleDrive] Ingestion failed for '%s': %s", filename, err)
        raise HTTPException(
            status_code=500,
            detail=f"Document processing failed for '{filename}': {str(err)}",
        )
