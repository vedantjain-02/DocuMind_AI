import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.chat_service import (
    load_document,
    generate_answer,
    is_summary_request,
    summarize_document,
)

from app.services.retrieval_service import (
    retrieve_relevant_chunks,
)


logger = logging.getLogger("documind.chat")


router = APIRouter(
    prefix="/api",
    tags=["Chat"],
)


class ChatRequest(BaseModel):
    document_id: str = Field(
        ...,
        min_length=1,
    )

    question: str = Field(
        ...,
        min_length=2,
    )


@router.post("/chat")
def chat_with_document(request: ChatRequest):
    """
    Handles both:

    1. Full-document summary requests
    2. Normal document question-answering requests
    """

    document_id = request.document_id.strip()
    question = request.question.strip()

    if not document_id:
        raise HTTPException(
            status_code=400,
            detail="Document ID is required.",
        )

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Question is required.",
        )

    # ============================================================
    # LOAD DOCUMENT
    # ============================================================

    try:
        document = load_document(document_id)

    except FileNotFoundError:
        logger.error(
            "[DocuMind AI] Document not found: %s",
            document_id,
        )

        raise HTTPException(
            status_code=404,
            detail=(
                "Document not found. "
                "Please upload the document again."
            ),
        )

    except Exception as error:
        logger.exception(
            "[DocuMind AI] Document loading failed.",
        )

        raise HTTPException(
            status_code=500,
            detail=f"Document loading failed: {str(error)}",
        )

    # ============================================================
    # SUMMARY REQUEST DETECTION
    # ============================================================

    try:
        summary_requested = is_summary_request(question)

    except Exception as error:
        logger.exception(
            "[DocuMind AI] Summary detection failed.",
        )

        summary_requested = False

    logger.info(
        "[DocuMind AI] Question: %s",
        question,
    )

    logger.info(
        "[DocuMind AI] Summary request detected: %s",
        summary_requested,
    )

    print(
        f"[DocuMind AI] Question: {question}",
        flush=True,
    )

    print(
        f"[DocuMind AI] Summary request: {summary_requested}",
        flush=True,
    )

    # ============================================================
    # FULL DOCUMENT SUMMARY MODE
    # ============================================================

    if summary_requested:
        logger.info(
            "[DocuMind AI] Request mode: full-document summary",
        )

        print(
            "[DocuMind AI] Request mode: full-document summary",
            flush=True,
        )

        try:
            result = summarize_document(
                document_id=document_id,
            )

            return {
                "document_id": document_id,
                "question": question,
                "answer": result.get(
                    "answer",
                    "Unable to summarize the document.",
                ),
                "sources": result.get(
                    "sources",
                    [],
                ),
            }

        except Exception as error:
            logger.exception(
                "[DocuMind AI] Document summarization failed.",
            )

            raise HTTPException(
                status_code=500,
                detail=(
                    "Document summarization failed: "
                    f"{str(error)}"
                ),
            )

    # ============================================================
    # NORMAL RAG MODE
    # ============================================================

    logger.info(
        "[DocuMind AI] Request mode: normal RAG",
    )

    print(
        "[DocuMind AI] Request mode: normal RAG",
        flush=True,
    )

    try:
        retrieved_chunks = retrieve_relevant_chunks(
            document=document,
            question=question,
            document_id=document_id,
            max_results=4,
        )

    except Exception as error:
        logger.exception(
            "[DocuMind AI] Retrieval failed.",
        )

        raise HTTPException(
            status_code=500,
            detail=f"Retrieval failed: {str(error)}",
        )

    try:
        result = generate_answer(
            question=question,
            document=document,
            retrieved_chunks=retrieved_chunks,
        )

    except Exception as error:
        logger.exception(
            "[DocuMind AI] Answer generation failed.",
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Answer generation failed: "
                f"{str(error)}"
            ),
        )

    return {
        "document_id": document_id,
        "question": question,
        "answer": result.get(
            "answer",
            "No answer received.",
        ),
        "sources": result.get(
            "sources",
            [],
        ),
    }


__all__ = ["router"]