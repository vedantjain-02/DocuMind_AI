import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.chat_service import (
    generate_answer,
    is_summary_request,
    load_document,
    load_documents,
    summarize_document,
)
from app.services.conversation_service import (
    add_message,
    create_conversation,
    delete_conversation,
    get_conversation,
    list_conversations,
    update_conversation,
)
from app.services.retrieval_service import retrieve_relevant_chunks


logger = logging.getLogger("documind.chat")


router = APIRouter(
    prefix="/api",
    tags=["Chat"],
)


class ChatSource(BaseModel):
    page: int | None = None
    chunk_id: int | None = None
    chunk_index: int | None = None
    title: str | None = None
    exact_text: str | None = None
    preview: str | None = None
    relevance_score: float | None = None
    character_start: int | None = None
    character_end: int | None = None
    document_id: str | None = None
    filename: str | None = None
    file_type: str | None = None


class ChatResponse(BaseModel):
    document_id: str | None = None
    document_ids: list[str] = Field(default_factory=list)
    question: str
    answer: str
    sources: list[ChatSource] = Field(default_factory=list)


class ChatRequest(BaseModel):
    document_id: str | None = Field(default=None, min_length=1)
    document_ids: list[str] = Field(default_factory=list)
    question: str = Field(..., min_length=2)


class ConversationMessage(BaseModel):
    id: int | str | None = None
    role: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    sources: list[dict] = Field(default_factory=list)
    created_at: str | None = None


class ConversationRecord(BaseModel):
    conversation_id: str
    title: str
    document_ids: list[str] = Field(default_factory=list)
    messages: list[ConversationMessage] = Field(default_factory=list)
    created_at: str
    updated_at: str


class ConversationCreateRequest(BaseModel):
    title: str | None = None
    document_ids: list[str] = Field(default_factory=list)


class ConversationUpdateRequest(BaseModel):
    title: str | None = None
    document_ids: list[str] | None = None
    messages: list[dict] | None = None


class MessageCreateRequest(BaseModel):
    role: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    sources: list[dict] = Field(default_factory=list)


@router.get("/conversations", response_model=list[ConversationRecord])
def get_all_conversations():
    return list_conversations()


@router.post("/conversations", response_model=ConversationRecord, status_code=201)
def create_conversation_record(request: ConversationCreateRequest):
    conversation = create_conversation(
        title=request.title,
        document_ids=request.document_ids or [],
    )
    return ConversationRecord(**conversation)


@router.get("/conversations/{conversation_id}", response_model=ConversationRecord)
def get_conversation_record(conversation_id: str):
    try:
        conversation = get_conversation(conversation_id)
        return ConversationRecord(**conversation)
    except KeyError:
        raise HTTPException(status_code=404, detail="Conversation not found.")


@router.patch("/conversations/{conversation_id}", response_model=ConversationRecord)
def update_conversation_record(conversation_id: str, request: ConversationUpdateRequest):
    try:
        conversation = update_conversation(
            conversation_id,
            title=request.title,
            document_ids=request.document_ids,
            messages=request.messages,
        )
        return ConversationRecord(**conversation)
    except KeyError:
        raise HTTPException(status_code=404, detail="Conversation not found.")


@router.delete("/conversations/{conversation_id}")
def delete_conversation_record(conversation_id: str):
    try:
        result = delete_conversation(conversation_id)
        return result
    except KeyError:
        raise HTTPException(status_code=404, detail="Conversation not found.")


@router.post("/conversations/{conversation_id}/messages", response_model=ConversationMessage, status_code=201)
def add_message_to_conversation(conversation_id: str, request: MessageCreateRequest):
    try:
        message = add_message(
            conversation_id=conversation_id,
            role=request.role,
            content=request.content,
            sources=request.sources,
        )
        return ConversationMessage(**message)
    except KeyError:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.post("/chat", response_model=ChatResponse)
def chat_with_document(request: ChatRequest):
    """
    Handles both single-document and multi-document chat workflows.

    When the frontend provides a ``document_id`` (the currently selected
    document), only that document is used.  This prevents answers or
    sources from leaking across uploaded files.
    """
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required.")

    # Single-document mode when the frontend selects one active document.
    if request.document_id and request.document_id.strip():
        active_document_ids = [request.document_id.strip()]
    else:
        active_document_ids = [
            item.strip()
            for item in (request.document_ids or [])
            if isinstance(item, str) and item.strip()
        ]

    if not active_document_ids:
        raise HTTPException(status_code=400, detail="Document ID is required.")

    try:
        documents = load_documents(active_document_ids)
    except FileNotFoundError as error:
        logger.error("[DocuMind AI] Document not found: %s", error)
        raise HTTPException(status_code=404, detail="Document not found. Please upload the document again.")
    except Exception as error:
        logger.exception("[DocuMind AI] Document loading failed.")
        raise HTTPException(status_code=500, detail=f"Document loading failed: {str(error)}")

    summary_requested = False
    try:
        summary_requested = is_summary_request(question)
    except Exception:
        summary_requested = False

    if summary_requested:
        try:
            result = summarize_document(document_ids=active_document_ids)
            return ChatResponse(
                document_id=active_document_ids[0] if active_document_ids else None,
                document_ids=active_document_ids,
                question=question,
                answer=result.get("answer", "Unable to summarize the document."),
                sources=[ChatSource(**source) for source in result.get("sources", [])],
            )
        except Exception as error:
            logger.exception("[DocuMind AI] Document summarization failed.")
            raise HTTPException(status_code=500, detail=f"Document summarization failed: {str(error)}")

    try:
        retrieved_chunks = retrieve_relevant_chunks(
            document=documents,
            question=question,
            document_id="|".join(active_document_ids),
            max_results=4,
        )
    except Exception as error:
        logger.exception("[DocuMind AI] Retrieval failed.")
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {str(error)}")

    # Safety net: discard any chunk that belongs to a different document.
    allowed_ids = set(active_document_ids)
    retrieved_chunks = [
        chunk
        for chunk in retrieved_chunks
        if str(chunk.get("document_id")) in allowed_ids
    ]

    try:
        result = generate_answer(
            question=question,
            document=documents,
            retrieved_chunks=retrieved_chunks,
            document_ids=active_document_ids,
            documents=documents,
        )
    except Exception as error:
        logger.exception("[DocuMind AI] Answer generation failed.")
        raise HTTPException(status_code=500, detail=f"Answer generation failed: {str(error)}")

    return ChatResponse(
        document_id=active_document_ids[0] if active_document_ids else None,
        document_ids=active_document_ids,
        question=question,
        answer=result.get("answer", "No answer received."),
        sources=[ChatSource(**source) for source in result.get("sources", [])],
    )


__all__ = ["router"]