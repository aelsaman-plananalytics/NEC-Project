"""
NEC4 Contract Data Part One Extractor.

Extracts fields from real NEC4 ECC contracts using exact label matching.
Works with EA-standard NEC4 formatting found in:
- Anderby Creek Piling NEC4 ECC
- Addingham Lower Gauge Fish Pass NEC4 ECC
- KSL Rec Package NEC4 ECC

This extractor does NOT use clause numbers (3.1, 3.2, etc.) as these do not appear
in real NEC4 Contract Data Part One documents.
"""

import re
from typing import Dict, List, Any, Optional, Tuple


class NEC4CDPartOneExtractor:
    """
    Extractor for NEC4 Contract Data Part One using exact label matching.
    
    Searches for real NEC4 field labels exactly as written in EA-standard contracts.
    """
    
    # NEC4 Contract Data Part One labels (exact matches, case-insensitive)
    FIELD_LABELS = {
        # Dates (Clause 3)
        "starting_date": [
            r"The\s+starting\s+date\s+is\s+(.+?)(?:\.|\n|$)",
            r"Starting\s+date\s+is\s+(.+?)(?:\.|\n|$)",
        ],
        "access_date": [
            r"The\s+access\s+date\s+is\s+(.+?)(?:\.|\n|$)",
            r"The\s+access\s+dates\s+are\s+(.+?)(?:\.|\n|$)",
            r"Access\s+date[s]?\s+is\s+(.+?)(?:\.|\n|$)",
        ],
        "completion_date": [
            r"The\s+Completion\s+Date\s+for\s+the\s+whole\s+of\s+the\s+works\s+is\s+(.+?)(?:\.|\n|$)",
            r"Completion\s+Date\s+for\s+the\s+whole\s+of\s+the\s+works\s+is\s+(.+?)(?:\.|\n|$)",
            r"The\s+completion\s+date\s+is\s+(.+?)(?:\.|\n|$)",
        ],
        
        # Programme requirements
        "submit_first_programme_within": [
            r"The\s+period\s+after\s+the\s+Contract\s+Date\s+within\s+which\s+the\s+Contractor\s+is\s+to\s+submit\s+a\s+first\s+programme\s+is\s+(.+?)(?:\.|\n|$)",
            r"period\s+after\s+the\s+Contract\s+Date\s+within\s+which\s+the\s+Contractor\s+is\s+to\s+submit\s+a\s+first\s+programme\s+is\s+(.+?)(?:\.|\n|$)",
            r"first\s+programme\s+is\s+to\s+be\s+submitted\s+within\s+(.+?)(?:\.|\n|$)",
        ],
        "revised_programme_interval": [
            r"The\s+Contractor\s+submits\s+revised\s+programmes\s+at\s+intervals\s+no\s+longer\s+than\s+(.+?)(?:\.|\n|$)",
            r"Contractor\s+submits\s+revised\s+programmes\s+at\s+intervals\s+no\s+longer\s+than\s+(.+?)(?:\.|\n|$)",
            r"revised\s+programmes\s+at\s+intervals\s+no\s+longer\s+than\s+(.+?)(?:\.|\n|$)",
        ],
        
        # Delay damages
        "delay_damages": [
            r"Delay\s+damages\s+for\s+Completion\s+of\s+the\s+whole\s+of\s+the\s+works\s+are\s+(.+?)(?:\.|\n|$)",
            r"Delay\s+damages\s+for\s+Completion\s+are\s+(.+?)(?:\.|\n|$)",
            r"Delay\s+damages\s+are\s+(.+?)(?:\.|\n|$)",
        ],
        
        # Defects
        "defects_date": [
            r"The\s+period\s+between\s+Completion\s+of\s+the\s+whole\s+of\s+the\s+works\s+and\s+the\s+defects\s+date\s+is\s+(.+?)(?:\.|\n|$)",
            r"period\s+between\s+Completion\s+and\s+the\s+defects\s+date\s+is\s+(.+?)(?:\.|\n|$)",
            r"defects\s+date\s+is\s+(.+?)(?:\.|\n|$)",
        ],
        "defect_correction_period": [
            r"The\s+defect\s+correction\s+period\s+is\s+(.+?)(?:\.|\n|$)",
            r"defect\s+correction\s+period\s+is\s+(.+?)(?:\.|\n|$)",
        ],
        
        # Payment
        "assessment_interval": [
            r"The\s+assessment\s+interval\s+is\s+(.+?)(?:\.|\n|$)",
            r"assessment\s+interval\s+is\s+(.+?)(?:\.|\n|$)",
        ],
        "payment_period": [
            r"The\s+period\s+for\s+payment\s+is\s+(.+?)(?:\.|\n|$)",
            r"period\s+for\s+payment\s+is\s+(.+?)(?:\.|\n|$)",
        ],
        "retention_percentage": [
            r"Retention\s+is\s+(.+?)(?:\.|\n|$)",
            r"The\s+retention\s+is\s+(.+?)(?:\.|\n|$)",
        ],
        
        # Weather data
        "weather_recording_location": [
            r"The\s+place\s+where\s+weather\s+is\s+to\s+be\s+recorded\s+is\s+(.+?)(?:\.|\n|$)",
            r"place\s+where\s+weather\s+is\s+to\s+be\s+recorded\s+is\s+(.+?)(?:\.|\n|$)",
            r"weather\s+is\s+to\s+be\s+recorded\s+at\s+(.+?)(?:\.|\n|$)",
        ],
        "weather_measurement_data": [
            r"The\s+weather\s+measurements\s+are\s+(.+?)(?:\.|\n|$)",
            r"weather\s+measurements\s+are\s+(.+?)(?:\.|\n|$)",
        ],
        "weather_historical_records_source": [
            r"The\s+weather\s+data\s+are\s+the\s+records\s+of\s+the\s+(.+?)(?:\.|\n|$)",
            r"weather\s+data\s+are\s+the\s+records\s+of\s+the\s+(.+?)(?:\.|\n|$)",
        ],
    }
    
    def __init__(self, debug: bool = False):
        """Initialize NEC4 extractor."""
        self.debug = debug
        self.compiled_patterns = {}
        for field_name, patterns in self.FIELD_LABELS.items():
            self.compiled_patterns[field_name] = [
                re.compile(pattern, re.IGNORECASE | re.DOTALL | re.MULTILINE)
                for pattern in patterns
            ]
    
    def log(self, msg: str):
        """Log debug message."""
        if self.debug:
            print(f"[NEC4Extractor] {msg}")
    
    def extract(self, clean_text: str) -> Dict[str, Any]:
        """
        Extract all NEC4 Contract Data Part One fields from clean text.
        
        Args:
            clean_text: Full clean text from PDF
            
        Returns:
            Dictionary with structure:
            {
                "contract_dates": {...},
                "programme_requirements": {...},
                "delay_damages": ...,
                "defects": {...},
                "payment_terms": {...},
                "weather_data": {...},
                "extracted_fields": {...},
                "completeness": {...}
            }
        """
        self.log("Starting NEC4 Contract Data Part One extraction")
        
        extracted_fields = {}
        
        # Extract each field
        for field_name, patterns in self.compiled_patterns.items():
            value = ""
            status = "missing"
            
            # Try each pattern for this field
            for pattern in patterns:
                match = pattern.search(clean_text)
                if match:
                    # Label found - extract value
                    raw_value = match.group(1).strip()
                    value = self._normalize_value(raw_value)
                    
                    if value and len(value) > 0:
                        status = "filled"
                        self.log(f"Extracted {field_name}: {value[:80]}")
                    else:
                        # Label exists but value is empty
                        status = "blank"
                        self.log(f"Found label for {field_name} but value is empty")
                    break
            
            extracted_fields[field_name] = {
                "value": value,
                "status": status
            }
        
        # Build structured output
        result = {
            "contract_dates": {
                "starting_date": extracted_fields.get("starting_date", {}).get("value", ""),
                "access_dates": self._parse_access_dates(extracted_fields.get("access_date", {}).get("value", "")),
                "completion_date": extracted_fields.get("completion_date", {}).get("value", "")
            },
            "programme_requirements": {
                "submit_first_programme_within": extracted_fields.get("submit_first_programme_within", {}).get("value", ""),
                "revised_programme_interval": extracted_fields.get("revised_programme_interval", {}).get("value", "")
            },
            "delay_damages": extracted_fields.get("delay_damages", {}).get("value", ""),
            "defects": {
                "defects_date": extracted_fields.get("defects_date", {}).get("value", ""),
                "defect_correction_period": extracted_fields.get("defect_correction_period", {}).get("value", "")
            },
            "payment_terms": {
                "assessment_interval": extracted_fields.get("assessment_interval", {}).get("value", ""),
                "payment_period": extracted_fields.get("payment_period", {}).get("value", ""),
                "retention_percentage": extracted_fields.get("retention_percentage", {}).get("value", "")
            },
            "weather_data": {
                "recording_location": extracted_fields.get("weather_recording_location", {}).get("value", ""),
                "measurement_data": self._parse_weather_measurements(extracted_fields.get("weather_measurement_data", {}).get("value", "")),
                "historical_records_source": extracted_fields.get("weather_historical_records_source", {}).get("value", "")
            },
            "extracted_fields": extracted_fields
        }
        
        # Calculate completeness
        result["completeness"] = self._calculate_completeness(extracted_fields)
        
        return result
    
    def _normalize_value(self, value: str) -> str:
        """
        Normalize extracted value.
        
        - Strip trailing punctuation
        - Remove repeated labels
        - Collapse whitespace
        - Remove corrupted fragments
        """
        if not value:
            return ""
        
        # Remove PDF artifacts
        value = re.sub(r'\(cid:\d+\)', '', value)
        
        # Remove trailing punctuation (but keep if it's part of the value)
        value = re.sub(r'[^\w\s\-/]+$', '', value)
        
        # Collapse whitespace
        value = re.sub(r'\s+', ' ', value)
        value = value.strip()
        
        # Remove corrupted single-word fragments
        words = value.split()
        if len(words) == 1:
            word = words[0]
            corrupted = ["is", "of", "the", "a", "an", "and", "or", "but"]
            if word.lower() in corrupted:
                return ""
            # Check if it's a drawing reference without context
            if re.match(r'^[A-Z]\d+$', word) and len(word) < 5:
                return ""
        
        # Remove leading/trailing punctuation
        value = re.sub(r'^[^\w]+|[^\w]+$', '', value)
        
        return value.strip()
    
    def _parse_access_dates(self, value: str) -> List[str]:
        """Parse access dates string into list."""
        if not value:
            return []
        
        # Split by comma, semicolon, or "and"
        dates = re.split(r'[,;]|\s+and\s+', value)
        return [d.strip() for d in dates if d.strip()]
    
    def _parse_weather_measurements(self, value: str) -> List[str]:
        """Parse weather measurements string into list."""
        if not value:
            return []
        
        # Split by comma, semicolon, or "and"
        measurements = re.split(r'[,;]|\s+and\s+', value)
        return [m.strip() for m in measurements if m.strip()]
    
    def _calculate_completeness(self, extracted_fields: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate contract completeness based on extracted fields.
        
        Args:
            extracted_fields: Dictionary of extracted fields with status
            
        Returns:
            Completeness dictionary
        """
        total_fields = len(extracted_fields)
        if total_fields == 0:
            return {
                "document_type": "template",
                "is_template": True,
                "filled_percentage": 0.0,
                "blank_percentage": 0.0,
                "mandatory_filled": 0,
                "mandatory_blank": 0,
                "mandatory_missing": 0,
                "total_mandatory": 0
            }
        
        filled = sum(1 for f in extracted_fields.values() if f.get("status") == "filled")
        blank = sum(1 for f in extracted_fields.values() if f.get("status") == "blank")
        missing = sum(1 for f in extracted_fields.values() if f.get("status") == "missing")
        
        filled_percentage = (filled / total_fields) * 100 if total_fields > 0 else 0.0
        blank_percentage = (blank / total_fields) * 100 if total_fields > 0 else 0.0
        
        # Determine document type
        if filled_percentage > 70:
            document_type = "completed"
            is_template = False
        elif filled_percentage > 20:
            document_type = "partial"
            is_template = False
        else:
            document_type = "template"
            is_template = True
        
        return {
            "document_type": document_type,
            "is_template": is_template,
            "filled_percentage": round(filled_percentage, 1),
            "blank_percentage": round(blank_percentage, 1),
            "mandatory_filled": filled,
            "mandatory_blank": blank,
            "mandatory_missing": missing,
            "total_mandatory": total_fields
        }
