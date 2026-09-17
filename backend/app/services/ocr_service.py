import logging
import os
import shutil
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter

logger = logging.getLogger("documind.ocr")

try:
    import pytesseract
except ImportError:
    pytesseract = None

TESSERACT_INSTALL_GUIDE = (
    "Tesseract OCR is not installed or not configured on this system. "
    "To enable image text extraction on Windows:\n"
    "1. Download the Windows installer from: https://github.com/UB-Mannheim/tesseract/wiki\n"
    "2. Install to the default path: C:\\Program Files\\Tesseract-OCR\n"
    "3. Add 'C:\\Program Files\\Tesseract-OCR' to your system PATH, or set TESSERACT_CMD in backend/.env\n"
    "4. Restart the backend server."
)

TESSERACT_CANDIDATE_PATHS = [
    Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
    Path(os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe")),
]


def configure_tesseract() -> bool:
    """
    Locates and configures the Tesseract executable for pytesseract.
    Returns True if Tesseract is available, False otherwise.
    """
    if pytesseract is None:
        logger.warning("[DocuMind OCR] pytesseract library is not installed.")
        return False

    # 1. Check explicit environment override
    env_cmd = os.getenv("TESSERACT_CMD", "").strip() or os.getenv("TESSERACT_PATH", "").strip()
    if env_cmd:
        env_path = Path(env_cmd)
        if env_path.is_file():
            pytesseract.pytesseract.tesseract_cmd = str(env_path)
            return True
        elif env_path.is_dir() and (env_path / "tesseract.exe").exists():
            pytesseract.pytesseract.tesseract_cmd = str(env_path / "tesseract.exe")
            return True

    # 2. Check standard Windows installation directories
    for candidate in TESSERACT_CANDIDATE_PATHS:
        if candidate.exists():
            pytesseract.pytesseract.tesseract_cmd = str(candidate)
            return True

    # 3. Check system PATH
    which_path = shutil.which("tesseract") or shutil.which("tesseract.exe")
    if which_path:
        pytesseract.pytesseract.tesseract_cmd = str(which_path)
        return True

    return False


def is_tesseract_available() -> bool:
    """Check if Tesseract OCR is available without raising."""
    try:
        return configure_tesseract()
    except Exception:
        return False


def extract_ocr_data(file_bytes: bytes) -> dict:
    """
    Extract text, bounding boxes, confidence scores, and dimensions from an image.
    Preserves original image pixel coordinates even if internal scaling was applied.
    Returns:
        {
            "text": str,
            "image_width": int,
            "image_height": int,
            "lines": list[dict],
            "words": list[dict],
            "all_ocr_bboxes": list[dict],
        }
    """
    if not configure_tesseract():
        raise RuntimeError(TESSERACT_INSTALL_GUIDE)

    if not file_bytes:
        raise ValueError("Uploaded image file is empty.")

    try:
        raw_image = Image.open(BytesIO(file_bytes))
    except Exception as error:
        raise ValueError(f"Failed to decode image file: {str(error)}")

    # Original dimensions
    orig_w, orig_h = raw_image.width, raw_image.height

    # Convert to RGB
    image = raw_image.convert("RGB")

    # Optimize resolution for OCR: scale up small images, maintain moderate resolution
    max_dimension = max(orig_w, orig_h)
    scale_factor = 1.0
    if max_dimension < 1200:
        scale_factor = 2.0
        new_size = (int(orig_w * scale_factor), int(orig_h * scale_factor))
        image = image.resize(new_size, Image.Resampling.LANCZOS)
    elif max_dimension > 3500:
        scale_factor = 3000.0 / max_dimension
        new_size = (int(orig_w * scale_factor), int(orig_h * scale_factor))
        image = image.resize(new_size, Image.Resampling.LANCZOS)

    # Convert to grayscale and enhance contrast for clearer text recognition
    gray_image = image.convert("L")
    enhanced_image = ImageEnhance.Contrast(gray_image).enhance(1.6)
    enhanced_image = enhanced_image.filter(ImageFilter.SHARPEN)

    def _run_ocr_data(target_img, psm_config=None):
        kwargs = {"output_type": pytesseract.Output.DICT}
        if psm_config:
            kwargs["config"] = psm_config
        return pytesseract.image_to_data(target_img, **kwargs)

    ocr_dict = None
    try:
        ocr_dict = _run_ocr_data(enhanced_image)
    except Exception as first_error:
        logger.debug("[DocuMind OCR] Default PSM failed, retrying with PSM 6: %s", first_error)
        try:
            ocr_dict = _run_ocr_data(enhanced_image, psm_config="--psm 6")
        except Exception as second_error:
            error_str = str(second_error)
            if "tesseract is not installed" in error_str.lower() or "not found" in error_str.lower():
                raise RuntimeError(TESSERACT_INSTALL_GUIDE)
            logger.warning("[DocuMind OCR] OCR processing failed: %s", error_str)

    has_words = False
    if ocr_dict and "text" in ocr_dict:
        has_words = any(bool(t.strip()) for t in ocr_dict["text"])

    if not has_words:
        try:
            fallback_dict = _run_ocr_data(gray_image)
            if fallback_dict and any(bool(t.strip()) for t in fallback_dict.get("text", [])):
                ocr_dict = fallback_dict
        except Exception:
            pass

    if not ocr_dict or "text" not in ocr_dict:
        return {
            "text": "",
            "image_width": orig_w,
            "image_height": orig_h,
            "lines": [],
            "words": [],
            "all_ocr_bboxes": [],
        }

    inv_scale = 1.0 / scale_factor
    n_boxes = len(ocr_dict["text"])

    words: list[dict] = []
    lines_map: dict[tuple[int, int, int], list[dict]] = {}

    for i in range(n_boxes):
        raw_text = ocr_dict["text"][i]
        token = raw_text.strip() if raw_text else ""
        if not token:
            continue

        raw_conf = ocr_dict["conf"][i]
        try:
            conf_val = float(raw_conf)
        except (ValueError, TypeError):
            conf_val = 0.0

        if conf_val < 0:
            conf_val = 0.0
        normalized_conf = round(min(1.0, conf_val / 100.0), 3)

        left = int(round(ocr_dict["left"][i] * inv_scale))
        top = int(round(ocr_dict["top"][i] * inv_scale))
        width = int(round(ocr_dict["width"][i] * inv_scale))
        height = int(round(ocr_dict["height"][i] * inv_scale))

        left = max(0, min(left, orig_w))
        top = max(0, min(top, orig_h))
        width = max(1, min(width, orig_w - left))
        height = max(1, min(height, orig_h - top))

        bbox = {"x": left, "y": top, "width": width, "height": height}

        block_num = int(ocr_dict.get("block_num", [0])[i])
        par_num = int(ocr_dict.get("par_num", [0])[i])
        line_num = int(ocr_dict.get("line_num", [0])[i])
        word_num = int(ocr_dict.get("word_num", [0])[i])

        word_data = {
            "text": token,
            "bbox": bbox,
            "confidence": normalized_conf,
            "block_num": block_num,
            "line_num": line_num,
            "word_num": word_num,
        }
        words.append(word_data)

        line_key = (block_num, par_num, line_num)
        if line_key not in lines_map:
            lines_map[line_key] = []
        lines_map[line_key].append(word_data)

    lines: list[dict] = []
    for line_key, line_words in lines_map.items():
        if not line_words:
            continue
        line_text = " ".join(w["text"] for w in line_words)
        min_x = min(w["bbox"]["x"] for w in line_words)
        min_y = min(w["bbox"]["y"] for w in line_words)
        max_x = max(w["bbox"]["x"] + w["bbox"]["width"] for w in line_words)
        max_y = max(w["bbox"]["y"] + w["bbox"]["height"] for w in line_words)
        avg_conf = round(sum(w["confidence"] for w in line_words) / len(line_words), 3)

        line_bbox = {
            "x": min_x,
            "y": min_y,
            "width": max(1, max_x - min_x),
            "height": max(1, max_y - min_y),
        }
        lines.append({
            "text": line_text,
            "bbox": line_bbox,
            "confidence": avg_conf,
            "block_num": line_key[0],
            "line_num": line_key[2],
            "words": [
                {"text": w["text"], "bbox": w["bbox"], "confidence": w["confidence"]}
                for w in line_words
            ],
        })

    all_ocr_bboxes = [line["bbox"] for line in lines]
    full_text = "\n".join(line["text"] for line in lines).strip()

    return {
        "text": full_text,
        "image_width": orig_w,
        "image_height": orig_h,
        "lines": lines,
        "words": words,
        "all_ocr_bboxes": all_ocr_bboxes,
    }


def extract_text_from_image(file_bytes: bytes) -> str:
    """
    Extract text from PNG, JPG, JPEG or WEBP image bytes using OCR.
    Maintains backward compatibility.
    """
    data = extract_ocr_data(file_bytes)
    return data.get("text", "")