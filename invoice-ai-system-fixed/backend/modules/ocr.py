"""
Production OCR engine for invoice PDFs and images.

The public contract is intentionally small: callers use
``ocr_engine.extract_text(file_path)`` and receive raw invoice text or a
ProcessingStageError. Upload, extraction, validation, and database code stay
outside this module.
"""

from __future__ import annotations

import logging
import os
import re
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageOps

from utils.error_handling import ProcessingStageError, log_stage

logger = logging.getLogger(__name__)


TESSERACT_CONFIGS = (
    ("psm6", "--oem 3 --psm 6"),
    ("psm11", "--oem 3 --psm 11"),
    ("psm4", "--oem 3 --psm 4"),
)
MIN_READABLE_CHARS = 1
ALMOST_NO_TEXT_CHARS = 40


@dataclass
class OCRAttempt:
    page_number: int
    variant: str
    config_name: str
    text: str
    confidence: float
    elapsed_ms: int
    error: str | None = None

    @property
    def readable_chars(self) -> int:
        return readable_char_count(self.text)


def readable_char_count(text: str) -> int:
    """Count OCR output that looks useful enough for invoice extraction."""
    return len(re.findall(r"[A-Za-z0-9]", text or ""))


def normalize_text(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", (text or "").strip())


def is_readable(text: str, minimum: int = MIN_READABLE_CHARS) -> bool:
    return readable_char_count(text) >= minimum


class OCREngine:
    def __init__(self):
        self._tesseract_available = self._check_tesseract()
        self._pdf2image_available = self._check_pdf2image()

    @log_stage("OCR", "OCR engine missing")
    def _check_tesseract(self) -> bool:
        try:
            import pytesseract

            configured = os.getenv("TESSERACT_CMD")
            tesseract_paths = [
                configured,
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                "tesseract",
            ]

            for path in filter(None, tesseract_paths):
                if path == "tesseract" or os.path.exists(path):
                    pytesseract.pytesseract.tesseract_cmd = path
                    break

            pytesseract.get_tesseract_version()
            logger.info("Tesseract OCR available.")
            return True
        except Exception as exc:
            logger.exception("OCR engine missing: %s", exc)
            traceback.print_exc()
            return False

    @log_stage("PDF to image conversion", "PDF conversion failed")
    def _check_pdf2image(self) -> bool:
        try:
            import pdf2image  # noqa: F401

            logger.info("pdf2image available.")
            return True
        except Exception as exc:
            logger.exception("pdf2image unavailable: %s", exc)
            traceback.print_exc()
            return False

    @log_stage("OCR")
    def extract_text(self, file_path: str) -> str:
        """Extract invoice text from a PDF or image without changing API shape."""
        ext = Path(file_path).suffix.lower()

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        logger.info("Processing file for OCR: %s", file_path)

        if ext == ".pdf":
            text = self._extract_from_pdf(file_path)
        elif ext in {".png", ".jpg", ".jpeg"}:
            text = self._extract_from_image(file_path)
        else:
            raise ProcessingStageError("File upload", f"Unsupported file type: {ext}")

        text = normalize_text(text)
        if not is_readable(text):
            raise ProcessingStageError(
                "OCR",
                "No readable text after all attempts",
                "Every OCR attempt returned empty or unreadable text.",
            )

        logger.info("OCR extraction successful. Characters: %d", len(text))
        return text

    def _extract_from_pdf(self, file_path: str) -> str:
        embedded_text = self._extract_embedded_pdf_text(file_path)
        if is_readable(embedded_text):
            logger.info(
                "Embedded PDF text detected; skipping OCR. Characters: %d",
                len(embedded_text),
            )
            return embedded_text

        if not self._pdf2image_available:
            raise ProcessingStageError(
                "PDF to image conversion",
                "PDF conversion failed",
                "pdf2image is not installed or could not be imported.",
            )
        if not self._tesseract_available:
            raise ProcessingStageError(
                "OCR",
                "OCR engine missing",
                "Tesseract executable was not found. Install Tesseract or set TESSERACT_CMD.",
            )

        images = self._convert_pdf_to_images(file_path)
        page_texts: list[str] = []
        all_attempts: list[OCRAttempt] = []

        for page_number, image in enumerate(images, start=1):
            page_text, page_attempts = self._ocr_image_page(image, page_number=page_number)
            all_attempts.extend(page_attempts)
            if is_readable(page_text):
                page_texts.append(page_text)
            else:
                logger.warning("Page %d produced no readable OCR text", page_number)

        text = normalize_text("\n\n".join(page_texts))
        if is_readable(text):
            return text

        details = self._attempt_error_summary(all_attempts)
        raise ProcessingStageError(
            "OCR",
            "No readable text after all attempts",
            details or "All pages were processed, but no readable text was found.",
        )

    def _extract_embedded_pdf_text(self, file_path: str) -> str:
        """Use PDF text layers first so OCR is only used for scanned documents."""
        text_parts: list[str] = []
        pdfplumber_error: Exception | None = None

        try:
            import pdfplumber

            with pdfplumber.open(file_path) as pdf:
                for index, page in enumerate(pdf.pages, start=1):
                    start = time.perf_counter()
                    page_text = page.extract_text() or ""
                    elapsed_ms = int((time.perf_counter() - start) * 1000)
                    logger.info(
                        "PDF embedded text page=%d length=%d confidence=n/a time_ms=%d engine=pdfplumber",
                        index,
                        len(page_text),
                        elapsed_ms,
                    )
                    text_parts.append(page_text)
        except Exception as exc:
            pdfplumber_error = exc
            logger.exception("pdfplumber embedded text extraction failed: %s", exc)
            traceback.print_exc()

        text = normalize_text("\n\n".join(text_parts))
        if is_readable(text):
            return text

        try:
            import fitz  # PyMuPDF

            fitz_parts: list[str] = []
            with fitz.open(file_path) as doc:
                for index, page in enumerate(doc, start=1):
                    start = time.perf_counter()
                    page_text = page.get_text("text") or ""
                    elapsed_ms = int((time.perf_counter() - start) * 1000)
                    logger.info(
                        "PDF embedded text page=%d length=%d confidence=n/a time_ms=%d engine=pymupdf",
                        index,
                        len(page_text),
                        elapsed_ms,
                    )
                    fitz_parts.append(page_text)
            return normalize_text("\n\n".join(fitz_parts))
        except Exception as exc:
            logger.exception("PyMuPDF embedded text extraction failed: %s", exc)
            traceback.print_exc()
            if pdfplumber_error:
                logger.debug("pdfplumber also failed: %s", pdfplumber_error)
            return ""

    @log_stage("PDF to image conversion", "PDF conversion failed")
    def _convert_pdf_to_images(self, file_path: str) -> list[Image.Image]:
        from pdf2image import convert_from_path

        poppler_path = self._find_poppler_path()
        logger.info("Converting PDF to images at 300 DPI. poppler_path=%s", poppler_path)

        try:
            kwargs = {"dpi": 300}
            if poppler_path:
                kwargs["poppler_path"] = poppler_path
            images = convert_from_path(file_path, **kwargs)
            logger.info("PDF conversion complete. Pages: %d", len(images))
            return images
        except Exception as exc:
            logger.exception("PDF conversion failed with complete exception: %s", exc)
            traceback.print_exc()
            raise ProcessingStageError(
                "PDF to image conversion",
                "PDF conversion failed",
                str(exc),
            ) from exc

    def _find_poppler_path(self) -> str | None:
        configured = os.getenv("POPPLER_PATH")
        candidates = [
            configured,
            r"C:\poppler\poppler-25.12.0\Library\bin",
            r"C:\poppler\Library\bin",
            r"C:\poppler\bin",
            r"C:\Program Files\poppler\bin",
        ]
        for path in filter(None, candidates):
            if os.path.isdir(path):
                return path
        return None

    def _extract_from_image(self, file_path: str) -> str:
        if not self._tesseract_available:
            raise ProcessingStageError(
                "OCR",
                "OCR engine missing",
                "Tesseract executable was not found. Install Tesseract or set TESSERACT_CMD.",
            )

        try:
            with Image.open(file_path) as image:
                text, attempts = self._ocr_image_page(image.copy(), page_number=1)
        except ProcessingStageError:
            raise
        except Exception as exc:
            logger.exception("Image loading failed: %s", exc)
            traceback.print_exc()
            raise ProcessingStageError("OCR", "Image preprocessing failed", str(exc)) from exc

        if is_readable(text):
            return text

        details = self._attempt_error_summary(attempts)
        raise ProcessingStageError(
            "OCR",
            "No readable text after all attempts",
            details or "Image was processed, but no readable text was found.",
        )

    def _ocr_image_page(self, image: Image.Image, page_number: int) -> tuple[str, list[OCRAttempt]]:
        try:
            variants = self._preprocess_variants(image)
        except Exception as exc:
            logger.exception("Image preprocessing failed on page %d: %s", page_number, exc)
            traceback.print_exc()
            raise ProcessingStageError("OCR", "Image preprocessing failed", str(exc)) from exc

        attempts: list[OCRAttempt] = []
        best = OCRAttempt(page_number, "none", "none", "", 0.0, 0)

        for variant_name, variant_image in variants:
            variant_attempts = self._run_tesseract_fallbacks(
                variant_image,
                page_number=page_number,
                variant_name=variant_name,
            )
            attempts.extend(variant_attempts)
            for attempt in variant_attempts:
                if attempt.readable_chars > best.readable_chars:
                    best = attempt

        logger.info(
            "Best OCR page=%d variant=%s config=%s length=%d readable=%d confidence=%.2f time_ms=%d",
            page_number,
            best.variant,
            best.config_name,
            len(best.text),
            best.readable_chars,
            best.confidence,
            best.elapsed_ms,
        )
        return normalize_text(best.text), attempts

    def _preprocess_variants(self, image: Image.Image) -> list[tuple[str, Image.Image]]:
        try:
            import cv2
            import numpy as np
        except ImportError as exc:
            logger.warning("OpenCV preprocessing unavailable; using PIL fallback: %s", exc)
            return self._preprocess_variants_pil(image)

        base = ImageOps.exif_transpose(image).convert("RGB")
        cv_image = cv2.cvtColor(np.array(base), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        gray = self._resize_if_small(gray)

        denoised = cv2.fastNlMeansDenoising(gray, None, h=30, templateWindowSize=7, searchWindowSize=21)

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        contrast = clahe.apply(denoised)

        threshold = cv2.adaptiveThreshold(
            contrast,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            11,
        )

        deskewed_threshold = self._deskew(threshold)
        deskewed_contrast = self._deskew(contrast)

        return [
            ("grayscale_resized", self._to_pil(gray)),
            ("denoised", self._to_pil(denoised)),
            ("contrast", self._to_pil(contrast)),
            ("adaptive_threshold", self._to_pil(threshold)),
            ("deskewed_contrast", self._to_pil(deskewed_contrast)),
            ("deskewed_threshold", self._to_pil(deskewed_threshold)),
        ]

    def _preprocess_variants_pil(self, image: Image.Image) -> list[tuple[str, Image.Image]]:
        base = ImageOps.exif_transpose(image).convert("RGB")
        gray = ImageOps.grayscale(base)
        gray = self._resize_pil_if_small(gray)
        contrast = ImageOps.autocontrast(gray)
        threshold = contrast.point(lambda pixel: 255 if pixel > 180 else 0)
        inverted_threshold = ImageOps.invert(threshold)
        return [
            ("pil_grayscale", gray),
            ("pil_autocontrast", contrast),
            ("pil_threshold", threshold),
            ("pil_inverted_threshold", inverted_threshold),
        ]

    def _resize_pil_if_small(self, image: Image.Image) -> Image.Image:
        width, height = image.size
        min_side = min(width, height)
        if min_side >= 1200:
            return image
        scale = min(3.0, 1200 / max(min_side, 1))
        new_size = (int(width * scale), int(height * scale))
        logger.debug("Resizing small PIL image from %sx%s to %sx%s", width, height, *new_size)
        return image.resize(new_size, Image.Resampling.BICUBIC)

    def _resize_if_small(self, gray_image):
        import cv2

        height, width = gray_image.shape[:2]
        min_side = min(width, height)
        if min_side >= 1200:
            return gray_image

        scale = min(3.0, 1200 / max(min_side, 1))
        new_size = (int(width * scale), int(height * scale))
        logger.debug("Resizing small image from %sx%s to %sx%s", width, height, *new_size)
        return cv2.resize(gray_image, new_size, interpolation=cv2.INTER_CUBIC)

    def _deskew(self, image):
        import cv2
        import numpy as np

        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        inverted = cv2.bitwise_not(gray)
        coords = np.column_stack(np.where(inverted > 0))
        if coords.size == 0:
            return image

        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle

        if abs(angle) < 0.5 or abs(angle) > 15:
            return image

        height, width = image.shape[:2]
        center = (width // 2, height // 2)
        matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        return cv2.warpAffine(
            image,
            matrix,
            (width, height),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )

    def _to_pil(self, image) -> Image.Image:
        return Image.fromarray(image)

    def _run_tesseract_fallbacks(
        self,
        image: Image.Image,
        page_number: int,
        variant_name: str,
    ) -> list[OCRAttempt]:
        attempts: list[OCRAttempt] = []

        first_attempt = self._run_tesseract(
            image,
            page_number=page_number,
            variant_name=variant_name,
            config_name=TESSERACT_CONFIGS[0][0],
            config=TESSERACT_CONFIGS[0][1],
        )
        attempts.append(first_attempt)

        if first_attempt.readable_chars >= ALMOST_NO_TEXT_CHARS:
            return attempts

        for config_name, config in TESSERACT_CONFIGS[1:]:
            attempts.append(
                self._run_tesseract(
                    image,
                    page_number=page_number,
                    variant_name=variant_name,
                    config_name=config_name,
                    config=config,
                )
            )

        return attempts

    def _run_tesseract(
        self,
        image: Image.Image,
        page_number: int,
        variant_name: str,
        config_name: str,
        config: str,
    ) -> OCRAttempt:
        import pytesseract
        from pytesseract import Output

        start = time.perf_counter()
        try:
            data = pytesseract.image_to_data(image, config=config, output_type=Output.DICT)
            text = self._text_from_tesseract_data(data)
            confidence = self._average_confidence(data.get("conf", []))
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            attempt = OCRAttempt(
                page_number=page_number,
                variant=variant_name,
                config_name=config_name,
                text=text,
                confidence=confidence,
                elapsed_ms=elapsed_ms,
            )
        except pytesseract.TesseractNotFoundError as exc:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            logger.exception("OCR engine missing on page %d: %s", page_number, exc)
            traceback.print_exc()
            raise ProcessingStageError(
                "OCR",
                "OCR engine missing",
                "Tesseract executable was not found. Install Tesseract or set TESSERACT_CMD.",
            ) from exc
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            logger.exception(
                "Tesseract attempt failed page=%d variant=%s config=%s: %s",
                page_number,
                variant_name,
                config_name,
                exc,
            )
            traceback.print_exc()
            attempt = OCRAttempt(
                page_number=page_number,
                variant=variant_name,
                config_name=config_name,
                text="",
                confidence=0.0,
                elapsed_ms=elapsed_ms,
                error=str(exc),
            )

        logger.info(
            "OCR attempt page=%d variant=%s config=%s length=%d readable=%d confidence=%.2f time_ms=%d",
            attempt.page_number,
            attempt.variant,
            attempt.config_name,
            len(attempt.text),
            attempt.readable_chars,
            attempt.confidence,
            attempt.elapsed_ms,
        )
        return attempt

    def _average_confidence(self, values: Iterable[object]) -> float:
        confidences: list[float] = []
        for value in values:
            try:
                confidence = float(value)
            except (TypeError, ValueError):
                continue
            if confidence >= 0:
                confidences.append(confidence)
        if not confidences:
            return 0.0
        return sum(confidences) / len(confidences)

    def _text_from_tesseract_data(self, data: dict) -> str:
        rows: dict[tuple[int, int, int], list[tuple[int, str]]] = {}
        texts = data.get("text", [])
        lefts = data.get("left", [])
        block_nums = data.get("block_num", [])
        par_nums = data.get("par_num", [])
        line_nums = data.get("line_num", [])

        for index, raw_word in enumerate(texts):
            word = (raw_word or "").strip()
            if not word:
                continue
            key = (
                int(block_nums[index]) if index < len(block_nums) else 0,
                int(par_nums[index]) if index < len(par_nums) else 0,
                int(line_nums[index]) if index < len(line_nums) else index,
            )
            left = int(lefts[index]) if index < len(lefts) else index
            rows.setdefault(key, []).append((left, word))

        lines = [
            " ".join(word for _, word in sorted(words, key=lambda item: item[0]))
            for _, words in sorted(rows.items(), key=lambda item: item[0])
        ]
        return "\n".join(lines)

    def _attempt_error_summary(self, attempts: list[OCRAttempt]) -> str:
        errors = [attempt.error for attempt in attempts if attempt.error]
        if errors:
            return "; ".join(errors[-5:])
        if attempts:
            best = max(attempts, key=lambda item: item.readable_chars)
            return (
                f"Best attempt page={best.page_number} variant={best.variant} "
                f"config={best.config_name} readable_chars={best.readable_chars} "
                f"confidence={best.confidence:.2f}."
            )
        return ""


ocr_engine = OCREngine()
