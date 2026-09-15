from pathlib import Path
from uuid import uuid4
import json

from fastapi import APIRouter, UploadFile, File, HTTPException

from app.services.document_service import extract_document


router = APIRouter(
    prefix="/api",
    tags=["Documents"]
)


UPLOAD_DIR = Path("data/uploads")
DOCUMENT_DIR = Path("data/documents")

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DOCUMENT_DIR.mkdir(parents=True, exist_ok=True)


ALLOWED_EXTENSIONS = {".pdf", ".docx"}


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Upload PDF/DOCX, extract text, split into chunks
    and save document data for chatbot usage.
    """

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Filename is missing"
        )

    extension = Path(file.filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Only PDF and DOCX files are supported"
        )

    document_id = str(uuid4())

    file_path = UPLOAD_DIR / f"{document_id}{extension}"
    document_json_path = DOCUMENT_DIR / f"{document_id}.json"

    try:
        content = await file.read()

        if not content:
            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty"
            )

        file_path.write_bytes(content)

        document_data = extract_document(str(file_path))

        pages = document_data["pages"]
        chunks = document_data["chunks"]

        saved_document = {
            "document_id": document_id,
            "filename": file.filename,
            "file_path": str(file_path),
            "pages": pages,
            "chunks": chunks
        }

        document_json_path.write_text(
            json.dumps(saved_document, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        return {
            "document_id": document_id,
            "filename": file.filename,
            "message": "Document uploaded successfully",
            "total_pages": len(pages),
            "total_chunks": len(chunks)
        }

    except HTTPException:
        file_path.unlink(missing_ok=True)
        document_json_path.unlink(missing_ok=True)
        raise

    except Exception as error:
        file_path.unlink(missing_ok=True)
        document_json_path.unlink(missing_ok=True)

        raise HTTPException(
            status_code=500,
            detail=f"Document extraction failed: {str(error)}"
        )