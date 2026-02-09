"""
Label-based fallback extractor for Contract Data Part One.

Used as second-stage extraction to fill gaps after table extraction.
Extracts from clean text using label patterns.
"""

import re
from typing import Dict, List, Any, Optional


class LabelFallbackExtractor:
    """
    Label-based extractor for filling gaps after table extraction.
    
    Scans clean_text for NEC labels and extracts values using pattern:
    LABEL <newline> <value until next blank line>
    """
    
    # Label patterns (case-insensitive, flexible spacing)
    LABEL_PATTERNS = {
        "3.1": [
            r"Starting\s+Date[:\-–]?\s*(.+)",
            r"Start\s+Date[:\-–]?\s*(.+)",
        ],
        "3.2": [
            r"Access\s+Date[s]?[:\-–]?\s*(.+)",
            r"Possession\s+Date[s]?[:\-–]?\s*(.+)",
        ],
        "3.3": [
            r"Completion\s+Date[:\-–]?\s*(.+)",
            r"Date\s+of\s+Completion[:\-–]?\s*(.+)",
        ],
        "3.5": [
            r"First\s+programme\s+to\s+be\s+submitted[:\-–]?\s*(.+)",
            r"Period\s+for\s+reply[:\-–]?\s*(.+)",
        ],
        "3.6": [
            r"Revised\s+programme[s]?\s+every[:\-–]?\s*(.+)",
            r"Programme\s+submission\s+interval[:\-–]?\s*(.+)",
        ],
        "3.7": [
            r"Delay\s+damages[:\-–]?\s*(.+)",
            r"Damages\s+for\s+late\s+Completion[:\-–]?\s*(.+)",
        ],
        "4.1": [
            r"Defects\s+Date[:\-–]?\s*(.+)",
        ],
        "4.2": [
            r"Defect\s+Correction\s+Period[:\-–]?\s*(.+)",
        ],
        "4.3": [
            r"Landscaping\s+Maintenance\s+Period[:\-–]?\s*(.+)",
        ],
        "5.2": [
            r"Assessment\s+Interval[:\-–]?\s*(.+)",
        ],
        "5.3": [
            r"Payment\s+Period[:\-–]?\s*(.+)",
        ],
        "5.5": [
            r"Retention[:\-–]?\s*(.+)",
        ],
        "5.6": [
            r"Bond\s+Amount[:\-–]?\s*(.+)",
            r"Performance\s+Bond[:\-–]?\s*(.+)",
        ],
        "6.1": [
            r"Weather\s+Recording\s+Location[:\-–]?\s*(.+)",
            r"Weather\s+recorded\s+at[:\-–]?\s*(.+)",
        ],
        "6.2": [
            r"Weather\s+Measurement\s+Data[:\-–]?\s*(.+)",
        ],
        "6.3": [
            r"Weather\s+Historical\s+Records[:\-–]?\s*(.+)",
        ],
    }
    
    def __init__(self, debug: bool = False):
        """Initialize label extractor."""
        self.debug = debug
        self.compiled_patterns = {}
        for clause_num, patterns in self.LABEL_PATTERNS.items():
            self.compiled_patterns[clause_num] = [
                re.compile(pattern, re.IGNORECASE | re.MULTILINE)
                for pattern in patterns
            ]
    
    def log(self, msg: str):
        """Log debug message."""
        if self.debug:
            print(f"[LabelExtractor] {msg}")
    
    def extract(self, clean_text: str, existing_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract fields from clean_text using label patterns.
        Only fills fields that are missing in existing_results.
        
        Args:
            clean_text: Full clean text from PDF
            existing_results: Results from table extraction (only fill missing fields)
            
        Returns:
            Dictionary of extracted fields (only for missing clauses)
        """
        results = {}
        
        for clause_num, patterns in self.compiled_patterns.items():
            # Only extract if field is missing
            if clause_num in existing_results and existing_results[clause_num].get("status") != "missing":
                continue
            
            # Try each pattern
            for pattern in patterns:
                match = pattern.search(clean_text)
                if match:
                    value = match.group(1).strip()
                    value = self._clean_value(value)
                    
                    if value and len(value) > 0:
                        results[clause_num] = {
                            "value": value,
                            "status": "filled",
                            "title": existing_results.get(clause_num, {}).get("title", "")
                        }
                        self.log(f"Label extraction filled {clause_num}: {value[:80]}")
                        break
        
        return results
    
    def _clean_value(self, value: str) -> str:
        """Clean extracted value."""
        if not value:
            return ""
        
        # Remove corrupted fragments
        value = re.sub(r'\s+', ' ', value)
        value = value.strip()
        
        # Remove single-word fragments
        words = value.split()
        if len(words) == 1:
            word = words[0]
            corrupted = ["is", "of", "the", "a", "an", "and", "or", "but"]
            if word.lower() in corrupted:
                return ""
            if re.match(r'^[A-Z]\d+$', word) and len(word) < 5:
                return ""
        
        # Remove leading/trailing punctuation
        value = re.sub(r'^[^\w]+|[^\w]+$', '', value)
        
        return value.strip()
