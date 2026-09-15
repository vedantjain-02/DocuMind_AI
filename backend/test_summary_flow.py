import os
import sys

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


from app.services.chat_service import (
    is_summary_request,
    get_all_document_chunks,
    build_summary_sources,
    summarize_document,
)

DOCUMENT_ID = "6007b54f-f4ed-45e1-ad76-4f8da661a6b4"

test_questions = [
    ("Please give me the summary of the PDF.", True),
    ("Summarize the complete document.", True),
    ("Explain the whole uploaded document.", True),
    ("What is this document about?", True),
    ("What is the main topic of this PDF?", True),
    ("What is the meaning of multi-agent architecture?", False),
]

print("=== TESTING QUESTION INTENT DETECTION ===")
all_passed = True
for q, expected in test_questions:
    actual = is_summary_request(q)
    status = "PASS" if actual == expected else "FAIL"
    if actual != expected:
        all_passed = False
    print(f"[{status}] Q: '{q}' -> is_summary={actual} (expected {expected})")

if not all_passed:
    print("FAILED intent detection tests!")
    sys.exit(1)
print("Intent detection PASSED!\n")

print("=== TESTING GET_ALL_DOCUMENT_CHUNKS ===")
chunks = get_all_document_chunks(DOCUMENT_ID)
print(f"Total chunks retrieved: {len(chunks)}")
assert len(chunks) > 0, "Expected chunks to be retrieved"

# Verify chunk ordering
for i in range(len(chunks) - 1):
    c1 = chunks[i]
    c2 = chunks[i + 1]
    p1 = c1.get("page") or 0
    p2 = c2.get("page") or 0
    idx1 = c1.get("chunk_index") or c1.get("chunk_id") or 0
    idx2 = c2.get("chunk_index") or c2.get("chunk_id") or 0
    assert (p1, idx1) <= (p2, idx2), f"Chunks out of order: {c1} vs {c2}"
print("Chunk ordering strictly preserved: PASS!\n")

print("=== TESTING BUILD_SUMMARY_SOURCES ===")
sources = build_summary_sources(chunks, max_sources=4)
print(f"Total summary sources generated: {len(sources)}")
for s in sources:
    print(f" - Page: {s.get('page')}, Chunk ID: {s.get('chunk_id')}, Title: {s.get('title')}, Preview: {s.get('preview')[:60]}...")
assert 1 <= len(sources) <= 4, "Expected between 1 and 4 sources"
print("build_summary_sources: PASS!\n")

print("=== TESTING FULL-DOCUMENT SUMMARIZE (GROQ CLOUD API) ===")
summary_result = summarize_document(DOCUMENT_ID)
print(f"Answer length: {len(summary_result['answer'])}")
print(f"Answer excerpt:\n{summary_result['answer'][:500]}...\n")
print(f"Sources count: {len(summary_result['sources'])}")

# Check required sections in answer
required_sections = [
    "Main Topic",
    "Important Sections",
    "Key Concepts",
    "Important Definitions",
    "Findings",
]
for sec in required_sections:
    has_sec = sec.lower() in summary_result["answer"].lower()
    print(f" - Section '{sec}': {'FOUND' if has_sec else 'NOT FOUND'}")

print("\nAll service tests completed successfully!")
