import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


BASE_DIR = Path(__file__).resolve().parents[2]
CONVERSATIONS_PATH = BASE_DIR / "data" / "conversations.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_store() -> None:
    CONVERSATIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not CONVERSATIONS_PATH.exists():
        CONVERSATIONS_PATH.write_text("[]", encoding="utf-8")


def _read_store() -> list[dict]:
    _ensure_store()
    try:
        data = json.loads(CONVERSATIONS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    return data if isinstance(data, list) else []


def _write_store(conversations: list[dict]) -> None:
    _ensure_store()
    CONVERSATIONS_PATH.write_text(
        json.dumps(conversations, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _normalize_message(message: dict) -> dict:
    if not isinstance(message, dict):
        return {"id": 1, "role": "user", "content": "", "sources": []}

    role = str(message.get("role", "user")).strip() or "user"
    content = str(message.get("content", "")).strip()
    sources = message.get("sources") if isinstance(message.get("sources"), list) else []

    message_id = message.get("id")
    if message_id is None:
        message_id = 1

    return {
        "id": message_id,
        "role": role,
        "content": content,
        "sources": sources,
    }


def _coerce_document_ids(document_ids: list[str] | None) -> list[str]:
    if not document_ids:
        return []

    cleaned = []
    for item in document_ids:
        if isinstance(item, str) and item.strip():
            cleaned.append(item.strip())
    return cleaned


def list_conversations() -> list[dict]:
    conversations = _read_store()
    return sorted(
        conversations,
        key=lambda item: item.get("updated_at", ""),
        reverse=True,
    )


def get_conversation(conversation_id: str) -> dict:
    for conversation in list_conversations():
        if conversation.get("conversation_id") == conversation_id:
            return conversation
    raise KeyError(conversation_id)


def create_conversation(title: str | None = None, document_ids: list[str] | None = None) -> dict:
    now = _utc_now()
    conversation = {
        "conversation_id": str(uuid4()),
        "title": (title or "New chat").strip() or "New chat",
        "document_ids": _coerce_document_ids(document_ids),
        "messages": [],
        "created_at": now,
        "updated_at": now,
    }

    conversations = list_conversations()
    conversations.append(conversation)
    _write_store(conversations)
    return conversation


def update_conversation(
    conversation_id: str,
    *,
    title: str | None = None,
    document_ids: list[str] | None = None,
    messages: list[dict] | None = None,
) -> dict:
    conversations = list_conversations()
    found = None
    for index, conversation in enumerate(conversations):
        if conversation.get("conversation_id") == conversation_id:
            found = index
            break

    if found is None:
        raise KeyError(conversation_id)

    conversation = conversations[found]

    if title is not None:
        conversation["title"] = (title or "New chat").strip() or "New chat"

    if document_ids is not None:
        conversation["document_ids"] = _coerce_document_ids(document_ids)

    if messages is not None:
        conversation["messages"] = [
            _normalize_message(message)
            for message in messages
            if isinstance(message, dict)
        ]

    conversation["updated_at"] = _utc_now()
    _write_store(conversations)
    return conversation


def add_message(conversation_id: str, role: str, content: str, sources: list[dict] | None = None) -> dict:
    conversations = list_conversations()
    for conversation in conversations:
        if conversation.get("conversation_id") == conversation_id:
            normalized_content = str(content or "").strip()
            if not normalized_content:
                raise ValueError("Message content is required.")

            next_id = len(conversation.get("messages", [])) + 1
            message = {
                "id": next_id,
                "role": str(role or "user").strip() or "user",
                "content": normalized_content,
                "sources": sources or [],
            }
            conversation.setdefault("messages", []).append(message)
            conversation["updated_at"] = _utc_now()
            _write_store(conversations)
            return message

    raise KeyError(conversation_id)


def delete_conversation(conversation_id: str) -> dict:
    conversations = list_conversations()
    remaining = [conversation for conversation in conversations if conversation.get("conversation_id") != conversation_id]
    if len(remaining) == len(conversations):
        raise KeyError(conversation_id)

    _write_store(remaining)
    return {"conversation_id": conversation_id, "status": "deleted"}
