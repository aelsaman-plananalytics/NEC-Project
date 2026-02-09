"""
Stage 1: Low-level PDF extraction using PyMuPDF + Camelot.

Responsibilities:
- Load PDF
- Extract text per page
- Extract cleaned text
- Detect fonts, bold headers
- Extract tables using Camelot
"""

import re
from typing import List, Dict, Any, Optional
from pathlib import Path

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    fitz = None

try:
    import camelot
    CAMELOT_AVAILABLE = True
except ImportError:
    CAMELOT_AVAILABLE = False
    camelot = None


class PDFLoader:
    """
    Low-level PDF extraction using PyMuPDF for text and Camelot for tables.
    """
    
    def __init__(self):
        """Initialize PDF loader."""
        if not PYMUPDF_AVAILABLE:
            raise ImportError("PyMuPDF (fitz) is required. Install with: pip install PyMuPDF")
    
    def load_pdf(self, pdf_path: str) -> List[Dict[str, Any]]:
        """
        Load PDF and extract structured page data.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            List of page dictionaries:
            [
                {
                    "page": 1,
                    "text": "...",
                    "cleaned_text": "...",
                    "tables": [...],
                    "fonts": [...],
                    "bold_headers": [...]
                },
                ...
            ]
        """
        if not Path(pdf_path).exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        self.pdf_path = pdf_path  # Store for table extraction
        doc = fitz.open(pdf_path)
        pages = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_data = self._extract_page_data(page, page_num + 1, pdf_path)
            pages.append(page_data)
        
        doc.close()
        return pages
    
    def _extract_page_data(self, page: Any, page_number: int, pdf_path: str) -> Dict[str, Any]:
        """
        Extract data from a single page.
        
        Args:
            page: PyMuPDF page object
            page_number: Page number (1-based)
            pdf_path: Path to PDF file
            
        Returns:
            Dictionary with page data
        """
        # Extract text
        text = page.get_text()
        cleaned_text = self._clean_text(text)
        
        # Extract fonts and formatting
        fonts_info = self._extract_fonts(page)
        bold_headers = self._extract_bold_headers(page)
        
        # Extract tables using Camelot
        tables = self._extract_tables(page_number, page.rect, pdf_path)
        
        return {
            "page": page_number,
            "text": text,
            "cleaned_text": cleaned_text,
            "tables": tables,
            "fonts": fonts_info,
            "bold_headers": bold_headers,
            "width": page.rect.width,
            "height": page.rect.height,
        }
    
    def _clean_text(self, text: str) -> str:
        """
        Clean extracted text.
        
        Args:
            text: Raw text from PDF
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove page numbers at bottom
        text = re.sub(r'\n\s*\d+\s*\n', '\n', text)
        
        # Normalize line breaks
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()
    
    def _extract_fonts(self, page: Any) -> List[Dict[str, Any]]:
        """
        Extract font information from page.
        
        Args:
            page: PyMuPDF page object
            
        Returns:
            List of font dictionaries
        """
        fonts = []
        text_dict = page.get_text("dict")
        
        for block in text_dict.get("blocks", []):
            if "lines" not in block:
                continue
            
            for line in block["lines"]:
                for span in line.get("spans", []):
                    font_info = {
                        "font": span.get("font", ""),
                        "size": span.get("size", 0),
                        "flags": span.get("flags", 0),
                        "bold": bool(span.get("flags", 0) & 16),  # Flag 16 = bold
                        "text": span.get("text", ""),
                    }
                    fonts.append(font_info)
        
        return fonts
    
    def _extract_bold_headers(self, page: Any) -> List[str]:
        """
        Extract bold text that might be headers.
        
        Args:
            page: PyMuPDF page object
            
        Returns:
            List of bold header text
        """
        headers = []
        text_dict = page.get_text("dict")
        
        for block in text_dict.get("blocks", []):
            if "lines" not in block:
                continue
            
            for line in block["lines"]:
                line_text = ""
                is_bold = False
                
                for span in line.get("spans", []):
                    if span.get("flags", 0) & 16:  # Bold flag
                        is_bold = True
                    line_text += span.get("text", "")
                
                if is_bold and len(line_text.strip()) > 0:
                    headers.append(line_text.strip())
        
        return headers
    
    def _extract_tables(self, page_number: int, page_rect: Any, pdf_path: Optional[str] = None) -> List[List[List[str]]]:
        """
        Extract tables from page using Camelot.
        
        Args:
            page_number: Page number (1-based)
            page_rect: Page rectangle for area detection
            pdf_path: Path to PDF file (if available)
            
        Returns:
            List of tables, each as list of rows (list of cells)
        """
        if not CAMELOT_AVAILABLE or not pdf_path:
            return []
        
        try:
            # Use stream mode for better table detection
            tables = camelot.read_pdf(
                str(Path(pdf_path).resolve()),
                pages=str(page_number),
                flavor="stream",
                row_tol=10,
                column_tol=20,
            )
            
            extracted_tables = []
            for table in tables:
                df = table.df
                rows = df.values.tolist()
                # Clean cells
                cleaned_rows = [[str(cell).strip() for cell in row] for row in rows]
                extracted_tables.append(cleaned_rows)
            
            return extracted_tables
            
        except Exception as e:
            print(f"[PDFLoader] Table extraction failed for page {page_number}: {e}")
            return []
    
    def extract_full_text(self, pdf_path: str) -> str:
        """
        Extract full text from PDF (concatenated).
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Full text as string
        """
        pages = self.load_pdf(pdf_path)
        full_text = "\n\n".join([page["cleaned_text"] for page in pages])
        return full_text
