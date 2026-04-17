"""
OCR Engine
Extracts text from PDF and image invoice files using Tesseract + pdf2image.
Falls back to pypdf but NEVER returns empty text.
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class OCREngine:
    def __init__(self):
        self._tesseract_available = self._check_tesseract()
        self._pdf2image_available = self._check_pdf2image()

    def _check_tesseract(self) -> bool:
        try:
            import pytesseract

            tesseract_paths = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                "tesseract",
            ]

            for path in tesseract_paths:
                if os.path.exists(path) or path == "tesseract":
                    pytesseract.pytesseract.tesseract_cmd = path
                    break

            pytesseract.get_tesseract_version()
            logger.info("✅ Tesseract OCR available.")
            return True

        except Exception as e:
            logger.error("❌ Tesseract not available: %s", e)
            return False

    def _check_pdf2image(self) -> bool:
        try:
            import pdf2image  # noqa
            logger.info("✅ pdf2image available.")
            return True
        except ImportError:
            logger.error("❌ pdf2image not available.")
            return False

    def extract_text(self, file_path: str) -> str:
        """Extract text from a PDF or image file."""
        ext = Path(file_path).suffix.lower()

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        logger.info("📄 Processing file: %s", file_path)

        if ext == ".pdf":
            text = self._extract_from_pdf(file_path)
        elif ext in {".png", ".jpg", ".jpeg"}:
            text = self._extract_from_image(file_path)
        else:
            raise ValueError(f"Unsupported file type: {ext}")

        # 🚨 NEVER allow empty text
        if not text or not text.strip():
            logger.error("❌ No text extracted from document")
            raise ValueError("OCR failed: No text extracted from document")

        logger.info("✅ Extraction successful. Characters: %d", len(text))
        return text

    def _extract_from_pdf(self, file_path: str) -> str:
        # Try OCR first
        if self._pdf2image_available and self._tesseract_available:
            try:
                return self._pdf_via_tesseract(file_path)
            except Exception as e:
                logger.error("❌ Tesseract PDF failed: %s", e)

        # Fallback: pypdf
        try:
            text = self._pdf_via_pypdf(file_path)

            if not text.strip():
                raise ValueError("pypdf extracted empty text")

            return text

        except Exception as e:
            logger.error("❌ pypdf extraction failed: %s", e)
            raise ValueError("Failed to extract text from PDF")

    def _pdf_via_tesseract(self, file_path: str) -> str:
        from pdf2image import convert_from_path
        import pytesseract

        poppler_path = None
        windows_poppler_paths = [
            r"C:\poppler\Library\bin",
            r"C:\poppler\bin",
            r"C:\Program Files\poppler\bin",
        ]

        for p in windows_poppler_paths:
            if os.path.isdir(p):
                poppler_path = p
                break

        logger.info("🔍 Using poppler path: %s", poppler_path)

        try:
            if poppler_path:
                images = convert_from_path(file_path, poppler_path=poppler_path)
            else:
                images = convert_from_path(file_path)

        except Exception as e:
            raise RuntimeError("Poppler not installed or not in PATH") from e

        text = ""
        for i, img in enumerate(images):
            logger.info("🧠 OCR processing page %d", i + 1)
            page_text = pytesseract.image_to_string(img)
            text += page_text

        if not text.strip():
            raise ValueError("OCR returned empty text from PDF")

        return text

    def _pdf_via_pypdf(self, file_path: str) -> str:
        try:
            from pypdf import PdfReader
        except ImportError:
            try:
                from PyPDF2 import PdfReader
            except ImportError:
                raise ImportError("Neither pypdf nor PyPDF2 is installed.")

        reader = PdfReader(file_path)
        text = ""

        for i, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            logger.info("📘 pypdf page %d chars: %d", i + 1, len(page_text))
            text += page_text

        return text

    def _extract_from_image(self, file_path: str) -> str:
        if not self._tesseract_available:
            raise RuntimeError("Tesseract is required for image OCR")

        import pytesseract
        from PIL import Image

        img = Image.open(file_path)
        text = pytesseract.image_to_string(img)

        if not text.strip():
            raise ValueError("OCR returned empty text from image")

        logger.info("🖼️ Image OCR extracted %d chars", len(text))
        return text


# Singleton instance
ocr_engine = OCREngine()