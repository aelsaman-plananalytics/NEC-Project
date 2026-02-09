"""
Real NEC4 ECC Contract Data Extractor (Option B - Regex + AI Value Isolation).

Extraction Philosophy:
1. Use REGEX to FIND the correct line containing the field
2. Use LLM ONLY to isolate the literal value from that line
3. LLM must NEVER invent, infer, or assume values
4. LLM may ONLY crop or trim text

Works with:
- Anderby Creek Piling NEC4 ECC
- Addingham Lower Gauge Fish Pass NEC4 ECC
- KSL Rec Package NEC4 ECC
"""

import re
import os
import json
from typing import Dict, List, Any, Optional, Tuple

# LLM support (optional)
try:
    from openai import AzureOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    AzureOpenAI = None

from app.contract_parser.nec_value_extractor import NECValueExtractor


class RealNECExtractor:
    """
    Extractor for real-world NEC4 ECC contracts (Option B).
    
    Uses regex to find lines, then LLM to isolate literal values only.
    Never invents or generates values.
    """
    
    # Label patterns for line detection (regex finds the line)
    LABEL_PATTERNS = {
        "starting_date": [
            r"\bStarting\s+Date\b",
            r"\bStart\s+Date\b",
            r"The\s+Starting\s+Date\b",
            r"Contract\s+Date\s+is",
        ],
        "access_date": [
            r"\bAccess\s+Date\b",
            r"Access\s+to\s+the\s+Site\s+is",
            r"Contractor['']s\s+access",
            r"The\s+access\s+date",
        ],
        "completion_date": [
            r"\bCompletion\s+Date\b",
            r"Completion\s+of\s+the\s+whole\s+of\s+the\s+works\s+is",
            r"Completion\s+Date\s+for\s+the\s+whole",
        ],
        "first_programme_submission": [
            r"first\s+programme\s+.*\s+submitted\s+within",
            r"submit\s+.*\s+first\s+programme",
            r"period\s+.*\s+submit\s+.*\s+first\s+programme",
            r"first\s+programme\s+for\s+acceptance",
        ],
        "revised_programme_interval": [
            r"revised\s+programme",
            r"programme\s+.*\s+interval",
            r"update\s+.*\s+every",
            r"submits\s+revised\s+programmes\s+at\s+intervals",
        ],
        "key_dates": [
            r"Key\s+Date",
            r"KD[-–]?\s*\d+",
        ],
        "defects_date": [
            r"Defects\s+Date",
            r"defects\s+date\s+is",
            r"period\s+.*\s+defects\s+date",
        ],
        "defect_correction_period": [
            r"defect\s+correction\s+period",
            r"correction\s+period\s+is",
        ],
        "assessment_interval": [
            r"assessment\s+interval",
            r"assessments\s+are\s+made",
        ],
        "payment_period": [
            r"payment\s+period",
            r"payment\s+is\s+made\s+within",
        ],
        "retention_percentage": [
            r"\bretention\b",
            r"\bretain\b",
            r"retainage",
        ],
        "bond_amount": [
            r"Performance\s+bond",
            r"Bond\s+amount",
            r"Contract\s+bond",
        ],
        "weather_location": [
            r"Weather\s+measurements\s+are\s+taken\s+at",
            r"weather\s+.*\s+recorded\s+at",
            r"Met\s+Office",
            r"place\s+where\s+weather",
        ],
        "weather_measurement_type": [
            r"rainfall",
            r"snow",
            r"temperature",
            r"wind\s+speed",
            r"weather\s+measurements",
        ],
        "weather_historical_source": [
            r"weather\s+data\s+is\s+obtained\s+from",
            r"historical\s+records",
            r"Met\s+Office",
        ],
        "delay_damages": [
            r"delay\s+damages",
            r"Option\s+X7",
            r"X7",
        ],
    }
    
    # Validation patterns for extracted values
    DATE_PATTERNS = [
        r'\d{1,2}\s+\w+\s+\d{4}',  # 1 March 2026
        r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',  # 01/03/2026
        r'\d+\s+weeks?\s+after',  # 52 weeks after Completion
        r'Month\s+\d+',  # Month 30
    ]
    
    NUMERIC_PATTERNS = [
        r'[£$€]?\s*\d[\d,\.]*',  # 250,000 or £250,000
        r'\d+%',  # 3%
        r'\d+\s+weeks?',  # 4 weeks
        r'\d+\s+days?',  # 2 days
    ]
    
    def __init__(self, debug: bool = False, enable_llm: bool = False):
        """
        Initialize real NEC extractor.
        
        Args:
            debug: Enable debug logging
            enable_llm: Enable LLM for value trimming (recommended)
        """
        self.debug = debug
        self.enable_llm = enable_llm
        self.azure_client = None
        
        # Initialize NEC Value Extractor (Option B - deterministic value extraction)
        self.value_extractor = NECValueExtractor(debug=debug)
        
        # Initialize Azure OpenAI if LLM is enabled
        if self.enable_llm and OPENAI_AVAILABLE:
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
                    self.log(f"Azure OpenAI enabled for value trimming (model: {model_name})")
                except Exception as e:
                    self.log(f"Warning: Azure OpenAI initialization failed: {e}")
                    self.enable_llm = False
            else:
                self.log("Warning: Azure OpenAI credentials not found, LLM disabled")
                self.enable_llm = False
        
        # Compile patterns for line detection
        self.compiled_label_patterns = {}
        for field, patterns in self.LABEL_PATTERNS.items():
            self.compiled_label_patterns[field] = [
                re.compile(pattern, re.IGNORECASE) for pattern in patterns
            ]
    
    def log(self, msg: str):
        """Log debug message."""
        if self.debug:
            print(f"[RealNECExtractor] {msg}")
    
    def extract(self, clean_text: str, pages: Optional[List[Any]] = None) -> Dict[str, Any]:
        """
        Extract programme-critical data from NEC4 contract.
        
        Args:
            clean_text: Full clean text from PDF
            pages: Optional list of page objects (not used in Option B)
            
        Returns:
            Dictionary with extracted contract data (literal values only)
        """
        self.log("Starting Option B extraction (Regex + LLM Value Isolation)")
        
        # Split text into lines for line-by-line processing
        lines = clean_text.split('\n')
        
        # Extract each field using line-based regex + LLM trimming
        result = {
            "starting_date": self._extract_field("starting_date", lines),
            "access_dates": self._extract_access_dates(lines),
            "completion_date": self._extract_field("completion_date", lines),
            "first_programme_submission": self._extract_field("first_programme_submission", lines),
            "revised_programme_interval": self._extract_field("revised_programme_interval", lines),
            "key_dates": self._extract_key_dates(lines),
            "defects_date": self._extract_field("defects_date", lines),
            "defect_correction_period": self._extract_field("defect_correction_period", lines),
            "assessment_interval": self._extract_field("assessment_interval", lines),
            "payment_period": self._extract_field("payment_period", lines),
            "retention_percentage": self._extract_field("retention_percentage", lines),
            "bond_amount": self._extract_field("bond_amount", lines),
            "delay_damages": self._extract_delay_damages(lines),
            "weather_location": self._extract_field("weather_location", lines),
            "weather_measurement_type": self._extract_field("weather_measurement_type", lines),
            "weather_historical_source": self._extract_field("weather_historical_source", lines),
        }
        
        # Build structured output
        structured_result = {
            "contract_dates": {
                "starting_date": result["starting_date"],
                "access_dates": result["access_dates"] if isinstance(result["access_dates"], list) else [result["access_dates"]] if result["access_dates"] else [],
                "completion_date": result["completion_date"],
                "programme_submission_rules": result["first_programme_submission"],
                "programme_revision_rules": result["revised_programme_interval"]
            },
            "key_dates": result["key_dates"],
            "delay_damages": result["delay_damages"].get("description", "") if isinstance(result["delay_damages"], dict) else result["delay_damages"],
            "delay_damages_amount": result["delay_damages"].get("amount", "") if isinstance(result["delay_damages"], dict) else "",
            "defects": {
                "defects_date": result["defects_date"],
                "defect_correction_period": result["defect_correction_period"]
            },
            "weather_data": {
                "weather_measurement_location": result["weather_location"],
                "weather_measurement_type": result["weather_measurement_type"],
                "historical_records_source": result["weather_historical_source"]
            },
            "payment_terms": {
                "assessment_interval": result["assessment_interval"],
                "payment_period": result["payment_period"],
                "retention_percentage": result["retention_percentage"],
                "bond_amount": result["bond_amount"]
            },
            "metadata": {
                "extraction_method": "real_nec_extractor_option_b"
            }
        }
        
        # Calculate completeness
        completeness = self._calculate_completeness(structured_result)
        structured_result["metadata"]["completeness"] = completeness
        structured_result["metadata"]["fields_extracted"] = self._count_extracted_fields(structured_result)
        
        return structured_result
    
    def _extract_field(self, field_name: str, lines: List[str]) -> str:
        """
        Extract a single field using regex line detection + LLM value trimming.
        
        Args:
            field_name: Name of field to extract
            lines: List of text lines
            
        Returns:
            Literal value (date, number, or short phrase) or empty string
        """
        if field_name not in self.compiled_label_patterns:
            return ""
        
        patterns = self.compiled_label_patterns[field_name]
        
        # STEP 1: Find the line using regex
        for line in lines:
            for pattern in patterns:
                if pattern.search(line):
                    self.log(f"Found line for {field_name}: {line[:100]}")
                    
                    # STEP 2: Trim to literal value using LLM or regex
                    value = self._trim_to_literal_value(line, field_name)
                    
                    # STEP 3: Validate the extracted value
                    if self._validate_value(value, field_name):
                        self.log(f"Extracted {field_name}: {value}")
                        return value
                    else:
                        self.log(f"Invalid value for {field_name}: {value}, skipping")
        
        return ""
    
    def _trim_to_literal_value(self, line: str, field_name: str) -> str:
        """
        Trim line to literal value only using NECValueExtractor.
        
        Args:
            line: Full line containing the field
            field_name: Name of field being extracted
            
        Returns:
            Literal value only (date, number, or short phrase)
        """
        # Use NECValueExtractor to extract literal value
        value = self.value_extractor.extract(field_name, line)
        
        # If value extractor didn't find anything and LLM is enabled, try LLM trimming
        if not value and self.enable_llm and self.azure_client:
            value = self._trim_with_llm(line, field_name)
        
        return value
    
    def _trim_with_llm(self, line: str, field_name: str) -> str:
        """
        Use LLM to trim line to literal value ONLY (fallback only).
        
        CRITICAL: LLM must NEVER invent or generate values.
        It may ONLY crop/trim the provided line.
        
        Args:
            line: Full line containing the field
            field_name: Name of field being extracted
            
        Returns:
            Literal value only
        """
        if not self.azure_client:
            return ""
        
        prompt = f"""You will be given one line from an NEC4 contract.
Your task: extract ONLY the literal value (date, number, or short phrase).
Never invent or guess.
If no literal value appears, return an empty string.

Example:
INPUT: "The Completion Date for the whole of the works is 31 March 2031."
OUTPUT: "31 March 2031"

INPUT: "The assessment interval is 4 weeks."
OUTPUT: "4 weeks"

INPUT: "Retention is 3%."
OUTPUT: "3%"

Now extract the literal value from this line:
{line}

Return ONLY the literal value, nothing else:"""

        try:
            response = self.azure_client.chat.completions.create(
                model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": "You extract literal values from contract text. Never invent or generate values. Only return what you see."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,  # Zero temperature for deterministic output
                max_tokens=50
            )
            
            value = response.choices[0].message.content.strip()
            
            # Remove quotes if LLM added them
            value = value.strip('"\'')
            
            # Validate that LLM didn't invent anything (check if value appears in original line)
            if value and value.lower() in line.lower():
                return value
            else:
                # AI is allowed to trim/extract - no strict validation
                self.log(f"LLM extracted value: {value}")
                return ""
        
        except Exception as e:
            self.log(f"LLM trimming failed: {e}")
            return ""
    
    def _validate_value(self, value: str, field_name: str) -> bool:
        """
        Validate that extracted value is a literal value (not a sentence).
        
        Args:
            value: Extracted value
            field_name: Name of field
            
        Returns:
            True if value is valid literal, False otherwise
        """
        if not value or len(value) == 0:
            return False
        
        # Reject if value is too long (likely a sentence, not a literal)
        if len(value) > 100:
            return False
        
        # Reject if value contains multiple sentences
        if value.count('.') > 1:
            return False
        
        # Reject common sentence starters (unless it's a valid pattern)
        sentence_starters = ["The", "This", "A", "An", "If", "When", "Where"]
        if any(value.startswith(starter + " ") for starter in sentence_starters):
            # Check if it contains valid patterns
            has_valid_pattern = (
                re.search(r'\d{1,2}\s+\w+\s+\d{4}', value) or  # Date
                re.search(r'\d+%', value) or  # Percentage
                re.search(r'[£$€]\s*\d', value) or  # Currency
                re.search(r'\d+\s+weeks?', value)  # Duration
            )
            if not has_valid_pattern:
                return False
        
        # Accept if it's a valid literal value (dates, numbers, short phrases)
        return True
    
    def _extract_access_dates(self, lines: List[str]) -> List[str]:
        """Extract access dates (may be multiple)."""
        access_dates = []
        
        for line in lines:
            for pattern in self.compiled_label_patterns.get("access_date", []):
                if pattern.search(line):
                    value = self._trim_to_literal_value(line, "access_date")
                    if self._validate_value(value, "access_date"):
                        # Parse multiple dates if present
                        dates = self._parse_multiple_dates(value)
                        access_dates.extend(dates)
                        self.log(f"Extracted access_date: {value}")
        
        # Remove duplicates
        return list(dict.fromkeys(access_dates))  # Preserves order
    
    def _extract_key_dates(self, lines: List[str]) -> List[Dict[str, Any]]:
        """Extract Key Dates (KD-01, KD-02, etc.) using NECValueExtractor."""
        # Combine lines into text block for key dates extraction
        text_block = '\n'.join(lines)
        
        # Use NECValueExtractor to extract key dates
        key_dates = self.value_extractor.extract_key_dates(text_block)
        
        return key_dates
    
    def _extract_delay_damages(self, lines: List[str]) -> Dict[str, Any]:
        """Extract Delay Damages from Option X7 using NECValueExtractor."""
        delay_damages = {
            "description": "",
            "amount": ""
        }
        
        for line in lines:
            for pattern in self.compiled_label_patterns.get("delay_damages", []):
                if pattern.search(line):
                    # Use NECValueExtractor to extract literal value
                    value = self.value_extractor.extract("delay_damages", line)
                    
                    if value:
                        delay_damages["description"] = value
                        
                        # Try to extract amount from value
                        amount_match = re.search(r'([£$€]?\s*\d[\d,\.]*)\s*(per|a)\s*(day|week|month)', value, re.IGNORECASE)
                        if amount_match:
                            delay_damages["amount"] = amount_match.group(0)
                        
                        self.log(f"Extracted delay_damages: {value}")
                        break
        
        return delay_damages
    
    def _parse_multiple_dates(self, value: str) -> List[str]:
        """Parse multiple dates from string."""
        if not value:
            return []
        
        # Split by comma, semicolon, or "and"
        dates = re.split(r'[,;]|\s+and\s+', value)
        return [d.strip() for d in dates if d.strip() and self._validate_value(d.strip(), "access_date")]
    
    def _count_extracted_fields(self, result: Dict[str, Any]) -> int:
        """Count number of extracted fields."""
        count = 0
        
        contract_dates = result.get("contract_dates", {})
        if contract_dates.get("starting_date"):
            count += 1
        if contract_dates.get("access_dates"):
            count += len(contract_dates["access_dates"])
        if contract_dates.get("completion_date"):
            count += 1
        if contract_dates.get("programme_submission_rules"):
            count += 1
        if contract_dates.get("programme_revision_rules"):
            count += 1
        
        if result.get("key_dates"):
            count += len(result["key_dates"])
        
        if result.get("delay_damages"):
            count += 1
        
        defects = result.get("defects", {})
        if defects.get("defects_date"):
            count += 1
        if defects.get("defect_correction_period"):
            count += 1
        
        weather_data = result.get("weather_data", {})
        if weather_data.get("weather_measurement_location"):
            count += 1
        if weather_data.get("weather_measurement_type"):
            count += 1
        if weather_data.get("historical_records_source"):
            count += 1
        
        payment_terms = result.get("payment_terms", {})
        if payment_terms.get("assessment_interval"):
            count += 1
        if payment_terms.get("payment_period"):
            count += 1
        if payment_terms.get("retention_percentage"):
            count += 1
        if payment_terms.get("bond_amount"):
            count += 1
        
        return count
    
    def _calculate_completeness(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate completeness based on Time & Key Dates."""
        contract_dates = result.get("contract_dates", {})
        time_fields = [
            contract_dates.get("starting_date"),
            contract_dates.get("completion_date"),
        ]
        
        time_filled = sum(1 for f in time_fields if f)
        key_dates_count = len(result.get("key_dates", []))
        
        # Completeness determined by Time & Key Dates
        has_time_data = time_filled >= 1
        has_key_dates = key_dates_count > 0
        
        if has_time_data and has_key_dates:
            document_type = "completed"
            is_template = False
        elif has_time_data or has_key_dates:
            document_type = "partial"
            is_template = False
        else:
            document_type = "template"
            is_template = True
        
        return {
            "document_type": document_type,
            "is_template": is_template,
            "time_fields_filled": time_filled,
            "key_dates_count": key_dates_count,
            "has_time_data": has_time_data,
            "has_key_dates": has_key_dates
        }
