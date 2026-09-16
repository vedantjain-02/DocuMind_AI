import uuid

from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_create_and_list_conversations():
    response = client.post(
        "/api/conversations",
        json={
            "title": "Research chat",
            "document_ids": ["doc-1", "doc-2"],
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["title"] == "Research chat"
    assert payload["document_ids"] == ["doc-1", "doc-2"]
    assert payload["conversation_id"]

    list_response = client.get("/api/conversations")
    assert list_response.status_code == 200, list_response.text
    conversations = list_response.json()
    assert any(item["conversation_id"] == payload["conversation_id"] for item in conversations)


def test_open_update_and_delete_conversation():
    created = client.post(
        "/api/conversations",
        json={"title": "Summary chat", "document_ids": ["doc-55"]},
    ).json()
    conversation_id = created["conversation_id"]

    opened = client.get(f"/api/conversations/{conversation_id}")
    assert opened.status_code == 200, opened.text
    assert opened.json()["title"] == "Summary chat"

    renamed = client.patch(
        f"/api/conversations/{conversation_id}",
        json={"title": "Renamed summary chat"},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["title"] == "Renamed summary chat"

    deleted = client.delete(f"/api/conversations/{conversation_id}")
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["status"] == "deleted"


def test_add_messages_and_clear_chat():
    created = client.post(
        "/api/conversations",
        json={"title": "QA chat", "document_ids": ["doc-9"]},
    ).json()
    conversation_id = created["conversation_id"]

    user_message = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={
            "role": "user",
            "content": "What is this document about?",
            "sources": [],
        },
    )
    assert user_message.status_code == 201, user_message.text

    assistant_message = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={
            "role": "assistant",
            "content": "It explains the system design.",
            "sources": [{"page": 1, "preview": "system design"}],
        },
    )
    assert assistant_message.status_code == 201, assistant_message.text

    loaded = client.get(f"/api/conversations/{conversation_id}")
    assert loaded.status_code == 200, loaded.text
    assert len(loaded.json()["messages"]) == 2

    cleared = client.patch(
        f"/api/conversations/{conversation_id}",
        json={"messages": []},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["messages"] == []
