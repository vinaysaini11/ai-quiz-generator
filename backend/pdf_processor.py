"""
PDF Processor Module for AI Quiz Generator.
Handles PDF file validation, page-by-page text extraction using pypdf,
and text cleaning with source page tracking.
"""
import os
import re
from typing import List, Dict, Any
from pypdf import PdfReader

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

class PDFProcessingError(Exception):
    """Custom exception for PDF processing issues."""
    pass

def clean_text(text: str) -> str:
    """Normalizes whitespace and removes non-printable characters."""
    if not text:
        return ""
    # Replace multiple newlines or spaces with a single whitespace
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()

def validate_pdf_header(filepath: str) -> None:
    """Verifies that the file begins with the standard PDF magic bytes '%PDF-'."""
    try:
        with open(filepath, "rb") as f:
            header = f.read(5)
        if header != b"%PDF-":
            raise PDFProcessingError(
                "Invalid file format: File header does not match PDF specification (%PDF-)."
            )
    except (OSError, IOError) as e:
        raise PDFProcessingError(f"Cannot read file header: {str(e)}") from e

def extract_text_from_pdf(filepath: str) -> Dict[str, Any]:
    """
    Extracts text page-by-page from a PDF file.
    Returns:
        Dict containing:
            - total_pages (int)
            - total_characters (int)
            - pages: List[Dict] with 'page_number' and 'text'
            - full_text: Combined cleaned string
    """
    if not os.path.exists(filepath):
        raise PDFProcessingError(f"File not found: {filepath}")

    file_size = os.path.getsize(filepath)
    if file_size > MAX_FILE_SIZE_BYTES:
        raise PDFProcessingError(
            f"File size ({file_size / (1024 * 1024):.1f}MB) exceeds maximum allowed limit of 10MB."
        )

    # Validate PDF magic bytes
    validate_pdf_header(filepath)

    try:
        reader = PdfReader(filepath)
    except Exception as e:
        raise PDFProcessingError(f"Failed to read PDF file. It may be corrupt or encrypted: {str(e)}") from e

    num_pages = len(reader.pages)
    if num_pages == 0:
        raise PDFProcessingError("The uploaded PDF has 0 pages.")

    pages_data: List[Dict[str, Any]] = []
    total_chars = 0
    full_text_parts: List[str] = []

    for idx, page in enumerate(reader.pages):
        page_num = idx + 1
        try:
            raw_text = page.extract_text() or ""
        except Exception:
            raw_text = ""

        cleaned = clean_text(raw_text)
        if cleaned:
            pages_data.append({
                "page_number": page_num,
                "text": cleaned,
                "char_count": len(cleaned)
            })
            total_chars += len(cleaned)
            full_text_parts.append(f"--- Page {page_num} ---\n{cleaned}")

    if total_chars < 50:
        raise PDFProcessingError(
            "The uploaded PDF contains very little or no extractable text. "
            "Please ensure the document contains searchable text (not scanned images)."
        )

    return {
        "total_pages": num_pages,
        "readable_pages": len(pages_data),
        "total_characters": total_chars,
        "pages": pages_data,
        "full_text": "\n\n".join(full_text_parts)
    }

