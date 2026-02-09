"""
Stage 3: High-level semantic extraction (LLM hybrid).

Collapses chunks into single clause bodies.
Runs GPT extraction request only when:
- clause content is ambiguous
- text short/empty
- numeric values missing

Returns normalized schema with confidence scoring.
"""

import os
import re
from typing import Dict, List, Optional, Any
from app.contract_parser.nec_schema import ClauseData, NECSchema
from app.contract_parser.utils import is_placeholder_value, normalize_clause_number

try:
    from openai import AzureOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    AzureOpenAI = None


class ClauseExtractor:
    """
    High-level semantic clause extraction with LLM fallback.
    """
    
    def __init__(self):
        """Initialize clause extractor."""
        self.llm_enabled = False
        self.azure_client = None
        
        # Initialize Azure OpenAI if available
        if OPENAI_AVAILABLE:
            azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
            azure_api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
            azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
            model_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini")
            
            if azure_endpoint and azure_api_key:
                try:
                    self.azure_client = AzureOpenAI(
                        api_key=azure_api_key,
                        api_version=azure_api_version,
                        azure_endpoint=azure_endpoint
                    )
                    self.llm_enabled = True
                    self.model_name = model_name
                    print(f"[ClauseExtractor] Azure OpenAI enabled (model: {model_name})")
                except Exception as e:
                    print(f"[ClauseExtractor] Warning: Azure OpenAI initialization failed: {e}")
    
    def extract_clauses(
        self,
        clause_chunks: List[Dict[str, Any]],
        pages: List[Dict[str, Any]],
        toc: Optional[Dict[str, int]] = None
    ) -> List[ClauseData]:
        """
        Extract clauses from detected chunks.
        
        Args:
            clause_chunks: List of clause chunks from ClauseDetector
            pages: List of page dictionaries from PDFLoader
            toc: Optional TOC dictionary
            
        Returns:
            List of ClauseData objects
        """
        # Group chunks by clause number
        clauses_by_number: Dict[str, List[Dict[str, Any]]] = {}
        for chunk in clause_chunks:
            clause_num = chunk.get("clause_number")
            if clause_num:
                if clause_num not in clauses_by_number:
                    clauses_by_number[clause_num] = []
                clauses_by_number[clause_num].append(chunk)
        
        extracted_clauses = []
        
        # Process each programme-critical clause
        for clause_num in NECSchema.PROGRAMME_CRITICAL_CLAUSES:
            chunks = clauses_by_number.get(clause_num, [])
            
            # Collapse chunks into single clause body
            clause_text = self._collapse_chunks(chunks)
            
            # Extract value
            value, source = self._extract_value(clause_num, clause_text, chunks, pages, toc)
            
            # Determine status
            status = self._determine_status(value)
            
            # Calculate confidence
            confidence = self._calculate_confidence(clause_num, value, status, chunks, toc)
            
            # Get title
            title = self._get_clause_title(clause_num, chunks)
            
            # Get page
            page = chunks[0].get("page_start") if chunks else None
            
            clause_data = ClauseData(
                clause_number=clause_num,
                title=title,
                value=value,
                status=status,
                confidence=confidence,
                page=page,
                source=source
            )
            
            extracted_clauses.append(clause_data)
        
        return extracted_clauses
    
    def _collapse_chunks(self, chunks: List[Dict[str, Any]]) -> str:
        """
        Collapse multiple chunks into single clause body.
        
        Args:
            chunks: List of clause chunks
            
        Returns:
            Combined clause text
        """
        if not chunks:
            return ""
        
        # Sort by page and position
        sorted_chunks = sorted(chunks, key=lambda x: (x.get("page_start", 0), x.get("position", 0)))
        
        # Combine text, removing duplicates
        texts = []
        seen_texts = set()
        
        for chunk in sorted_chunks:
            text = chunk.get("text", "").strip()
            if text and text not in seen_texts:
                texts.append(text)
                seen_texts.add(text)
        
        return " ".join(texts)
    
    def _extract_value(
        self,
        clause_num: str,
        clause_text: str,
        chunks: List[Dict[str, Any]],
        pages: List[Dict[str, Any]],
        toc: Optional[Dict[str, int]]
    ) -> tuple[str, str]:
        """
        Extract clause value using multiple strategies.
        
        Args:
            clause_num: Clause number
            clause_text: Combined clause text
            chunks: Clause chunks
            pages: Page data
            toc: TOC dictionary
            
        Returns:
            Tuple of (value, source)
        """
        # Strategy 1: Try table extraction
        value = self._extract_from_tables(clause_num, pages)
        if value and not is_placeholder_value(value):
            return value, "table"
        
        # Strategy 2: Try text extraction
        value = self._extract_from_text(clause_text, clause_num)
        if value and not is_placeholder_value(value):
            return value, "text"
        
        # Strategy 3: LLM extraction (if enabled and needed)
        if self.llm_enabled and (not clause_text or len(clause_text) < 50):
            value = self._extract_with_llm(clause_num, clause_text, pages)
            if value and not is_placeholder_value(value):
                return value, "llm"
        
        return "", "missing"
    
    def _extract_from_tables(self, clause_num: str, pages: List[Dict[str, Any]]) -> str:
        """Extract clause value from tables."""
        for page in pages:
            tables = page.get("tables", [])
            for table in tables:
                for row in table:
                    if len(row) >= 2:
                        left = str(row[0]).strip()
                        right = str(row[1]).strip()
                        
                        if clause_num in left or left.startswith(clause_num):
                            return right
        
        return ""
    
    def _extract_from_text(self, text: str, clause_num: str) -> str:
        """Extract clause value from text."""
        # Find clause number in text
        pattern = rf'\b{re.escape(clause_num)}\b'
        match = re.search(pattern, text, re.IGNORECASE)
        
        if not match:
            return ""
        
        # Extract text after clause number (next 200 chars)
        start = match.end()
        end = min(start + 200, len(text))
        
        value = text[start:end].strip()
        
        # Remove clause number if present
        value = re.sub(rf'\b{re.escape(clause_num)}\b', '', value).strip()
        
        # Remove common prefixes
        value = re.sub(r'^[:\-\.\s]+', '', value)
        
        return value[:100]  # Limit length
    
    def _extract_with_llm(
        self,
        clause_num: str,
        clause_text: str,
        pages: List[Dict[str, Any]]
    ) -> str:
        """Extract clause value using LLM."""
        if not self.azure_client:
            return ""
        
        try:
            # Get clause title
            title = self._get_clause_title(clause_num, [])
            
            prompt = f"""Extract the value for NEC clause {clause_num} ({title}) from the following text.

Text: {clause_text[:500]}

Return only the extracted value, or "Not Provided" if not found. Do not include explanations."""
            
            response = self.azure_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are an expert at extracting NEC contract clause values."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=100
            )
            
            value = response.choices[0].message.content.strip()
            
            # Clean LLM output
            if "not provided" in value.lower() or "not found" in value.lower():
                return ""
            
            return value
            
        except Exception as e:
            print(f"[ClauseExtractor] LLM extraction failed: {e}")
            return ""
    
    def _determine_status(self, value: str) -> str:
        """Determine clause status."""
        if not value or is_placeholder_value(value):
            return "blank"
        return "filled"
    
    def _calculate_confidence(
        self,
        clause_num: str,
        value: str,
        status: str,
        chunks: List[Dict[str, Any]],
        toc: Optional[Dict[str, int]]
    ) -> float:
        """Calculate confidence score."""
        confidence = 0.5
        
        # TOC match
        if toc and clause_num in toc:
            confidence += 0.2
        
        # Has value
        if status == "filled":
            confidence += 0.2
        
        # Has chunks
        if chunks:
            confidence += 0.1
        
        return min(1.0, confidence)
    
    def _get_clause_title(self, clause_num: str, chunks: List[Dict[str, Any]]) -> str:
        """Get clause title."""
        # Try to get from chunks
        for chunk in chunks:
            title = chunk.get("title", "")
            if title:
                return title
        
        # Default titles
        titles = {
            "3.1": "Starting Date",
            "3.2": "Possession Date(s)",
            "3.3": "Completion Date",
            "3.5": "First Programme Submission",
            "3.6": "Revised Programme Interval",
            "3.7": "Delay Damages",
            "4.1": "Defects Date",
            "4.2": "Defect Correction Period",
            "4.3": "Landscaping Maintenance Period",
            "5.2": "Assessment Interval",
            "5.3": "Payment Period",
            "5.5": "Retention Percentage",
            "5.6": "Bond Amount",
            "6.1": "Weather Recording Location",
            "6.2": "Weather Measurement Data",
            "6.3": "Historical Weather Records Source",
        }
        
        return titles.get(clause_num, "Unknown")
