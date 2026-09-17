import io
from pathlib import Path
from PIL import Image, ImageDraw
import pytest
from fastapi.testclient import TestClient

from main import app
from app.services.ocr_service import extract_ocr_data, extract_text_from_image
from app.services.chat_service import match_ocr_boxes, build_document_sources
from app.services.document_service import extract_document


def create_test_image(text_lines: list[str], width: int = 600, height: int = 300) -> bytes:
    """Helper to draw text onto a blank image."""
    img = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(img)
    y = 40
    for line in text_lines:
        draw.text((40, y), line, fill="black")
        y += 50
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestOcrExtraction:
    def test_extract_ocr_data_structure(self):
        """Verify extract_ocr_data returns all expected fields, dimensions, and normalized confidence."""
        img_bytes = create_test_image(["DocuMind Neural Engine", "Multi-Agent System"], 700, 350)
        ocr_data = extract_ocr_data(img_bytes)

        assert ocr_data["image_width"] == 700
        assert ocr_data["image_height"] == 350
        assert "DocuMind" in ocr_data["text"] or "Engine" in ocr_data["text"]
        assert len(ocr_data["lines"]) >= 1
        assert len(ocr_data["words"]) >= 1

        # Check line structure
        line = ocr_data["lines"][0]
        assert "text" in line
        assert "bbox" in line
        assert "confidence" in line
        assert 0.0 <= line["confidence"] <= 1.0

        bbox = line["bbox"]
        assert "x" in bbox and "y" in bbox and "width" in bbox and "height" in bbox
        assert bbox["x"] >= 0 and bbox["x"] + bbox["width"] <= 700
        assert bbox["y"] >= 0 and bbox["y"] + bbox["height"] <= 350

    def test_backward_compatible_extract_text_from_image(self):
        """Verify extract_text_from_image continues to work and returns string."""
        img_bytes = create_test_image(["Agentic Workflow Ready"], 500, 200)
        text = extract_text_from_image(img_bytes)
        assert isinstance(text, str)
        assert len(text) > 0

    def test_coordinate_scaling_invariance_small_image(self):
        """Verify bounding boxes stay bounded within original dimensions on small (<1200px) images."""
        img_bytes = create_test_image(["Small Canvas Test"], 400, 200)
        ocr_data = extract_ocr_data(img_bytes)

        assert ocr_data["image_width"] == 400
        assert ocr_data["image_height"] == 200
        for line in ocr_data["lines"]:
            box = line["bbox"]
            assert box["x"] >= 0
            assert box["y"] >= 0
            assert box["x"] + box["width"] <= 400
            assert box["y"] + box["height"] <= 200


class TestOcrMatchingAndMerging:
    def test_exact_ocr_source_match(self):
        ocr_lines = [
            {"text": "Agentic Architecture", "bbox": {"x": 20, "y": 30, "width": 150, "height": 20}, "confidence": 0.95},
            {"text": "Fast Parallel Processing", "bbox": {"x": 20, "y": 60, "width": 180, "height": 20}, "confidence": 0.92},
            {"text": "Unrelated Footer Info", "bbox": {"x": 20, "y": 250, "width": 120, "height": 18}, "confidence": 0.88},
        ]

        matched_text, overall_box, line_boxes, conf, match_type = match_ocr_boxes("Agentic Architecture", ocr_lines)
        assert match_type == "exact"
        assert overall_box is not None
        assert overall_box["x"] == 20
        assert overall_box["y"] == 30
        assert overall_box["width"] == 150
        assert overall_box["height"] == 20
        assert conf == 0.95
        assert "Agentic Architecture" in matched_text

    def test_case_insensitive_match(self):
        ocr_lines = [
            {"text": "Agentic Architecture", "bbox": {"x": 20, "y": 30, "width": 150, "height": 20}, "confidence": 0.95},
        ]
        matched_text, overall_box, line_boxes, conf, match_type = match_ocr_boxes("agentic architecture", ocr_lines)
        assert match_type == "exact"
        assert overall_box is not None
        assert overall_box["x"] == 20
        assert "Agentic Architecture" in matched_text

    def test_match_with_extra_spaces_and_newlines(self):
        ocr_lines = [
            {"text": "Agentic Architecture", "bbox": {"x": 20, "y": 30, "width": 150, "height": 20}, "confidence": 0.95},
        ]
        target = "   \n  Agentic \t  Architecture \n\n "
        matched_text, overall_box, line_boxes, conf, match_type = match_ocr_boxes(target, ocr_lines)
        assert match_type == "exact"
        assert overall_box is not None
        assert overall_box["x"] == 20

    def test_adjacent_line_merging(self):
        """Adjacent matching lines should merge into a single bounding box."""
        ocr_lines = [
            {"text": "Deep Neural Network", "bbox": {"x": 30, "y": 40, "width": 160, "height": 22}, "confidence": 0.90},
            {"text": "Trained on Legal Docs", "bbox": {"x": 30, "y": 68, "width": 170, "height": 22}, "confidence": 0.94},
        ]
        target = "Deep Neural Network Trained on Legal Docs"
        matched_text, overall_box, merged_boxes, conf, match_type = match_ocr_boxes(target, ocr_lines)

        assert overall_box is not None
        assert len(merged_boxes) == 1
        assert merged_boxes[0]["y"] == 40
        assert merged_boxes[0]["height"] >= 45  # Covers both lines
        assert round(conf, 2) == 0.92
        assert "Deep Neural Network" in matched_text
        assert "Trained on Legal Docs" in matched_text

    def test_keyword_fallback_matching(self):
        """When exact line or phrase does not match, keyword overlap triggers keyword matching."""
        ocr_lines = [
            {"text": "Deliberate Reasoning Pattern", "bbox": {"x": 20, "y": 30, "width": 150, "height": 20}, "confidence": 0.92},
            {"text": "Unrelated Weather Forecast", "bbox": {"x": 20, "y": 150, "width": 180, "height": 20}, "confidence": 0.85},
        ]
        # Paraphrased query that shares keywords 'deliberate' and 'reasoning'
        target = "The architecture utilizes deliberate reasoning to critique its own answers."
        matched_text, overall_box, merged_boxes, conf, match_type = match_ocr_boxes(target, ocr_lines)

        assert match_type == "keyword"
        assert overall_box is not None
        assert overall_box["x"] == 20
        assert overall_box["y"] == 30
        assert "Deliberate Reasoning Pattern" in matched_text

    def test_multiple_bounding_boxes_separated(self):
        """Distant lines that match should produce multiple merged bounding boxes."""
        ocr_lines = [
            {"text": "Top Header Overview", "bbox": {"x": 20, "y": 30, "width": 150, "height": 20}, "confidence": 0.95},
            {"text": "Middle Body Explanation", "bbox": {"x": 20, "y": 180, "width": 160, "height": 20}, "confidence": 0.80},
            {"text": "Bottom Footer Note", "bbox": {"x": 20, "y": 450, "width": 140, "height": 20}, "confidence": 0.90},
        ]
        target = "Top Header Overview and also Bottom Footer Note"
        matched_text, overall_box, merged_boxes, conf, match_type = match_ocr_boxes(target, ocr_lines)

        assert overall_box is not None
        assert len(merged_boxes) == 2
        assert merged_boxes[0]["y"] == 30
        assert merged_boxes[1]["y"] == 450

    def test_no_match_fallback(self):
        """Arbitrary unmatched text must return None, [], None, 'none' without crashing."""
        ocr_lines = [
            {"text": "DocuMind AI", "bbox": {"x": 10, "y": 20, "width": 100, "height": 20}, "confidence": 0.90},
        ]
        matched_text, overall_box, line_boxes, conf, match_type = match_ocr_boxes("Quantum Physics Astronomy", ocr_lines)
        assert matched_text == ""
        assert overall_box is None
        assert line_boxes == []
        assert conf is None
        assert match_type == "none"

    def test_empty_or_whitespace_handling(self):
        matched_text, overall_box, line_boxes, conf, match_type = match_ocr_boxes("", [])
        assert matched_text == ""
        assert overall_box is None
        assert line_boxes == []
        assert conf is None
        assert match_type == "none"


class TestDocumentExtractionMetadata:
    def test_extract_document_includes_image_metadata(self, tmp_path):
        img_path = tmp_path / "spec_test.png"
        img_bytes = create_test_image(["Microservice Spec", "Version 2.0"], 640, 320)
        img_path.write_bytes(img_bytes)

        result = extract_document(str(img_path))
        assert "pages" in result
        assert "chunks" in result
        assert result["image_width"] == 640
        assert result["image_height"] == 320

        # Verify chunks have propagated OCR lines
        chunk = result["chunks"][0]
        assert chunk["image_width"] == 640
        assert chunk["image_height"] == 320
        assert len(chunk["ocr_lines"]) >= 1


class TestEndToEndChatSourceHighlighting:
    @pytest.fixture(autouse=True)
    def setup_client(self):
        self.client = TestClient(app)

    def test_upload_and_chat_with_image_source_highlight(self):
        """Upload image, query /api/chat, verify source contains valid bbox and dimensions."""
        img_bytes = create_test_image(
            ["DocuMind Neural Highlighting", "Accurate Source Bounding Boxes"],
            width=800,
            height=400,
        )

        upload_res = self.client.post(
            "/api/upload",
            files={"files": ("neural_test.png", img_bytes, "image/png")},
        )
        assert upload_res.status_code == 200, upload_res.text
        doc_data = upload_res.json()
        doc_id = doc_data["document_id"]

        try:
            # Query the chat endpoint
            chat_res = self.client.post(
                "/api/chat",
                json={
                    "document_id": doc_id,
                    "question": "What kind of highlighting is described?",
                },
            )
            assert chat_res.status_code == 200, chat_res.text
            chat_data = chat_res.json()
            assert "answer" in chat_data
            assert len(chat_data["sources"]) > 0

            source = chat_data["sources"][0]
            assert source["file_type"] == "png"
            assert source["image_width"] == 800
            assert source["image_height"] == 400

            # Verify bbox is populated
            assert source["bbox"] is not None
            assert "x" in source["bbox"]
            assert "y" in source["bbox"]
            assert "width" in source["bbox"]
            assert "height" in source["bbox"]
            assert source["confidence"] is not None
            assert 0.0 <= source["confidence"] <= 1.0
            assert source["text"] is not None and len(source["text"]) > 0
            assert source["match_type"] in ("exact", "phrase", "keyword", "word")
        finally:
            # Clean up
            self.client.delete(f"/api/documents/{doc_id}")

    def test_existing_image_document_highlighting_images_jpg(self):
        """Verify querying existing uploaded image 'cfd430f2-efa7-4723-a104-9d6254d005c1' (images.jpg) works."""
        doc_id = "cfd430f2-efa7-4723-a104-9d6254d005c1"
        chat_res = self.client.post(
            "/api/chat",
            json={
                "document_id": doc_id,
                "question": "What is all agentic architecture?",
            },
        )
        assert chat_res.status_code == 200, chat_res.text
        chat_data = chat_res.json()
        assert "answer" in chat_data
        assert len(chat_data["sources"]) > 0

        source = chat_data["sources"][0]
        assert source["file_type"] == "jpg"
        assert source["image_width"] == 493
        assert source["image_height"] == 622
        assert source["bbox"] is not None
        assert source["bbox"]["x"] >= 0
        assert source["bbox"]["y"] >= 0
        assert source["bbox"]["width"] > 0
        assert source["bbox"]["height"] > 0
        assert source["confidence"] is not None
        assert 0.0 <= source["confidence"] <= 1.0
        assert "Agentic Architectures" in source["text"]
        assert source["match_type"] in ("exact", "phrase", "keyword", "word")
