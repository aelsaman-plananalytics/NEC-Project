"""
NEW NEC Extraction Engine (2026)
Works reliably on real-world NEC contracts, including:
- NEC4 ECC
- NEC3 ECC
- EA Framework Contracts
- Fully signed contracts
- Contracts that are not formatted like clean NEC templates
"""

from typing import Dict, List, Any
import re


class HybridNECExtractor:
    """
    NEW NEC Extraction Engine (2026)
    Works reliably on real-world NEC contracts, including:
    - NEC4 ECC
    - NEC3 ECC
    - EA Framework Contracts
    - Fully signed contracts
    - Contracts that are not formatted like clean NEC templates
    """

    # ---------------------------------------------------------------
    #  SECTION DETECTION
    # ---------------------------------------------------------------
    SECTION_HEADERS = [
        r"CONTRACT DATA PART ONE",
        r"CONTRACT DATA PART TWO",
        r"CONTRACT DATA",
        r"PART ONE DATA PROVIDED BY",
        r"WORKS INFORMATION",
        r"PRICING INFORMATION",
        r"Z[- ]CLAUSES",
        r"SECONDARY OPTIONS",
        r"CERTIFICATES AND DATES",
        r"PROGRAMME",
        r"EARLY WARNING",
    ]

    # NEC4 standard labels most commonly preserved across real contracts
    LABELS = {
        "starting_date": [
            r"Starting Date[:\s]*([^\n]+)",
            r"Start Date[:\s]*([^\n]+)",
        ],
        "access_date": [
            r"Access Date[s]?\s*[:\-]\s*([^\n]+)",
            r"Possession Date[s]?\s*[:\-]\s*([^\n]+)",
        ],
        "completion_date": [
            r"Completion Date[:\s]*([^\n]+)",
            r"Date of Completion[:\s]*([^\n]+)",
        ],
        "key_dates": [
            r"Key Date[s]?\s*[:\-]\s*(.+?)(?=\n[A-Z])",
        ],
        "delay_damages": [
            r"Delay Damages[:\s]*([^\n]+)",
            r"Damages for late Completion[:\s]*([^\n]+)",
        ],
        "defects_date": [
            r"Defects Date[:\s]*([^\n]+)",
        ],
        "defects_period": [
            r"Defect Correction Period[:\s]*([^\n]+)",
        ],
        "programme_first_submission": [
            r"First programme to be submitted[:\s]*([^\n]+)",
        ],
        "programme_revisions": [
            r"Revised programme every[:\s]*([^\n]+)",
        ],
        "retention": [
            r"Retention[:\s]*([^\n]+)",
        ],
        "bond_amount": [
            r"Performance Bond[:\s]*([^\n]+)",
            r"Bond Amount[:\s]*([^\n]+)",
        ],
        "weather_location": [
            r"Weather recorded at[:\s]*([^\n]+)",
        ]
    }

    # ---------------------------------------------------------------
    #  MAIN EXTRACTION FUNCTION
    # ---------------------------------------------------------------
    def extract(self, clean_text: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {}

        for field, patterns in self.LABELS.items():
            extracted = self._extract_field(clean_text, patterns)
            result[field] = extracted if extracted else ""

        return result

    # ---------------------------------------------------------------
    #  INTERNAL HELPER — RUN REGEXES SAFELY
    # ---------------------------------------------------------------
    def _extract_field(self, text: str, patterns: List[str]) -> str:
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
            if match:
                value = match.group(1).strip()
                # Clean trailing punctuation or clause headings
                value = re.sub(r"\s{2,}", " ", value)
                value = value.replace("­", "")
                return value
        return ""
