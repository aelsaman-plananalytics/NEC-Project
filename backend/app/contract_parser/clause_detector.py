"""
Stage 2: Clause Detection.

Identifies clause headings using:
- regex patterns
- font-weight detection
- indentation patterns
- TOC lookup

Tags every line as: heading, body, or noise.
Produces clause chunks with page spans.
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from app.contract_parser.utils import normalize_clause_number


class ClauseDetector:
    """
    Detects clause boundaries and headings in PDF text.
    """
    
    # Clause number patterns
    CLAUSE_PATTERN = re.compile(r'\b(\d+\.\d+(?:\.\d+)?)\b')
    
    # Common clause titles (for validation)
    COMMON_TITLES = [
        "starting date", "completion date", "possession date",
        "defects date", "defect correction period",
        "assessment interval", "payment period", "retention",
        "weather", "programme", "delay damages"
    ]
    
    def __init__(self):
        """Initialize clause detector."""
        pass
    
    def detect_clauses(
        self,
        pages: List[Dict[str, Any]],
        toc: Optional[Dict[str, int]] = None
    ) -> List[Dict[str, Any]]:
        """
        Detect clause boundaries across pages.
        
        Args:
            pages: List of page dictionaries from PDFLoader
            toc: Optional TOC dictionary mapping clause numbers to page numbers
            
        Returns:
            List of clause chunks:
            [
                {
                    "clause_number": "3.1",
                    "title": "Starting Date",
                    "page_start": 1,
                    "page_end": 1,
                    "text": "...",
                    "type": "heading|body|noise",
                    "confidence": 0.95
                },
                ...
            ]
        """
        clauses = []
        
        for page_idx, page in enumerate(pages):
            text = page.get("cleaned_text", "")
            bold_headers = page.get("bold_headers", [])
            
            # Find clause numbers in text
            clause_matches = self._find_clause_matches(text, bold_headers)
            
            for match in clause_matches:
                clause_num = normalize_clause_number(match["clause_number"])
                if not clause_num:
                    continue
                
                # Extract clause text
                clause_text = self._extract_clause_text(
                    text,
                    match["position"],
                    page_idx + 1
                )
                
                # Determine clause type
                clause_type = self._classify_clause_type(
                    clause_text,
                    match["is_bold"],
                    match["is_header"]
                )
                
                # Calculate confidence
                confidence = self._calculate_confidence(
                    clause_num,
                    clause_text,
                    clause_type,
                    toc
                )
                
                clause_chunk = {
                    "clause_number": clause_num,
                    "title": match.get("title", ""),
                    "page_start": page_idx + 1,
                    "page_end": page_idx + 1,
                    "text": clause_text,
                    "type": clause_type,
                    "confidence": confidence,
                }
                
                clauses.append(clause_chunk)
        
        return clauses
    
    def _find_clause_matches(
        self,
        text: str,
        bold_headers: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Find clause number matches in text.
        
        Args:
            text: Page text
            bold_headers: List of bold header text
            
        Returns:
            List of match dictionaries
        """
        matches = []
        
        # Search for clause patterns
        for match in self.CLAUSE_PATTERN.finditer(text):
            clause_num = match.group(1)
            position = match.start()
            
            # Check if it's in bold headers
            is_bold = any(clause_num in header for header in bold_headers)
            
            # Extract potential title (next 50 chars)
            title_candidate = text[position:position + 100].strip()
            title = self._extract_title(title_candidate, clause_num)
            
            matches.append({
                "clause_number": clause_num,
                "position": position,
                "is_bold": is_bold,
                "is_header": is_bold or position < 200,  # Early in page = likely header
                "title": title,
            })
        
        return matches
    
    def _extract_title(self, text: str, clause_num: str) -> str:
        """
        Extract clause title from text.
        
        Args:
            text: Text containing clause
            clause_num: Clause number
            
        Returns:
            Extracted title
        """
        # Remove clause number
        text = text.replace(clause_num, "").strip()
        
        # Extract first meaningful phrase (up to 50 chars)
        words = text.split()[:10]
        title = " ".join(words)
        
        # Clean up
        title = re.sub(r'[^\w\s]', '', title)
        title = title.strip()
        
        return title[:50] if title else ""
    
    def _extract_clause_text(
        self,
        text: str,
        start_pos: int,
        page_num: int
    ) -> str:
        """
        Extract clause text starting from position.
        
        Args:
            text: Full page text
            start_pos: Start position of clause
            page_num: Page number
            
        Returns:
            Extracted clause text
        """
        # Extract next 500 characters or until next clause
        end_pos = min(start_pos + 500, len(text))
        
        # Stop at next clause number
        next_match = self.CLAUSE_PATTERN.search(text[start_pos + 10:end_pos])
        if next_match:
            end_pos = start_pos + 10 + next_match.start()
        
        return text[start_pos:end_pos].strip()
    
    def _classify_clause_type(
        self,
        text: str,
        is_bold: bool,
        is_header: bool
    ) -> str:
        """
        Classify clause type.
        
        Args:
            text: Clause text
            is_bold: Whether text is bold
            is_header: Whether it's a header position
            
        Returns:
            "heading", "body", or "noise"
        """
        if is_bold and is_header and len(text) < 100:
            return "heading"
        
        if len(text) < 20:
            return "noise"
        
        # Check for meaningful content
        if re.search(r'\d+', text) or len(text.split()) > 5:
            return "body"
        
        return "noise"
    
    def _calculate_confidence(
        self,
        clause_num: str,
        text: str,
        clause_type: str,
        toc: Optional[Dict[str, int]]
    ) -> float:
        """
        Calculate confidence score for clause detection.
        
        Args:
            clause_num: Clause number
            text: Clause text
            clause_type: Type classification
            toc: Optional TOC reference
            
        Returns:
            Confidence score (0.0 to 1.0)
        """
        confidence = 0.5  # Base confidence
        
        # TOC match increases confidence
        if toc and clause_num in toc:
            confidence += 0.3
        
        # Body type is more confident than noise
        if clause_type == "body":
            confidence += 0.2
        elif clause_type == "noise":
            confidence -= 0.3
        
        # Text length affects confidence
        if len(text) > 50:
            confidence += 0.1
        elif len(text) < 20:
            confidence -= 0.2
        
        # Contains numbers/dates
        if re.search(r'\d+', text):
            confidence += 0.1
        
        return max(0.0, min(1.0, confidence))
