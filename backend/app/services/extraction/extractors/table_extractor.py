"""
Table extraction module for NEC contracts.

Supports multiple extraction methods:
- Camelot for vector-based PDFs
- pdfplumber for fallback
- OCR for image-based pages
"""

import re
from typing import List, Dict, Optional, Any
from pathlib import Path

try:
    import camelot
    CAMELOT_AVAILABLE = True
except ImportError:
    CAMELOT_AVAILABLE = False
    camelot = None

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    pdfplumber = None

try:
    import pytesseract
    from PIL import Image
    import pdf2image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    pytesseract = None
    Image = None
    pdf2image = None

from app.services.extraction.extractors.utils_pdf import detect_page_type, detect_tables_on_page


class TableExtractor:
    """Extract tables from PDF documents using multiple methods."""
    
    def __init__(self):
        """Initialize table extractor with available libraries."""
        self.camelot_available = CAMELOT_AVAILABLE
        self.pdfplumber_available = PDFPLUMBER_AVAILABLE
        self.ocr_available = OCR_AVAILABLE
    
    def extract_tables_camelot(self, pdf_path: str, pages: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Extract tables using Camelot (best for vector PDFs).
        
        Args:
            pdf_path: Path to PDF file
            pages: Page range (e.g., "1-5" or "1,3,5") or None for all
            
        Returns:
            List of extracted tables
        """
        if not self.camelot_available:
            return []
        
        try:
            tables = camelot.read_pdf(pdf_path, pages=pages, flavor='lattice')
            
            extracted = []
            for idx, table in enumerate(tables):
                # Convert to list of lists
                data = table.df.values.tolist()
                
                extracted.append({
                    "method": "camelot",
                    "page": table.page,
                    "table_index": idx,
                    "accuracy": table.accuracy,
                    "data": data,
                    "rows": len(data),
                    "columns": len(data[0]) if data else 0
                })
            
            return extracted
        except Exception as e:
            print(f"[TABLE_EXTRACTOR] Camelot extraction failed: {str(e)}")
            return []
    
    def extract_tables_pdfplumber(self, pdf_path: str, page_num: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Extract tables using pdfplumber (fallback method).
        
        Args:
            pdf_path: Path to PDF file
            page_num: Specific page number (0-indexed) or None for all
            
        Returns:
            List of extracted tables
        """
        if not self.pdfplumber_available:
            return []
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                extracted = []
                pages_to_process = [page_num] if page_num is not None else range(len(pdf.pages))
                
                for page_idx in pages_to_process:
                    if page_idx >= len(pdf.pages):
                        continue
                    
                    page = pdf.pages[page_idx]
                    tables = page.extract_tables()
                    
                    for idx, table in enumerate(tables):
                        if table and len(table) > 0:
                            extracted.append({
                                "method": "pdfplumber",
                                "page": page_idx + 1,  # 1-indexed
                                "table_index": idx,
                                "data": table,
                                "rows": len(table),
                                "columns": len(table[0]) if table[0] else 0
                            })
                
                return extracted
        except Exception as e:
            print(f"[TABLE_EXTRACTOR] pdfplumber extraction failed: {str(e)}")
            return []
    
    def extract_tables_ocr(self, pdf_path: str, page_num: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Extract tables using OCR (for image-based PDFs).
        
        Args:
            pdf_path: Path to PDF file
            page_num: Specific page number (0-indexed) or None for all
            
        Returns:
            List of extracted tables (basic structure)
        """
        if not self.ocr_available:
            return []
        
        try:
            # Convert PDF pages to images
            if page_num is not None:
                images = pdf2image.convert_from_path(pdf_path, first_page=page_num+1, last_page=page_num+1)
            else:
                images = pdf2image.convert_from_path(pdf_path)
            
            extracted = []
            for page_idx, image in enumerate(images):
                # Extract text using OCR
                ocr_text = pytesseract.image_to_string(image)
                
                # Basic table detection (look for tabular patterns)
                lines = ocr_text.split('\n')
                table_data = []
                
                for line in lines:
                    # Check if line looks like table row (multiple columns separated by spaces/tabs)
                    if re.search(r'\s{2,}|\t', line):
                        row = re.split(r'\s{2,}|\t', line.strip())
                        if len(row) > 1:
                            table_data.append(row)
                
                if table_data:
                    extracted.append({
                        "method": "ocr",
                        "page": (page_num if page_num is not None else page_idx) + 1,
                        "table_index": 0,
                        "data": table_data,
                        "rows": len(table_data),
                        "columns": len(table_data[0]) if table_data else 0
                    })
            
            return extracted
        except Exception as e:
            print(f"[TABLE_EXTRACTOR] OCR extraction failed: {str(e)}")
            return []
    
    def extract_tables_hybrid(self, pdf_path: str) -> List[Dict[str, Any]]:
        """
        Extract tables using hybrid strategy (Camelot -> pdfplumber -> OCR).
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            List of all extracted tables with method information
        """
        all_tables = []
        
        # Get PDF info
        from app.services.extraction.extractors.utils_pdf import get_pdf_info
        pdf_info = get_pdf_info(pdf_path)
        total_pages = pdf_info.get("total_pages", 0)
        
        print(f"[TABLE_EXTRACTOR] Extracting tables from {total_pages} pages...")
        
        # Try Camelot first (best for vector PDFs)
        if self.camelot_available:
            print(f"[TABLE_EXTRACTOR] Attempting Camelot extraction...")
            camelot_tables = self.extract_tables_camelot(pdf_path)
            if camelot_tables:
                print(f"[TABLE_EXTRACTOR] Camelot found {len(camelot_tables)} tables")
                all_tables.extend(camelot_tables)
        
        # Fallback to pdfplumber for pages without Camelot tables
        if self.pdfplumber_available:
            print(f"[TABLE_EXTRACTOR] Attempting pdfplumber extraction...")
            pdfplumber_tables = self.extract_tables_pdfplumber(pdf_path)
            if pdfplumber_tables:
                print(f"[TABLE_EXTRACTOR] pdfplumber found {len(pdfplumber_tables)} tables")
                # Only add tables from pages not already covered by Camelot
                camelot_pages = {t["page"] for t in all_tables if t.get("method") == "camelot"}
                for table in pdfplumber_tables:
                    if table["page"] not in camelot_pages:
                        all_tables.append(table)
        
        # OCR fallback for image-based pages
        if self.ocr_available:
            # Detect image pages
            for page_num in range(total_pages):
                page_type = detect_page_type(pdf_path, page_num)
                if page_type == "image":
                    print(f"[TABLE_EXTRACTOR] OCR extraction for image page {page_num + 1}...")
                    ocr_tables = self.extract_tables_ocr(pdf_path, page_num)
                    if ocr_tables:
                        all_tables.extend(ocr_tables)
        
        print(f"[TABLE_EXTRACTOR] Total tables extracted: {len(all_tables)}")
        return all_tables
    
    def parse_drawings_table(self, table_data: List[List[str]]) -> List[Dict[str, str]]:
        """
        Parse Schedule of Drawings table into structured format.
        
        Args:
            table_data: Raw table data (list of rows)
            
        Returns:
            List of drawing reference dictionaries
        """
        drawings = []
        
        if not table_data or len(table_data) < 2:
            return drawings
        
        # Try to identify header row
        header_row = None
        for idx, row in enumerate(table_data[:3]):  # Check first 3 rows
            row_lower = ' '.join(str(cell).lower() for cell in row if cell)
            if any(keyword in row_lower for keyword in ['number', 'title', 'scale', 'status', 'rev']):
                header_row = idx
                break
        
        # Map column indices
        if header_row is not None:
            headers = [str(cell).lower().strip() if cell else "" for cell in table_data[header_row]]
            start_row = header_row + 1
        else:
            # Assume standard format: Size, Number, Rev, Title, Scale, Status
            headers = ["size", "number", "revision", "title", "scale", "status"]
            start_row = 1
        
        # Find column indices
        col_map = {}
        for header in ["size", "number", "rev", "revision", "title", "scale", "status", "series"]:
            for idx, h in enumerate(headers):
                if header in h:
                    col_map[header] = idx
                    break
        
        # Parse data rows
        for row in table_data[start_row:]:
            if not any(cell and str(cell).strip() for cell in row):
                continue  # Skip empty rows
            
            drawing = {}
            
            # Extract fields
            if "size" in col_map:
                drawing["size"] = str(row[col_map["size"]]).strip() if col_map["size"] < len(row) else ""
            if "number" in col_map:
                drawing["number"] = str(row[col_map["number"]]).strip() if col_map["number"] < len(row) else ""
            if "revision" in col_map or "rev" in col_map:
                rev_idx = col_map.get("revision") or col_map.get("rev")
                if rev_idx is not None and rev_idx < len(row):
                    drawing["revision"] = str(row[rev_idx]).strip()
            if "title" in col_map:
                drawing["title"] = str(row[col_map["title"]]).strip() if col_map["title"] < len(row) else ""
            if "scale" in col_map:
                drawing["scale"] = str(row[col_map["scale"]]).strip() if col_map["scale"] < len(row) else ""
            if "status" in col_map:
                drawing["status"] = str(row[col_map["status"]]).strip() if col_map["status"] < len(row) else ""
            if "series" in col_map:
                drawing["series"] = str(row[col_map["series"]]).strip() if col_map["series"] < len(row) else ""
            
            # Only add if we have at least a number or title
            if drawing.get("number") or drawing.get("title"):
                drawings.append(drawing)
        
        return drawings



