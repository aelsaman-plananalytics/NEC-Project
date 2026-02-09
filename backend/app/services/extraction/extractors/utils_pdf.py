"""
PDF utility functions for page type detection and text extraction.

Handles detection of vector vs image pages, table detection,
and page-level text extraction.
"""

import pdfplumber
from typing import List, Dict, Tuple, Optional
from pathlib import Path


def detect_page_type(pdf_path: str, page_num: int) -> str:
    """
    Detect if a PDF page is vector-based, image-based, or mixed.
    
    Args:
        pdf_path: Path to PDF file
        page_num: Page number (0-indexed)
        
    Returns:
        "vector", "image", or "mixed"
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if page_num >= len(pdf.pages):
                return "unknown"
            
            page = pdf.pages[page_num]
            
            # Check for text objects
            has_text = bool(page.chars) and len(page.chars) > 10
            
            # Check for images
            has_images = bool(page.images) and len(page.images) > 0
            
            if has_text and not has_images:
                return "vector"
            elif has_images and not has_text:
                return "image"
            elif has_text and has_images:
                return "mixed"
            else:
                return "unknown"
    except Exception:
        return "unknown"


def extract_text_from_page(pdf_path: str, page_num: int) -> str:
    """
    Extract text from a specific PDF page using pdfplumber.
    
    Args:
        pdf_path: Path to PDF file
        page_num: Page number (0-indexed)
        
    Returns:
        Extracted text
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if page_num >= len(pdf.pages):
                return ""
            
            page = pdf.pages[page_num]
            text = page.extract_text()
            return text if text else ""
    except Exception:
        return ""


def detect_tables_on_page(pdf_path: str, page_num: int) -> List[Dict]:
    """
    Detect tables on a PDF page using pdfplumber.
    
    Args:
        pdf_path: Path to PDF file
        page_num: Page number (0-indexed)
        
    Returns:
        List of detected table dictionaries
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if page_num >= len(pdf.pages):
                return []
            
            page = pdf.pages[page_num]
            tables = page.extract_tables()
            
            if not tables:
                return []
            
            # Convert to structured format
            detected_tables = []
            for idx, table in enumerate(tables):
                if table and len(table) > 0:
                    detected_tables.append({
                        "table_index": idx,
                        "rows": len(table),
                        "columns": len(table[0]) if table[0] else 0,
                        "data": table
                    })
            
            return detected_tables
    except Exception:
        return []


def get_pdf_info(pdf_path: str) -> Dict[str, any]:
    """
    Get basic information about a PDF file.
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        Dictionary with PDF metadata
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            return {
                "total_pages": len(pdf.pages),
                "metadata": pdf.metadata or {}
            }
    except Exception:
        return {
            "total_pages": 0,
            "metadata": {}
        }


def extract_all_text(pdf_path: str) -> str:
    """
    Extract all text from PDF using pdfplumber.
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        Complete extracted text
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            all_text = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    all_text.append(text)
            return '\n'.join(all_text)
    except Exception:
        return ""



