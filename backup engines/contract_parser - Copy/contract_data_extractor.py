"""
NEC4 Contract Data Part One Extractor (Label-Based).

Extracts programme-critical fields from real-world NEC4 ECC contracts using
exact label pattern matching. Does NOT rely on clause numbers.

Works with:
- Addingham Lower Gauge Fish Pass NEC4 ECC
- Anderby Creek Piling NEC4 ECC
- KSL Rec Package NEC4 ECC
"""

import re
from typing import Dict, List, Any, Optional
from app.contract_parser.nec_value_extractor import NECValueExtractor


class ContractDataExtractor:
    """
    Extracts NEC4 Contract Data Part One fields using label-based patterns.
    
    Uses exact NEC4 label text to find and extract literal values.
    Never relies on clause numbers.
    """
    
    # Exact NEC4 label patterns (case-insensitive)
    LABEL_PATTERNS = {
        "starting_date": [
            r"The\s+starting\s+date\s+is\s+(.+?)(?:\.|$|\n)",
            r"Starting\s+Date\s+is\s+(.+?)(?:\.|$|\n)",
            r"The\s+Starting\s+Date\s+is\s+(.+?)(?:\.|$|\n)",
        ],
        "access_dates": [
            r"The\s+access\s+dates?\s+are\s+(.+?)(?:\.|$|\n)",
            r"Access\s+Date[s]?\s+is\s+(.+?)(?:\.|$|\n)",
            r"Access\s+to\s+the\s+Site\s+is\s+(.+?)(?:\.|$|\n)",
        ],
        "completion_date": [
            r"The\s+Completion\s+Date\s+for\s+the\s+whole\s+of\s+the\s+works\s+is\s+(.+?)(?:\.|$|\n)",
            r"Completion\s+Date\s+for\s+the\s+whole\s+of\s+the\s+works\s+is\s+(.+?)(?:\.|$|\n)",
            r"The\s+Completion\s+Date\s+is\s+(.+?)(?:\.|$|\n)",
        ],
        "first_programme_submission": [
            r"The\s+period\s+after\s+the\s+Contract\s+Date\s+within\s+which\s+the\s+Contractor\s+is\s+to\s+submit\s+a\s+first\s+programme\s+for\s+acceptance\s+is\s+(.+?)(?:\.|$|\n)",
            r"first\s+programme\s+for\s+acceptance\s+is\s+(.+?)(?:\.|$|\n)",
            r"submit\s+a\s+first\s+programme\s+within\s+(.+?)(?:\.|$|\n)",
        ],
        "revised_programme_interval": [
            r"The\s+Contractor\s+submits\s+revised\s+programmes\s+at\s+intervals\s+no\s+longer\s+than\s+(.+?)(?:\.|$|\n)",
            r"revised\s+programmes\s+at\s+intervals\s+no\s+longer\s+than\s+(.+?)(?:\.|$|\n)",
            r"revised\s+programmes\s+every\s+(.+?)(?:\.|$|\n)",
        ],
        "defects_date": [
            r"The\s+period\s+between\s+Completion\s+of\s+the\s+whole\s+of\s+the\s+works\s+and\s+the\s+defects\s+date\s+is\s+(.+?)(?:\.|$|\n)",
            r"defects\s+date\s+is\s+(.+?)(?:\.|$|\n)",
            r"Defects\s+Date\s+is\s+(.+?)(?:\.|$|\n)",
        ],
        "defect_correction_period": [
            r"The\s+defect\s+correction\s+period\s+is\s+(.+?)(?:\.|$|\n)",
            r"defect\s+correction\s+period\s+is\s+(.+?)(?:\.|$|\n)",
        ],
        "delay_damages": [
            r"Delay\s+damages\s+(.+?)(?:\.|$|\n)",
            r"Option\s+X7[^\n]*\n(.+?)(?:\.|$|\n)",
        ],
        "assessment_interval": [
            r"The\s+assessment\s+interval\s+is\s+(.+?)(?:\.|$|\n)",
            r"assessment\s+interval\s+is\s+(.+?)(?:\.|$|\n)",
        ],
        "interest_rate": [
            r"The\s+interest\s+rate\s+is\s+(.+?)(?:\.|$|\n)",
            r"interest\s+rate\s+is\s+(.+?)(?:\.|$|\n)",
        ],
        "weather_recording_location": [
            r"The\s+place\s+where\s+weather\s+is\s+to\s+be\s+recorded\s+is\s+(.+?)(?:\.|$|\n)",
            r"place\s+where\s+weather\s+is\s+recorded\s+is\s+(.+?)(?:\.|$|\n)",
        ],
        "weather_measurement_supplier": [
            r"The\s+weather\s+measurements\s+are\s+supplied\s+by\s+(.+?)(?:\.|$|\n)",
            r"weather\s+measurements\s+are\s+supplied\s+by\s+(.+?)(?:\.|$|\n)",
        ],
        "weather_historical_source": [
            r"The\s+weather\s+data\s+are\s+the\s+records\s+of\s+past\s+weather\s+measurement[^\n]*recorded\s+at\s+(.+?)\s+available\s+from\s+(.+?)(?:\.|$|\n)",
            r"weather\s+data\s+are\s+the\s+records[^\n]*available\s+from\s+(.+?)(?:\.|$|\n)",
            r"historical\s+records\s+from\s+(.+?)(?:\.|$|\n)",
        ],
    }
    
    def __init__(self, debug: bool = False):
        """Initialize contract data extractor."""
        self.debug = debug
        self.value_extractor = NECValueExtractor(debug=debug)
        
        # Compile patterns
        self.compiled_patterns = {}
        for field, patterns in self.LABEL_PATTERNS.items():
            self.compiled_patterns[field] = [
                re.compile(pattern, re.IGNORECASE | re.DOTALL) for pattern in patterns
            ]
    
    def log(self, msg: str):
        """Log debug message."""
        if self.debug:
            print(f"[ContractDataExtractor] {msg}")
    
    def extract(self, clean_text: str) -> Dict[str, Any]:
        """
        Extract all Contract Data Part One fields from text.
        
        Args:
            clean_text: Full clean text from PDF
            
        Returns:
            Dictionary with extracted contract data (literal values only)
        """
        self.log("Starting Contract Data Part One extraction (label-based)")
        
        result = {
            "starting_date": self._extract_field("starting_date", clean_text),
            "access_dates": self._extract_access_dates(clean_text),
            "completion_date": self._extract_field("completion_date", clean_text),
            "first_programme_submission": self._extract_field("first_programme_submission", clean_text),
            "revised_programme_interval": self._extract_field("revised_programme_interval", clean_text),
            "defects_date": self._extract_field("defects_date", clean_text),
            "defect_correction_period": self._extract_field("defect_correction_period", clean_text),
            "delay_damages": self._extract_delay_damages(clean_text),
            "assessment_interval": self._extract_field("assessment_interval", clean_text),
            "interest_rate": self._extract_field("interest_rate", clean_text),
            "weather_recording_location": self._extract_field("weather_recording_location", clean_text),
            "weather_measurement_supplier": self._extract_field("weather_measurement_supplier", clean_text),
            "weather_historical_source": self._extract_weather_historical_source(clean_text),
        }
        
        # Build structured output matching expected format
        structured_result = {
            "contract_dates": {
                "starting_date": result["starting_date"],
                "access_dates": result["access_dates"],
                "completion_date": result["completion_date"],
                "programme_submission_rules": result["first_programme_submission"],
                "programme_revision_rules": result["revised_programme_interval"]
            },
            "programme_requirements": {
                "submit_first_programme_within": result["first_programme_submission"],
                "revised_programme_interval": result["revised_programme_interval"]
            },
            "defects": {
                "defects_date": result["defects_date"],
                "defect_correction_period": result["defect_correction_period"]
            },
            "delay_damages": result["delay_damages"].get("description", "") if isinstance(result["delay_damages"], dict) else result["delay_damages"],
            "delay_damages_amount": result["delay_damages"].get("amount", "") if isinstance(result["delay_damages"], dict) else "",
            "payment_terms": {
                "assessment_interval": result["assessment_interval"],
                "interest_rate": result["interest_rate"]
            },
            "weather_data": {
                "recording_location": result["weather_recording_location"],
                "measurement_data": result["weather_measurement_supplier"],
                "historical_records_source": result["weather_historical_source"]
            },
            "metadata": {
                "extraction_method": "contract_data_extractor_label_based"
            }
        }
        
        return structured_result
    
    def _extract_field(self, field_name: str, text: str) -> str:
        """
        Extract a single field using label patterns.
        
        Args:
            field_name: Name of field to extract
            text: Full text to search
            
        Returns:
            Literal value only (cleaned and trimmed)
        """
        if field_name not in self.compiled_patterns:
            return ""
        
        patterns = self.compiled_patterns[field_name]
        
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                raw_value = match.group(1).strip()
                self.log(f"Found raw value for {field_name}: {raw_value[:100]}")
                
                # Use NECValueExtractor to extract literal value
                literal_value = self.value_extractor.extract(field_name, raw_value)
                
                if literal_value:
                    # Additional cleaning
                    literal_value = self._clean_value(literal_value)
                    self.log(f"Extracted {field_name}: {literal_value}")
                    return literal_value
        
        return ""
    
    def _extract_access_dates(self, text: str) -> List[str]:
        """Extract access dates (may be multiple)."""
        access_dates = []
        
        for pattern in self.compiled_patterns.get("access_dates", []):
            match = pattern.search(text)
            if match:
                raw_value = match.group(1).strip()
                self.log(f"Found raw access dates: {raw_value[:100]}")
                
                # Extract literal value
                literal_value = self.value_extractor.extract("access_date", raw_value)
                
                if literal_value:
                    # Parse multiple dates
                    dates = self._parse_multiple_dates(literal_value)
                    access_dates.extend(dates)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_dates = []
        for date in access_dates:
            if date not in seen:
                seen.add(date)
                unique_dates.append(date)
        
        return unique_dates
    
    def _extract_delay_damages(self, text: str) -> Dict[str, Any]:
        """Extract delay damages."""
        delay_damages = {
            "description": "",
            "amount": ""
        }
        
        for pattern in self.compiled_patterns.get("delay_damages", []):
            match = pattern.search(text)
            if match:
                raw_value = match.group(1).strip()
                self.log(f"Found raw delay damages: {raw_value[:100]}")
                
                # Extract literal value
                literal_value = self.value_extractor.extract("delay_damages", raw_value)
                
                if literal_value:
                    delay_damages["description"] = self._clean_value(literal_value)
                    
                    # Try to extract amount
                    amount_match = re.search(r'([£$€]?\s*\d[\d,\.]*)\s*(per|a)\s*(day|week|month)', literal_value, re.IGNORECASE)
                    if amount_match:
                        delay_damages["amount"] = amount_match.group(0).strip()
                    
                    break
        
        return delay_damages
    
    def _extract_weather_historical_source(self, text: str) -> str:
        """Extract weather historical records source (complex pattern)."""
        for pattern in self.compiled_patterns.get("weather_historical_source", []):
            match = pattern.search(text)
            if match:
                # Pattern may have multiple groups
                if match.lastindex >= 2:
                    # Use the "available from" part (last group)
                    raw_value = match.group(match.lastindex).strip()
                else:
                    raw_value = match.group(1).strip()
                
                self.log(f"Found raw weather source: {raw_value[:100]}")
                
                # Extract literal value
                literal_value = self.value_extractor.extract("weather_historical_source", raw_value)
                
                if literal_value:
                    return self._clean_value(literal_value)
        
        return ""
    
    def _parse_multiple_dates(self, value: str) -> List[str]:
        """Parse multiple dates from string."""
        if not value:
            return []
        
        # Split by comma, semicolon, or "and"
        dates = re.split(r'[,;]|\s+and\s+', value)
        cleaned_dates = []
        
        for date in dates:
            cleaned = self._clean_value(date.strip())
            if cleaned:
                cleaned_dates.append(cleaned)
        
        return cleaned_dates
    
    def _clean_value(self, value: str) -> str:
        """
        Clean extracted value by removing:
        - Trailing labels
        - Bullet points
        - Duplicate values (e.g., "0 20 March 2023" → "20 March 2023")
        - Leading zeros before dates
        - Extra whitespace
        """
        if not value:
            return ""
        
        # Remove bullet points
        value = re.sub(r'^[\u2022\u2023\u25E6\u2043\-\*]\s*', '', value)
        
        # Remove leading zeros before dates (e.g., "0 20 March 2023" → "20 March 2023")
        # Handle various formats
        value = re.sub(r'^0\s+(\d{1,2}\s+\w+\s+\d{4})', r'\1', value)
        value = re.sub(r'^0\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', r'\1', value)
        # Also handle "0 20" at start of line
        value = re.sub(r'^0\s+(\d{1,2})\s+(\w+\s+\d{4})', r'\1 \2', value)
        
        # Remove trailing labels (common NEC4 phrases that might be captured)
        trailing_labels = [
            r'\s+after\s+Completion\s*$',
            r'\s+after\s+the\s+Contract\s+Date\s*$',
            r'\s+from\s+the\s+Contract\s+Date\s*$',
        ]
        for label_pattern in trailing_labels:
            value = re.sub(label_pattern, '', value, flags=re.IGNORECASE)
        
        # Collapse whitespace
        value = re.sub(r'\s+', ' ', value)
        
        # Remove trailing punctuation (except % and currency symbols)
        value = re.sub(r'[^\w\s\-/%,£$€]+$', '', value)
        
        return value.strip()
