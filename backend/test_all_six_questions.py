import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient
from main import app
from app.services.chat_service import is_summary_request

client = TestClient(app)
DOCUMENT_ID = "6007b54f-f4ed-45e1-ad76-4f8da661a6b4"

questions = [
    ("Please give me the summary of the PDF.", True),
    ("Summarize the complete document.", True),
    ("Explain the whole uploaded document.", True),
    ("What is this document about?", True),
    ("What is the main topic of this PDF?", True),
    ("What is the meaning of multi-agent architecture?", False),
]

print("=" * 60)
print("PART 1: VERIFYING INTENT DETECTION ON ALL 6 REQUIRED QUESTIONS")
print("=" * 60)

for idx, (question, expect_summary) in enumerate(questions, 1):
    detected_summary = is_summary_request(question)
    status = "PASS" if detected_summary == expect_summary else "FAIL"
    print(f"[{status}] Q{idx}: '{question}' -> is_summary={detected_summary} (Expected: {expect_summary})")
    assert detected_summary == expect_summary, f"Question {idx} detection mismatch!"

print("\nAll 6 question intent classifications PASSED!\n")

print("=" * 60)
print("PART 2: TESTING /api/chat ENDPOINT FOR SUMMARY & NORMAL RAG")
print("=" * 60)

# 1. Test Summary question (Q1)
q1 = questions[0][0]
print(f"\n--- Testing Q1 (Summary): '{q1}' ---")
res1 = client.post("/api/chat", json={"document_id": DOCUMENT_ID, "question": q1})
assert res1.status_code == 200, f"Q1 failed: {res1.text}"
data1 = res1.json()
assert "answer" in data1 and "sources" in data1
print(f"Status: {res1.status_code}")
print(f"Answer Preview:\n{data1['answer'][:300]}...\n")
print(f"Sources Count: {len(data1['sources'])}")
for s in data1["sources"]:
    print(f"  Source Page {s.get('page')}: preview='{s.get('preview')[:50]}...'")
print("Q1 PASSED!")

# 2. Test Normal RAG question (Q6)
q6 = questions[5][0]
print(f"\n--- Testing Q6 (Normal RAG): '{q6}' ---")
res6 = client.post("/api/chat", json={"document_id": DOCUMENT_ID, "question": q6})
assert res6.status_code == 200, f"Q6 failed: {res6.text}"
data6 = res6.json()
assert "answer" in data6 and "sources" in data6
print(f"Status: {res6.status_code}")
print(f"Answer Preview:\n{data6['answer'][:300]}...\n")
print("Q6 PASSED!")

print("\n" + "=" * 60)
print("ALL 6 REQUIRED QUESTIONS VERIFIED SUCCESSFULLY!")
print("=" * 60)

