import os
import sys

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)
DOCUMENT_ID = "6007b54f-f4ed-45e1-ad76-4f8da661a6b4"

print("=== TEST 1: NON-EXISTENT DOCUMENT (404) ===")
res_404 = client.post("/api/chat", json={"document_id": "non-existent-id", "question": "Summarize this"})
print(f"Status: {res_404.status_code}, Detail: {res_404.json().get('detail')}")
assert res_404.status_code == 404
print("Test 1 PASSED!\n")

print("=== TEST 2: NORMAL RAG QUESTION ===")
rag_payload = {
    "document_id": DOCUMENT_ID,
    "question": "What is the meaning of multi-agent architecture?",
}
res_rag = client.post("/api/chat", json=rag_payload)
print(f"Status: {res_rag.status_code}")
assert res_rag.status_code == 200
rag_data = res_rag.json()
assert "answer" in rag_data and "sources" in rag_data
print(f"Answer snippet: {rag_data['answer'][:200]}...")
print(f"Sources count: {len(rag_data['sources'])}")
print("Test 2 PASSED!\n")

print("=== TEST 3: SUMMARY REQUEST VIA API ===")
summary_payload = {
    "document_id": DOCUMENT_ID,
    "question": "What is the main topic of this PDF?",
}
res_summary = client.post("/api/chat", json=summary_payload)
print(f"Status: {res_summary.status_code}")
assert res_summary.status_code == 200
summary_data = res_summary.json()
assert "answer" in summary_data and "sources" in summary_data
assert len(summary_data["sources"]) > 0
print(f"Summary Answer snippet: {summary_data['answer'][:300]}...")
print(f"Sources count: {len(summary_data['sources'])}")
for s in summary_data["sources"]:
    print(f"  Source - Page {s.get('page')}: {s.get('preview')[:60]}...")
print("Test 3 PASSED!\n")

print("ALL API TESTS PASSED SUCCESSFULLY!")
