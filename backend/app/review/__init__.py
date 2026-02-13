"""
Programme Review Pack: read-only presentation and decision layer.

Assembles a single payload from stored submission and acceptance only.
No validation, no inference, no UI.
"""

from app.review.programme_review_pack import build_programme_review_pack
from app.review.pdf_export_builder import build_pdf_export_input
from app.review.pdf_export_contract import (
    PDF_EXPORT_SECTION_ORDER,
    REVIEW_PACK_REQUIRED_KEYS,
)

__all__ = [
    "build_programme_review_pack",
    "build_pdf_export_input",
    "PDF_EXPORT_SECTION_ORDER",
    "REVIEW_PACK_REQUIRED_KEYS",
]
