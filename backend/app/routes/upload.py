import json
import logging
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.services.chat_service import generate_document_summary
from app.services.document_service import extract_document

logger = logging.getLogger("documind.upload")


router = APIRouter(
    prefix="/api",
    tags=["Documents"]
)


BASE_DIR = Path(__file__).resolve().parents[2]
UPLOAD_DIR = BASE_DIR / "data" / "uploads"
DOCUMENT_DIR = BASE_DIR / "data" / "documents"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DOCUMENT_DIR.mkdir(parents=True, exist_ok=True)


ALLOWED_EXTENSIONS = {".pdf", ".docx", ".png", ".jpg", ".jpeg", ".webp"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}



class DocumentSummary(BaseModel):
    document_id: str
    filename: str
    file_type: str
    upload_status: str
    total_pages: int = 0
    total_chunks: int = 0


class UploadResult(BaseModel):
    document_id: str
    filename: str
    file_type: str
    message: str
    total_pages: int
    total_chunks: int
    upload_status: str = "processed"


class DocumentSummaryResponse(BaseModel):
    document_id: str
    filename: str
    overview: str = ""
    main_topics: list[str] = Field(default_factory=list)
    important_points: list[str] = Field(default_factory=list)
    key_takeaways: list[str] = Field(default_factory=list)
    generated_at: str | None = None
    source_count: int = 0
    status: str = "processed"


def _document_record_to_summary(document_data: dict) -> DocumentSummary:
    file_path = Path(document_data.get("file_path", ""))
    file_type = (
        document_data.get("file_type")
        or file_path.suffix.lower().lstrip(".")
        or "unknown"
    )

    pages = document_data.get("pages", [])
    chunks = document_data.get("chunks", [])

    return DocumentSummary(
        document_id=document_data.get("document_id", ""),
        filename=document_data.get("filename", file_path.name),
        file_type=file_type,
        upload_status=document_data.get("upload_status", "processed"),
        total_pages=len(pages),
        total_chunks=len(chunks),
    )


def _load_document_metadata(document_id: str) -> dict:
    document_json_path = DOCUMENT_DIR / f"{document_id}.json"

    if not document_json_path.exists():
        raise FileNotFoundError(document_json_path)

    return json.loads(document_json_path.read_text(encoding="utf-8"))


def _delete_document_record(document_id: str) -> None:
    document_json_path = DOCUMENT_DIR / f"{document_id}.json"
    if document_json_path.exists():
        try:
            data = json.loads(document_json_path.read_text(encoding="utf-8"))
            saved_file_path = Path(data.get("file_path", ""))
            if saved_file_path.exists():
                saved_file_path.unlink(missing_ok=True)
        except Exception:
            pass
        document_json_path.unlink(missing_ok=True)

    for suffix in ALLOWED_EXTENSIONS:
        file_path = UPLOAD_DIR / f"{document_id}{suffix}"
        if file_path.exists():
            file_path.unlink(missing_ok=True)



@router.get("/documents", response_model=list[DocumentSummary])
async def list_documents():
    documents: list[DocumentSummary] = []

    for path in sorted(DOCUMENT_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        documents.append(_document_record_to_summary(data))

    return documents


@router.get("/documents/{document_id}")
async def get_document_details(document_id: str):
    try:
        return _load_document_metadata(document_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")


@router.get("/documents/{document_id}/file")
async def get_document_file(document_id: str):
    try:
        document_data = _load_document_metadata(document_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = Path(document_data.get("file_path", ""))
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Document file not found")

    media_types = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }
    content_type = media_types.get(file_path.suffix.lower(), "application/octet-stream")

    return FileResponse(
        path=str(file_path),
        media_type=content_type,
        filename=document_data.get("filename", file_path.name),
    )



@router.get("/documents/{document_id}/summary", response_model=DocumentSummaryResponse)
@router.post("/documents/{document_id}/summary", response_model=DocumentSummaryResponse)
async def summarize_document_endpoint(document_id: str):
    """Generate a structured summary for a stored document using the existing Grok-backed document pipeline."""
    try:
        _load_document_metadata(document_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        summary = generate_document_summary(document_id)
        return DocumentSummaryResponse(**summary)
    except RuntimeError as error:
        logger.exception("[DocuMind AI] Summary generation failed for %s", document_id)
        raise HTTPException(status_code=502, detail=f"Summary generation failed: {str(error)}")
    except ValueError as error:
        logger.warning("[DocuMind AI] Invalid summary request for %s: %s", document_id, error)
        raise HTTPException(status_code=400, detail=f"Summary generation failed: {str(error)}")
    except Exception as error:
        logger.exception("[DocuMind AI] Unexpected summary generation error for %s", document_id)
        raise HTTPException(status_code=500, detail=f"Summary generation failed: {str(error)}")


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    try:
        _load_document_metadata(document_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")

    _delete_document_record(document_id)
    generate_document_summary.cache_clear()

    return {
        "document_id": document_id,
        "status": "deleted",
        "message": "Document removed successfully",
    }


@router.delete("/documents")
async def clear_all_documents():
    for path in list(DOCUMENT_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            document_id = data.get("document_id")
            if document_id:
                _delete_document_record(document_id)
        except Exception:
            path.unlink(missing_ok=True)

    generate_document_summary.cache_clear()

    return {
        "status": "cleared",
        "message": "All documents removed successfully",
    }


@router.post("/upload")
async def upload_document(
    files: list[UploadFile] = File(default_factory=list),
    file: UploadFile | None = File(default=None),
):
    """
    Upload one or many PDF/DOCX files, extract text, split into chunks,
    and save document data for chatbot usage.
    """
    incoming_files = files or ([file] if file is not None else [])

    if not incoming_files:
        raise HTTPException(
            status_code=400,
            detail="No files were uploaded",
        )

    existing_documents = await list_documents()
    existing_names = {
        item.filename.lower()
        for item in existing_documents
    }

    uploaded_results: list[dict] = []

    for upload_file in incoming_files:
        if not upload_file.filename:
            raise HTTPException(
                status_code=400,
                detail="Filename is missing",
            )

        filename = upload_file.filename
        extension = Path(filename).suffix.lower()

        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type for '{filename}'. Allowed formats: PDF, DOCX, PNG, JPG, JPEG, WEBP.",
            )


        if filename.lower() in existing_names:
            raise HTTPException(
                status_code=409,
                detail=f"Duplicate upload: '{filename}' is already in the workspace.",
            )

        document_id = str(uuid4())
        file_path = UPLOAD_DIR / f"{document_id}{extension}"
        document_json_path = DOCUMENT_DIR / f"{document_id}.json"

        try:
            content = await upload_file.read()

            if not content:
                raise HTTPException(
                    status_code=400,
                    detail=f"Uploaded file is empty: '{filename}'",
                )

            file_path.write_bytes(content)
            document_data = extract_document(str(file_path))

            pages = document_data["pages"]
            chunks = document_data["chunks"]

            for chunk in chunks:
                chunk["document_id"] = document_id
                chunk["filename"] = filename
                chunk["file_type"] = extension.lstrip(".")

            saved_document = {
                "document_id": document_id,
                "filename": filename,
                "file_path": str(file_path),
                "file_type": extension.lstrip("."),
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

            uploaded_results.append({
                "document_id": document_id,
                "filename": filename,
                "file_type": extension.lstrip("."),
                "message": "Document uploaded successfully",
                "total_pages": len(pages),
                "total_chunks": len(chunks),
                "upload_status": "processed",
            })

        except HTTPException:
            file_path.unlink(missing_ok=True)
            document_json_path.unlink(missing_ok=True)
            raise

        except ValueError as error:
            file_path.unlink(missing_ok=True)
            document_json_path.unlink(missing_ok=True)
            logger.warning("[DocuMind AI] Document extraction value error for '%s': %s", filename, error)
            raise HTTPException(
                status_code=400,
                detail=f"Document extraction failed for '{filename}': {str(error)}",
            )

        except RuntimeError as error:
            file_path.unlink(missing_ok=True)
            document_json_path.unlink(missing_ok=True)
            logger.error("[DocuMind AI] Document extraction runtime error for '%s': %s", filename, error)
            raise HTTPException(
                status_code=503,
                detail=f"Extraction service error for '{filename}': {str(error)}",
            )

        except Exception as error:
            file_path.unlink(missing_ok=True)
            document_json_path.unlink(missing_ok=True)
            logger.exception("[DocuMind AI] Unexpected document extraction error for '%s'", filename)
            raise HTTPException(
                status_code=500,
                detail=f"Document extraction failed for '{filename}': {str(error)}",
            )


    if len(uploaded_results) == 1:
        return uploaded_results[0]

    return {
        "documents": uploaded_results,
        "count": len(uploaded_results),
        "message": "Documents uploaded successfully",
    }