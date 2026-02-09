"""
Document parsers.

Contains:
- PDFParser: PDF document parsing
- XERParser: Primavera XER file parsing (if available)
"""

from app.services.parsing.parsers.pdf_parser import DocumentParser as PDFParser

# XERParser is optional - only import if the file has the class
try:
    from app.services.parsing.parsers.xer_parser import XERParser
    __all__ = ["PDFParser", "XERParser"]
except ImportError:
    # XERParser not implemented yet
    XERParser = None
    __all__ = ["PDFParser"]

