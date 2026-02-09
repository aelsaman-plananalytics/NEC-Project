"""
NEC4 Contract Data Extraction – Hybrid Engine + AI Override System

Extraction Pipeline Order:
1. Deterministic pattern matching (dates, money, durations)
2. Table cells (Camelot/PDFMiner)
3. Semantic AI extraction (LLM) - only when engine fails or returns garbage

Works with:
- Anderby Creek NEC4 ECC
- Addingham Lower Gauge Fish Pass NEC4 ECC
- KSL Rec Package NEC4 ECC
- Skyscraper contract
"""

import re
import os
from typing import Dict, List, Any, Optional, Tuple

# LLM support
try:
    from openai import AzureOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    AzureOpenAI = None

# Table extraction support
try:
    import camelot
    CAMELOT_AVAILABLE = True
except ImportError:
    CAMELOT_AVAILABLE = False
    camelot = None


class HybridAIExtractor:
    """
    Hybrid extraction system with deterministic patterns + AI override.
    
    Pipeline:
    1. Deterministic pattern matching (dates, money, durations)
    2. Table extraction (Camelot/PDFMiner)
    3. AI semantic extraction (only when engine fails or returns garbage)
    """
    
    # Keyword patterns for field detection (exact NEC4 clause references prioritized)
    KEYWORD_PATTERNS = {
        "starting_date": [
            r"the\s+starting\s+date\s+is",  # Exact phrase (highest priority)
            r"start\s+date[:]",
            r"starting[:]",
            r"commencement\s+date",
            r"starting\s+date",
        ],
        "access_dates": [
            r"the\s+contractor\s+is\s+provided\s+access\s+to\s+the\s+site\s+on",  # Exact phrase (highest priority)
            r"the\s+access\s+dates\s+are",  # Exact phrase
            r"access\s+is\s+given\s+on",
            r"access\s+date",
            r"access\s+dates",
            r"the\s+contractor\s+is\s+allowed\s+access\s+from",
            r"site\s+access\s+on",
        ],
        "completion_date": [
            r"the\s+completion\s+date\s+for\s+the\s+whole\s+of\s+the\s+works\s+is",  # Exact phrase (highest priority)
            r"completion\s+date\s+is",
            r"completion\s+date",
            r"completion\s+is",
            r"for\s+the\s+whole\s+of\s+the\s+works\s+is",
        ],
        "first_programme_submission": [
            r"within\s+which\s+the\s+contractor\s+is\s+to\s+submit\s+a\s+first\s+programme",  # Exact phrase (highest priority)
            r"first\s+programme",
            r"submit\s+the\s+first\s+programme\s+within",
            r"programme\s+submission\s+interval",
        ],
        "revised_programme_interval": [
            r"submits\s+revised\s+programmes",  # Exact phrase (highest priority)
            r"revised\s+programme",
            r"revised\s+programmes\s+at\s+intervals",
        ],
        "delay_damages": [
            r"x7",  # Must be in X7 section (highest priority)
            r"option\s+x7",
            r"delay\s+damages",
            r"damages\s+for\s+delay",
        ],
        "defect_correction_period": [
            r"defect\s+correction\s+period\s+is",  # Exact phrase (highest priority)
            r"correction\s+period",
            r"is\s+corrected\s+within",
            r"defect\s+correction\s+period",
        ],
        "defects_date": [
            r"the\s+period\s+between\s+completion\s+.*\s+and\s+the\s+defects\s+date\s+is",  # Exact phrase (highest priority)
            r"period\s+between\s+completion\s+.*\s+and\s+the\s+defects\s+date",
            r"defects\s+date",
            r"period\s+between\s+completion\s+and\s+defects",
        ],
        "retention_percentage": [
            r"retention\s+following\s+completion",
            r"the\s+retention\s+percentage\s+is",
            r"retention\s+is",
            r"retention",
        ],
        "assessment_interval": [
            r"the\s+assessment\s+interval\s+is",  # Exact phrase (highest priority)
            r"assessment\s+interval\s+is",
            r"assessment\s+interval",
        ],
        "payment_period": [
            r"the\s+payment\s+period\s+is",  # Exact phrase (highest priority)
            r"payment\s+period\s+is",
            r"payment\s+period",
            r"payment\s+is\s+made\s+within",
        ],
        "weather_recording_location": [
            r"weather\s+is\s+recorded\s+at",  # Exact phrase (highest priority)
            r"weather\s+station",
            r"met\s+office",
            r"place\s+where\s+weather",
        ],
        "weather_measurements": [
            r"cumulative\s+rainfall",  # Specific measurements (highest priority)
            r"days\s+with\s+rainfall",
            r"days\s+with\s+snow",
            r"days\s+with\s+min\s+temp",
            r"weather\s+measurements",
            r"rainfall",
            r"temperature",
            r"wind\s+speed",
        ],
        "historical_weather_source": [
            r"met\s+office",  # Must extract Met Office (highest priority)
            r"weather\s+data\s+are\s+the\s+records",
            r"historical\s+weather",
        ],
    }
    
    # Deterministic patterns for value extraction
    # DATE_REGEX with month names (as specified)
    DATE_PATTERNS = [
        r'\b(\d{1,2}\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})\b',  # 1 March 2024
        r'\b(\d{1,2}\s+[A-Za-z]+\s+\d{4})\b',  # 1 March 2024 (fallback)
        r'\b(\d{1,2}/\d{1,2}/\d{4})\b',  # 01/03/2024
        r'\b(\d{1,2}-\d{1,2}-\d{4})\b',  # 01-03-2024
        r'\b(\d{4}-\d{2}-\d{2})\b',  # 2024-03-01
    ]
    
    DURATION_PATTERNS = [
        r'(\d+\s+(?:week|weeks|day|days|month|months))',  # 2 weeks, 52 weeks
        r'(\d+\s+weeks?\s+after)',  # 52 weeks after Completion
    ]
    
    MONEY_PATTERNS = [
        r'£[\d,]+(?:\.\d{2})?',  # £250,000 or £250,000.00
        r'[£$€]\s*[\d,]+(?:\.\d{2})?',  # £ 250,000
        r'[\d,]+(?:\.\d{2})?\s*(?:per|a)\s*(?:day|week|month)',  # 250,000 per week
    ]
    
    WINDOW_SIZE = 4  # Lines before/after keyword
    
    def __init__(self, debug: bool = False, enable_ai: bool = True, pdf_path: Optional[str] = None):
        """
        Initialize hybrid AI extractor.
        
        Args:
            debug: Enable debug logging
            enable_ai: Enable AI extraction (required)
            pdf_path: Optional PDF path for table extraction
        """
        self.debug = debug
        self.enable_ai = enable_ai
        self.pdf_path = pdf_path
        self.azure_client = None
        self.sections = {}  # Cache for detected sections
        
        # Compile patterns FIRST (before AI initialization)
        self.compiled_keyword_patterns = {}
        for field, patterns in self.KEYWORD_PATTERNS.items():
            self.compiled_keyword_patterns[field] = [
                re.compile(pattern, re.IGNORECASE) for pattern in patterns
            ]
        
        self.compiled_date_patterns = [re.compile(p, re.IGNORECASE) for p in self.DATE_PATTERNS]
        self.compiled_duration_patterns = [re.compile(p, re.IGNORECASE) for p in self.DURATION_PATTERNS]
        self.compiled_money_patterns = [re.compile(p, re.IGNORECASE) for p in self.MONEY_PATTERNS]
        
        if self.enable_ai:
            if not OPENAI_AVAILABLE:
                raise ValueError("OpenAI library not available. Install openai package.")
            
            azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
            azure_api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
            azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
            
            if azure_endpoint and azure_api_key:
                try:
                    self.azure_client = AzureOpenAI(
                        api_key=azure_api_key,
                        api_version=azure_api_version,
                        azure_endpoint=azure_endpoint
                    )
                except Exception as e:
                    self.log(f"Failed to initialize Azure OpenAI client: {e}")
    
    def detect_sections(self, clean_text: str) -> Dict[str, Tuple[int, int]]:
        """
        STAGE 1 — SECTION LOCATOR
        
        Detect boundaries of each NEC section.
        
        Returns:
            Dictionary mapping section names to (start_idx, end_idx) tuples
        """
        sections = {}
        lines = clean_text.split('\n')
        text_length = len(clean_text)
        
        # Section detection patterns
        section_patterns = {
            "section_3": [
                r"3(\.| )\s*Time",
                r"Section\s+3[: ]*Time",
                r"^3\s+Time",
            ],
            "section_4": [
                r"4(\.| )\s*Quality",
                r"Section\s+4[: ]*Quality",
                r"^4\s+Quality",
            ],
            "section_5": [
                r"5(\.| )\s*Payment",
                r"Section\s+5[: ]*Payment",
                r"^5\s+Payment",
            ],
            "section_x7": [
                r"X7(\.| )\s*Delay",
                r"Option\s+X7",
                r"X7\s*–\s*Delay\s+Damages",
                r"X7\s*Delay",
            ],
            "section_6": [
                r"6(\.| )\s*Compensation",
                r"Section\s+6[: ]*Compensation",
                r"^6\s+Compensation",
            ],
        }
        
        # Find start positions for each section
        section_starts = {}
        for section_name, patterns in section_patterns.items():
            for line_idx, line in enumerate(lines):
                for pattern in patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        # Calculate character position
                        char_pos = sum(len(lines[i]) + 1 for i in range(line_idx))
                        section_starts[section_name] = char_pos
                        self.log(f"Found {section_name} at line {line_idx}, char {char_pos}")
                        break
                if section_name in section_starts:
                    break
        
        # Determine end positions (start of next section, or end of document)
        section_order = ["section_3", "section_4", "section_5", "section_x7", "section_6"]
        
        for i, section_name in enumerate(section_order):
            if section_name not in section_starts:
                continue
            
            start_pos = section_starts[section_name]
            
            # Find end position (start of next section)
            end_pos = text_length
            for next_section in section_order[i+1:]:
                if next_section in section_starts:
                    end_pos = section_starts[next_section]
                    break
            
            sections[section_name] = (start_pos, end_pos)
            self.log(f"{section_name}: {start_pos} to {end_pos} ({end_pos - start_pos} chars)")
        
        return sections
    
    def _get_section_text(self, clean_text: str, section_name: str) -> str:
        """
        Get text block for a specific section.
        
        Args:
            clean_text: Full clean text
            section_name: Section name (e.g., "section_3")
            
        Returns:
            Text block for the section, or empty string if section not found
        """
        if not self.sections:
            self.sections = self.detect_sections(clean_text)
        
        if section_name not in self.sections:
            return ""
        
        start_idx, end_idx = self.sections[section_name]
        return clean_text[start_idx:end_idx]
    
    def log(self, msg: str):
        """Log debug message."""
        if self.debug:
            print(f"[HybridAIExtractor] {msg}")
    
    def _get_context_around_keyword(self, clean_text: str, field_name: str, window_chars: int = 1500) -> str:
        """
        Extract 800-1500 characters around the keyword for AI processing.
        
        Args:
            clean_text: Full clean text
            field_name: Field name to find keyword for
            window_chars: Number of characters to extract (default 1500)
            
        Returns:
            Context text slice around keyword
        """
        # Get section-specific text first
        section_map = {
            "starting_date": "section_3",
            "access_dates": "section_3",
            "completion_date": "section_3",
            "first_programme_submission": "section_3",
            "revised_programme_interval": "section_3",
            "delay_damages": "section_x7",
            "defects_date": "section_4",
            "defect_correction_period": "section_4",
            "assessment_interval": "section_5",
            "payment_period": "section_5",
            "retention_percentage": "section_5",
            "weather_recording_location": "section_6",
            "weather_measurements": "section_6",
            "historical_weather_source": "section_6",
        }
        
        section_name = section_map.get(field_name, None)
        if section_name:
            text = self._get_section_text(clean_text, section_name)
            if not text:
                # Fallback to full text if section not found
                text = clean_text
        else:
            text = clean_text
        
        # Find keyword position
        patterns = self.compiled_keyword_patterns.get(field_name, [])
        if not patterns:
            # Return slice from beginning if no patterns
            return text[:window_chars]
        
        # Find first keyword match
        keyword_pos = -1
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                keyword_pos = match.start()
                break
        
        if keyword_pos == -1:
            # Keyword not found, return beginning slice
            return text[:window_chars]
        
        # Extract window around keyword
        start_pos = max(0, keyword_pos - window_chars // 2)
        end_pos = min(len(text), keyword_pos + window_chars // 2)
        
        return text[start_pos:end_pos]
    
    def ai_verify_and_correct(self, field_name: str, engine_value: str, context_text: str) -> str:
        """
        Uses LLM to confirm whether engine_value is correct.
        If incorrect → returns corrected value.
        If AI cannot confirm → returns engine_value.
        
        Args:
            field_name: Field name being extracted
            engine_value: Value extracted by engine (regex/pattern)
            context_text: Context text around the keyword (800-1500 chars)
            
        Returns:
            AI-verified and corrected value
        """
        if not self.azure_client:
            return engine_value if engine_value else "not specified"
        
        # Field-specific extraction rules
        field_rules = {
            "completion_date": {
                "phrases": ["completion date", "completion for the whole of the works", "completion of the whole of the works is", "completion is"],
                "extract": "date (DD Month YYYY) and any trailing notes like 'TBC', 'estimated', 'provisional'",
                "format": "date only, or date + notes separated by comma"
            },
            "access_dates": {
                "phrases": ["access date", "access dates", "the contractor is given access", "access to the site", "the Employer gives access"],
                "extract": "ALL dates or date ranges (from X to Y)",
                "format": "comma-separated list of dates"
            },
            "delay_damages": {
                "phrases": ["X7", "delay damages", "damages for delay"],
                "extract": "£ amount + per day/week, or 'specified but redacted', or 'not included'",
                "format": "£X per week/day, or 'specified but redacted', or 'not included'"
            },
            "defects_date": {
                "phrases": ["defects date", "period between completion and the defects date"],
                "extract": "duration offset (e.g., '52 weeks after Completion')",
                "format": "X weeks/days after Completion"
            },
            "defect_correction_period": {
                "phrases": ["defect correction period", "correction period", "is corrected within"],
                "extract": "numeric duration (e.g., '2 weeks')",
                "format": "X weeks or X days"
            },
            "assessment_interval": {
                "phrases": ["assessment interval", "interval between assessments", "assessment period"],
                "extract": "numeric duration",
                "format": "X weeks or X days"
            },
            "payment_period": {
                "phrases": ["paid within", "payment period", "payment is made within"],
                "extract": "numeric duration",
                "format": "X weeks or X days"
            },
            "retention_percentage": {
                "phrases": ["the retention percentage is", "retention is"],
                "extract": "percentage value",
                "format": "X%"
            },
            "weather_recording_location": {
                "phrases": ["weather station", "weather measurements", "met office"],
                "extract": "location name",
                "format": "location name only"
            },
            "historical_weather_source": {
                "phrases": ["met office", "weather data", "historic weather"],
                "extract": "source name (usually 'Met Office')",
                "format": "source name"
            },
        }
        
        field_rule = field_rules.get(field_name, {})
        phrases = field_rule.get("phrases", [])
        extract_desc = field_rule.get("extract", "value")
        format_desc = field_rule.get("format", "value")
        
        prompt = f"""You are verifying and correcting a value extracted from an NEC4 contract.

Field: {field_name}
Engine extracted value: {engine_value if engine_value else "None (not found)"}
Look for phrases: {', '.join(phrases)}
Extract: {extract_desc}
Format: {format_desc}

CRITICAL RULES:
1. Extract ONLY the target value (date, duration, percentage, amount, location) - NO narrative text
2. If engine value is correct → return it unchanged
3. If engine value is wrong/incomplete → extract correct value from context
4. AI is ALLOWED to:
   - Trim text to extract just the number/date/amount
   - Remove irrelevant words
   - Extract numbers or dates from nearby text
5. AI is NOT ALLOWED to:
   - Invent dates or numbers not in the context
   - Replace text not found in the window
   - Rewrite values outside the extracted context
6. If value is redacted (████) → return "specified but redacted"
7. If field is not present → return "not included"
8. If value cannot be determined → return "not specified"
9. NEVER return full sentences or paragraphs
10. NEVER hallucinate - only extract what actually exists in the text

Context text:
{context_text[:2000]}

Return JSON: {{"value": "...", "notes": "..." if applicable}}
If no notes, omit notes field."""

        try:
            response = self.azure_client.chat.completions.create(
                model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini"),
                messages=[
                    {
                        "role": "system",
                        "content": "You verify and correct extracted values from NEC contracts. Extract ONLY literal values (dates, numbers, durations, amounts). Never return sentences or paragraphs. Return JSON with 'value' field."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.0,
                max_tokens=150,
                response_format={"type": "json_object"}
            )
            
            result = response.choices[0].message.content.strip()
            
            # Parse JSON response
            import json
            try:
                parsed = json.loads(result)
                ai_value = parsed.get("value", "").strip()
                notes = parsed.get("notes", "").strip()
                
                # Clean value
                ai_value = self._clean_value(ai_value)
                
                # AI is allowed to trim/extract - no strict validation that value must appear verbatim
                # Only check that it's not a status message
                
                # Combine value and notes if applicable
                if notes and ai_value:
                    return f"{ai_value}, {notes}"
                
                return ai_value if ai_value else (engine_value if engine_value else "not specified")
            except json.JSONDecodeError:
                # Fallback: try to extract value from response
                value = result.strip('"\'{}')
                value = self._clean_value(value)
                return value if value else (engine_value if engine_value else "not specified")
        
        except Exception as e:
            self.log(f"AI verification failed for {field_name}: {e}")
            return engine_value if engine_value else "not specified"
    
    def extract(self, clean_text: str, pdf_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract all NEC4 contract data using fallback engine (Layer 3).
        
        This is used as a fallback when phrase-based extraction fails.
        NO section slicing - searches entire document.
        
        Args:
            clean_text: Full clean text from PDF
            pdf_path: Optional PDF path for table extraction
            
        Returns:
            Dictionary with extracted contract data (clean literal values only)
        """
        self.log("Starting fallback engine extraction (no section slicing)")
        
        if pdf_path:
            self.pdf_path = pdf_path
        
        # NO section detection - search entire document
        # Step 1: Extract from tables first (most reliable)
        table_data = self._extract_from_tables()
        
        # Step 2: Extract using deterministic patterns (entire document, no section slicing)
        pattern_data = self._extract_with_patterns(clean_text)
        
        # Step 3: Merge results
        merged_data = {}
        for field_name in self.KEYWORD_PATTERNS.keys():
            # Priority order: table data > pattern data
            engine_value = table_data.get(field_name) or pattern_data.get(field_name, "")
            merged_data[field_name] = engine_value if engine_value else "not specified"
        
        # Build structured output with new JSON structure
        completion_value = merged_data.get("completion_date", "not specified")
        completion_notes = ""
        if ", " in completion_value:
            parts = completion_value.split(", ", 1)
            completion_value = parts[0]
            completion_notes = parts[1] if len(parts) > 1 else ""
        
        delay_damages_value = merged_data.get("delay_damages", "not specified")
        delay_damages_amount = None
        if delay_damages_value.startswith("£"):
            delay_damages_amount = delay_damages_value
        elif delay_damages_value == "specified but redacted":
            delay_damages_amount = None
        elif delay_damages_value == "not included":
            delay_damages_amount = None
        
        # Return flat dictionary matching phrase extractor field names
        structured_result = {
            "starting_date": merged_data.get("starting_date", "not specified"),
            "access_dates": merged_data.get("access_dates", ""),  # Keep as string for consistency
            "completion_date": completion_value,
            "first_programme_submission": merged_data.get("first_programme_submission", "not specified"),
            "revised_programme_interval": merged_data.get("revised_programme_interval", "not specified"),
            "delay_damages": delay_damages_value,
            "defects_date": merged_data.get("defects_date", "not specified"),
            "defect_correction_period": merged_data.get("defect_correction_period", "not specified"),
            "assessment_interval": merged_data.get("assessment_interval", "not specified"),
            "payment_period": merged_data.get("payment_period", "not specified"),
            "retention_percentage": merged_data.get("retention_percentage", "not specified"),
            "bond_amount": merged_data.get("bond_amount", "not specified"),
            "weather_location": merged_data.get("weather_recording_location", "not specified"),
            "weather_measurement_type": merged_data.get("weather_measurements", "not specified"),
            "weather_historical_source": merged_data.get("historical_weather_source", "Met Office"),
        }
        
        return structured_result
    
    def _extract_from_tables(self) -> Dict[str, Any]:
        """Extract values from PDF tables using Camelot or fallback."""
        table_data = {}
        
        if not self.pdf_path:
            return table_data
        
        try:
            if CAMELOT_AVAILABLE:
                # Try Camelot first
                tables = camelot.read_pdf(self.pdf_path, pages='all', flavor='lattice')
                self.log(f"Found {len(tables)} tables using Camelot")
                
                for table in tables:
                    df = table.df
                    # Look for keyword-value pairs in table
                    for idx, row in df.iterrows():
                        left_col = str(row.iloc[0]).lower() if len(row) > 0 else ""
                        right_col = str(row.iloc[1]).strip() if len(row) > 1 else ""
                        
                        # Match left column to field keywords (exact NEC4 clause references)
                        for field_name, patterns in self.compiled_keyword_patterns.items():
                            for pattern in patterns:
                                if pattern.search(left_col):
                                    # Extract value from right column using field-specific rules
                                    value = self._extract_value_from_text(right_col, field_name)
                                    if value and not self._is_hallucination(value):
                                        # Validate value passes sanity filter
                                        if self._passes_sanity_filter(value, field_name):
                                            table_data[field_name] = value
                                            self.log(f"Extracted {field_name} from table: {value}")
                                    break
        except Exception as e:
            self.log(f"Table extraction failed: {e}")
        
        return table_data
    
    def _extract_with_patterns(self, clean_text: str) -> Dict[str, Any]:
        """
        Extract values using deterministic patterns (NO section slicing).
        
        This is the fallback engine (Layer 3) that searches the entire document.
        
        Prioritizes:
        1. Exact NEC4 clause references
        2. Semantically relevant phrases
        3. Rule-based fallback
        """
        pattern_data = {}
        
        # NO SECTION SLICING - search entire document
        # Extract all fields from full clean_text
        
        # Starting Date
        if "starting_date" not in pattern_data:
            value = self._extract_starting_date(clean_text)
            if value:
                pattern_data["starting_date"] = value
        
        # Access Dates
        if "access_dates" not in pattern_data:
            value = self._extract_access_dates(clean_text)
            if value:
                pattern_data["access_dates"] = value
        
        # Completion Date
        if "completion_date" not in pattern_data:
            value = self._extract_completion_date(clean_text)
            if value:
                pattern_data["completion_date"] = value
        
        # First Programme Submission
        if "first_programme_submission" not in pattern_data:
            value = self._extract_first_programme_submission(clean_text)
            if value:
                pattern_data["first_programme_submission"] = value
        
        # Revised Programme Interval
        if "revised_programme_interval" not in pattern_data:
            value = self._extract_revised_programme_interval(clean_text)
            if value:
                pattern_data["revised_programme_interval"] = value
        
        # Delay Damages (X7) - NO section slicing, search entire document
        if "delay_damages" not in pattern_data:
            value = self._extract_delay_damages(clean_text)
            if value:
                pattern_data["delay_damages"] = value
        
        # Defects Date
        if "defects_date" not in pattern_data:
            value = self._extract_defects_date(clean_text)
            if value:
                pattern_data["defects_date"] = value
        
        # Defect Correction Period
        if "defect_correction_period" not in pattern_data:
            value = self._extract_defect_correction_period(clean_text)
            if value:
                pattern_data["defect_correction_period"] = value
        
        # Assessment Interval
        if "assessment_interval" not in pattern_data:
            value = self._extract_assessment_interval(clean_text)
            if value:
                pattern_data["assessment_interval"] = value
        
        # Payment Period
        if "payment_period" not in pattern_data:
            value = self._extract_payment_period(clean_text)
            if value:
                pattern_data["payment_period"] = value
        
        # Retention Percentage
        if "retention_percentage" not in pattern_data:
            value = self._extract_retention_percentage(clean_text)
            if value:
                pattern_data["retention_percentage"] = value
        
        # Bond Amount
        if "bond_amount" not in pattern_data:
            value = self._extract_bond_amount(clean_text)
            if value:
                pattern_data["bond_amount"] = value
        
        # Weather Location
        if "weather_recording_location" not in pattern_data:
            value = self._extract_weather_location(clean_text)
            if value:
                pattern_data["weather_recording_location"] = value
        
        # Weather Source
        if "historical_weather_source" not in pattern_data:
            value = self._extract_weather_source(clean_text)
            if value:
                pattern_data["historical_weather_source"] = value
        
        return pattern_data
    
    # SECTION-SPECIFIC EXTRACTION METHODS
    
    def _extract_starting_date(self, full_text: str) -> str:
        """Extract starting date from Section 3 only."""
        # Search for phrases
        phrases = [
            r"the\s+starting\s+date\s+is",
            r"start\s+date[:]",
            r"starting[:]",
            r"commencement\s+date",
        ]
        
        # DATE_REGEX with month names
        months = r"(January|February|March|April|May|June|July|August|September|October|November|December)"
        date_regex = rf"\b(\d{{1,2}}\s+{months}\s+\d{{4}})\b"
        
        for phrase in phrases:
            phrase_match = re.search(phrase, full_text, re.IGNORECASE)
            if phrase_match:
                # Extract text within ±300 characters
                start_pos = max(0, phrase_match.start() - 300)
                end_pos = min(len(full_text), phrase_match.end() + 300)
                context = full_text[start_pos:end_pos]
                
                # Extract date using DATE_REGEX
                date_match = re.search(date_regex, context, re.IGNORECASE)
                if date_match:
                    return self._ai_clean(date_match.group(1))
        
        return ""
    
    def _extract_access_dates(self, full_text: str) -> str:
        """Extract access dates from Section 3 only - ALL dates or date ranges."""
        # Search for access date phrases
        phrases = [
            r"access\s+date",
            r"access\s+dates",
            r"the\s+contractor\s+is\s+given\s+access",
            r"access\s+to\s+the\s+site",
            r"the\s+Employer\s+gives\s+access",
        ]
        
        dates = []
        months = r"(January|February|March|April|May|June|July|August|September|October|November|December)"
        
        for phrase in phrases:
            # Find phrase position
            phrase_match = re.search(phrase, full_text, re.IGNORECASE)
            if phrase_match:
                # Extract text after phrase (up to 300 chars for date ranges)
                start_pos = phrase_match.end()
                context = full_text[start_pos:start_pos + 300]
                
                # Extract all dates
                date_pattern = rf"\b(\d{{1,2}}\s+{months}\s+\d{{4}})\b"
                date_matches = re.findall(date_pattern, context, re.IGNORECASE)
                dates.extend([m[0] if isinstance(m, tuple) else m for m in date_matches])
                
                # Also check for date ranges "from X to Y"
                range_pattern = rf"from\s+(\d{{1,2}}\s+{months}\s+\d{{4}})\s+to\s+(\d{{1,2}}\s+{months}\s+\d{{4}})"
                range_match = re.search(range_pattern, context, re.IGNORECASE)
                if range_match:
                    dates.append(range_match.group(1))
                    dates.append(range_match.group(2))
        
        if dates:
            # Remove duplicates while preserving order
            seen = set()
            unique_dates = []
            for d in dates:
                d_clean = d.strip()
                if d_clean not in seen:
                    seen.add(d_clean)
                    unique_dates.append(d_clean)
            
            return ", ".join(unique_dates)
        
        return ""
    
    def _extract_completion_date(self, full_text: str) -> str:
        """Extract completion date from Section 3 only, including notes like 'TBC'."""
        # Search for completion date phrases
        phrases = [
            r"completion\s+date",
            r"completion\s+for\s+the\s+whole\s+of\s+the\s+works",
            r"completion\s+of\s+the\s+whole\s+of\s+the\s+works\s+is",
            r"completion\s+is",
        ]
        
        # Month names for date extraction
        months = r"(January|February|March|April|May|June|July|August|September|October|November|December)"
        
        for phrase in phrases:
            # Find phrase position
            phrase_match = re.search(phrase, full_text, re.IGNORECASE)
            if phrase_match:
                # Extract text after phrase (up to 200 chars)
                start_pos = phrase_match.end()
                context = full_text[start_pos:start_pos + 200]
                
                # Extract date with month name
                date_pattern = rf"\b(\d{{1,2}}\s+{months}\s+\d{{4}})\b"
                date_match = re.search(date_pattern, context, re.IGNORECASE)
                if date_match:
                    date_value = date_match.group(1)
                    
                    # Extract trailing notes (TBC, estimated, provisional)
                    notes_pattern = r"(TBC|estimated|provisional|subject to|to be confirmed)"
                    notes_match = re.search(notes_pattern, context, re.IGNORECASE)
                    if notes_match:
                        notes = notes_match.group(1)
                        return f"{date_value}, {notes}"
                    
                    return date_value
        
        return ""
    
    def _extract_first_programme_submission(self, full_text: str) -> str:
        """Extract first programme submission interval from Section 3 only."""
        patterns = [
            r"first\s+programme[^\d]*(\d+\s+weeks?)",
            r"submit[^\d]*programme[^\d]*(\d+\s+weeks?)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                return self._ai_clean(match.group(1))
        
        return ""
    
    def _extract_revised_programme_interval(self, full_text: str) -> str:
        """Extract revised programme interval from Section 3 only."""
        patterns = [
            r"revised\s+programme[^\d]*(\d+\s+weeks?)",
            r"programme[^\d]*revised[^\d]*(\d+\s+weeks?)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                return self._ai_clean(match.group(1))
        
        return ""
    
    def _extract_delay_damages(self, full_text: str) -> str:
        """Extract delay damages from entire document (NO section slicing)."""
        # Search for X7 phrases in entire document
        x7_phrases = [
            r"\bX7\b",
            r"delay\s+damages",
            r"damages\s+for\s+delay",
        ]
        
        has_x7 = any(re.search(phrase, full_text, re.IGNORECASE) for phrase in x7_phrases)
        
        if not has_x7:
            return "not included"
        
        # Check for redacted values (████, ####, [REDACTED])
        redacted_patterns = [
            r"[█#\*]{3,}",
            r"\[REDACTED\]",
            r"redacted",
            r"confidential",
        ]
        
        is_redacted = any(re.search(pattern, full_text, re.IGNORECASE) for pattern in redacted_patterns)
        
        if is_redacted:
            return "specified but redacted"
        
        # Extract £ amount from entire document
        money_patterns = [
            r"£\s?([\d,]+(?:\.\d+)?)\s+per\s+(day|week)",
            r"([\d,]+(?:\.\d+)?)\s+per\s+(day|week)",
        ]
        
        amount = None
        unit = None
        for pattern in money_patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                amount = match.group(1)
                unit = match.group(2) if len(match.groups()) > 1 else None
                break
        
        if amount and unit:
            return f"£{amount} per {unit}"
        elif amount:
            return f"£{amount}"
        
        # Amount not found but X7 exists
        return "specified but redacted"
    
    def _extract_defects_date(self, full_text: str) -> str:
        """Extract defects date offset from Section 4 only."""
        # Search for defects date phrases
        phrases = [
            r"defects\s+date",
            r"period\s+between\s+completion\s+and\s+the\s+defects\s+date",
        ]
        
        for phrase in phrases:
            phrase_match = re.search(phrase, full_text, re.IGNORECASE)
            if phrase_match:
                # Extract text after phrase
                start_pos = phrase_match.end()
                context = full_text[start_pos:start_pos + 200]
                
                # Extract duration offset pattern: "X weeks/days after/from Completion"
                offset_pattern = r"(\d+)\s*(weeks?|days?)\s*(after|from)\s*Completion"
                offset_match = re.search(offset_pattern, context, re.IGNORECASE)
                if offset_match:
                    number = offset_match.group(1)
                    unit = offset_match.group(2)
                    preposition = offset_match.group(3)
                    return f"{number} {unit} {preposition} Completion"
        
        return ""
    
    def _extract_defect_correction_period(self, full_text: str) -> str:
        """Extract defect correction period from Section 4 only."""
        # Search for correction period phrases
        phrases = [
            r"defect\s+correction\s+period",
            r"correction\s+period",
            r"is\s+corrected\s+within",
        ]
        
        for phrase in phrases:
            phrase_match = re.search(phrase, full_text, re.IGNORECASE)
            if phrase_match:
                # Extract text after phrase
                start_pos = phrase_match.end()
                context = full_text[start_pos:start_pos + 100]
                
                # Extract numeric duration
                duration_pattern = r"(\d+)\s*(weeks?|days?)"
                duration_match = re.search(duration_pattern, context, re.IGNORECASE)
                if duration_match:
                    number = duration_match.group(1)
                    unit = duration_match.group(2)
                    return f"{number} {unit}"
        
        return ""
    
    def _extract_assessment_interval(self, full_text: str) -> str:
        """Extract assessment interval from Section 5 only."""
        # Search for assessment interval phrases
        phrases = [
            r"assessment\s+interval",
            r"interval\s+between\s+assessments",
            r"assessment\s+period",
        ]
        
        for phrase in phrases:
            phrase_match = re.search(phrase, full_text, re.IGNORECASE)
            if phrase_match:
                # Extract text after phrase
                start_pos = phrase_match.end()
                context = full_text[start_pos:start_pos + 100]
                
                # Extract numeric duration
                duration_pattern = r"(\d+)\s*(weeks?|days?)"
                duration_match = re.search(duration_pattern, context, re.IGNORECASE)
                if duration_match:
                    number = duration_match.group(1)
                    unit = duration_match.group(2)
                    return f"{number} {unit}"
        
        return ""
    
    def _extract_payment_period(self, full_text: str) -> str:
        """Extract payment period from Section 5 only."""
        # Search for payment period phrases
        phrases = [
            r"paid\s+within",
            r"payment\s+period",
            r"payment\s+is\s+made\s+within",
        ]
        
        for phrase in phrases:
            phrase_match = re.search(phrase, full_text, re.IGNORECASE)
            if phrase_match:
                # Extract text after phrase
                start_pos = phrase_match.end()
                context = full_text[start_pos:start_pos + 100]
                
                # Extract numeric duration
                duration_pattern = r"(\d+)\s*(weeks?|days?)"
                duration_match = re.search(duration_pattern, context, re.IGNORECASE)
                if duration_match:
                    number = duration_match.group(1)
                    unit = duration_match.group(2)
                    return f"{number} {unit}"
        
        return ""
    
    def _extract_retention_percentage(self, full_text: str) -> str:
        """Extract retention percentage from Section 5 only."""
        # Search for retention phrases
        phrases = [
            r"the\s+retention\s+percentage\s+is",
            r"retention\s+is",
        ]
        
        for phrase in phrases:
            phrase_match = re.search(phrase, full_text, re.IGNORECASE)
            if phrase_match:
                # Extract text after phrase
                start_pos = phrase_match.end()
                context = full_text[start_pos:start_pos + 50]
                
                # Extract percentage
                percentage_pattern = r"\b(\d{1,2}%)\b"
                percentage_match = re.search(percentage_pattern, context, re.IGNORECASE)
                if percentage_match:
                    return percentage_match.group(1)
        
        return ""
    
    def _extract_bond_amount(self, full_text: str) -> str:
        """Extract bond amount from Section 5 only."""
        pattern = r"bond(?: amount)?[: ]+£?([\d,]+)"
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            return self._ai_clean(f"£{match.group(1)}")
        
        return ""
    
    def _extract_weather_location(self, full_text: str) -> str:
        """Extract weather recording location from Section 6 only."""
        # Search for weather-related phrases
        phrases = [
            r"weather\s+station",
            r"weather\s+measurements",
            r"met\s+office",
        ]
        
        for phrase in phrases:
            phrase_match = re.search(phrase, full_text, re.IGNORECASE)
            if phrase_match:
                # Extract location name (capitalized word sequence)
                start_pos = phrase_match.end()
                context = full_text[start_pos:start_pos + 100]
                
                # Look for location name (capitalized words)
                location_pattern = r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)"
                location_match = re.search(location_pattern, context)
                if location_match:
                    location = location_match.group(1).strip()
                    # Filter out common words
                    if location.lower() not in ["the", "and", "or", "for", "with", "from"]:
                        return location
        
        return ""
    
    def _extract_weather_source(self, full_text: str) -> str:
        """Extract historical weather source from Section 6 only."""
        # Search for weather data phrases
        phrases = [
            r"met\s+office",
            r"weather\s+data",
            r"historic\s+weather",
            r"weather\s+monitoring",
        ]
        
        # Default to Met Office unless explicitly overridden
        has_met_office = re.search(r"met\s+office", full_text, re.IGNORECASE)
        if has_met_office:
            return "Met Office"
        
        # Look for alternative sources
        for phrase in phrases:
            phrase_match = re.search(phrase, full_text, re.IGNORECASE)
            if phrase_match:
                # Extract source name
                start_pos = phrase_match.end()
                context = full_text[start_pos:start_pos + 100]
                
                source_pattern = r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)"
                source_match = re.search(source_pattern, context)
                if source_match:
                    source = source_match.group(1).strip()
                    if source.lower() not in ["the", "and", "or", "for", "with", "from"]:
                        return source
        
        # Default to Met Office
        return "Met Office"
    
    def _ai_clean(self, value: str) -> str:
        """
        STAGE 4 — AI REFINER
        
        Clean extracted value:
        - Extract only the number/date/£
        - Remove any sentence over 20 words
        - Remove clause references
        - Reject hallucinations
        - If no clean value extracted → return "not specified"
        """
        if not value:
            return "not specified"
        
        value = value.strip()
        
        # Remove clause references
        value = re.sub(r'clause\s+\d+\.\d+|see\s+section\s+\d+|section\s+\d+', '', value, flags=re.IGNORECASE)
        
        # Remove sentences over 20 words
        words = value.split()
        if len(words) > 20:
            # Try to extract just the date/number/amount
            date_match = re.search(r'(\d{1,2}\s+[A-Za-z]+\s+\d{4}|\d{1,2}/\d{1,2}/\d{4})', value, re.IGNORECASE)
            if date_match:
                return date_match.group(1)
            
            money_match = re.search(r'£[\d,]+(?:\.\d+)?', value)
            if money_match:
                return money_match.group(0)
            
            duration_match = re.search(r'\d+\s+weeks?', value, re.IGNORECASE)
            if duration_match:
                return duration_match.group(0)
            
            return "not specified"
        
        # Reject hallucinations
        if self._is_hallucination(value):
            return "not specified"
        
        # Clean up value
        value = self._clean_value(value)
        
        return value if value else "not specified"
    
    def _extract_value_from_text(self, text: str, field_name: str) -> str:
        """
        Extract literal value from text using deterministic patterns.
        
        Field-specific extraction rules:
        1. Starting Date: Extract first valid date
        2. Access Dates: Extract ALL dates
        3. Completion Date: Extract single date
        4. Programme fields: Extract duration only
        5. Delay Damages: Only from X7 section
        6. Defects: Extract duration/date
        7. Weather: Extract location/measurements
        """
        # Field-specific extraction
        if field_name == "starting_date":
            # Extract first valid date after "starting date" phrase
            for pattern in self.compiled_date_patterns:
                matches = pattern.findall(text)
                if matches:
                    return matches[0].strip()
        
        elif field_name == "access_dates":
            # Extract ALL dates from Section 3 (Time) block
            # Search for dates near "access" keywords
            dates = []
            
            # Look for access-related phrases
            access_keywords = [
                r'access\s+dates?\s+are',
                r'access\s+to\s+the\s+site',
                r'access\s+to\s+the\s+working\s+areas',
                r'the\s+employer\s+gives\s+access',
                r'access\s+will\s+be\s+given',
                r'access\s+date',
            ]
            
            # Find lines with access keywords
            lines = text.split('\n')
            for line in lines:
                for keyword_pattern in access_keywords:
                    if re.search(keyword_pattern, line, re.IGNORECASE):
                        # Extract all dates from this line and nearby lines
                        context = line
                        line_idx = lines.index(line)
                        # Include next 2 lines for context
                        for i in range(line_idx + 1, min(len(lines), line_idx + 3)):
                            context += " " + lines[i]
                        
                        # Extract dates from context
                        for pattern in self.compiled_date_patterns:
                            matches = pattern.findall(context)
                            dates.extend(matches)
                        break
            
            # Also search for dates in tables (if text contains table-like structure)
            if not dates:
                # Direct date extraction from text
                for pattern in self.compiled_date_patterns:
                    matches = pattern.findall(text)
                    dates.extend(matches)
            
            # Remove duplicates and validate
            unique_dates = []
            seen = set()
            for date in dates:
                date_clean = date.strip()
                # Reject if date is part of a long sentence (> 25 words)
                if len(date_clean.split()) <= 3:  # Date should be short
                    if date_clean not in seen:
                        seen.add(date_clean)
                        unique_dates.append(date_clean)
            
            if unique_dates:
                # Return comma-separated for multi-value parsing
                return ", ".join(unique_dates)
            return ""
        
        elif field_name == "completion_date":
            # Extract single date, prioritize "Completion Date for the whole of the works"
            completion_match = re.search(
                r'Completion\s+Date\s+for\s+the\s+whole[^\d]*(\d{1,2}\s+[A-Za-z]+\s+\d{4}|\d{1,2}/\d{1,2}/\d{4})',
                text,
                re.IGNORECASE
            )
            if completion_match:
                return completion_match.group(1).strip()
            # Fallback to any date
            for pattern in self.compiled_date_patterns:
                matches = pattern.findall(text)
                if matches:
                    return matches[0].strip()
        
        elif field_name == "first_programme_submission":
            # Extract only number + unit (e.g., "4 weeks")
            for pattern in self.compiled_duration_patterns:
                match = pattern.search(text)
                if match:
                    return match.group(0).strip()
            # Look for "within X weeks" pattern
            within_match = re.search(r'within\s+(\d+\s+weeks?)', text, re.IGNORECASE)
            if within_match:
                return within_match.group(1).strip()
        
        elif field_name == "revised_programme_interval":
            # Extract duration from "revised programmes" context
            for pattern in self.compiled_duration_patterns:
                match = pattern.search(text)
                if match:
                    return match.group(0).strip()
            # Look for "every X weeks" or "intervals no longer than X weeks"
            interval_match = re.search(r'(?:every|intervals\s+no\s+longer\s+than)\s+(\d+\s+weeks?)', text, re.IGNORECASE)
            if interval_match:
                return interval_match.group(1).strip()
        
        elif field_name == "delay_damages":
            # ONLY extract from Option X7 section
            # Check if we're in X7 section (must contain "X7" or "option X7" or "Delay damages" or "for delay")
            x7_indicators = [
                r'\bx7\b',
                r'option\s+x7',
                r'delay\s+damages',
                r'for\s+delay',
            ]
            is_x7_section = any(re.search(indicator, text, re.IGNORECASE) for indicator in x7_indicators)
            
            if not is_x7_section:
                return ""  # Not in X7 section, skip
            
            # Check for "not applicable"
            if re.search(r'not\s+applicable', text, re.IGNORECASE):
                return "not applicable"
            
            # Check for redacted values (████ or unclear)
            if re.search(r'[█#\*]{3,}|redacted|unclear', text, re.IGNORECASE):
                return "not specified"
            
            # Extract money amount with patterns:
            # "delay damages are £... per day/week"
            # "the rate of delay damages is..."
            # "£[number] per [day/week]"
            delay_patterns = [
                r'delay\s+damages\s+are\s+([£$€]\s*[\d,]+(?:\.[\d]{2})?)\s+per\s+(day|week)',
                r'rate\s+of\s+delay\s+damages\s+is\s+([£$€]\s*[\d,]+(?:\.[\d]{2})?)\s+per\s+(day|week)',
                r'([£$€]\s*[\d,]+(?:\.[\d]{2})?)\s+per\s+(day|week)',
            ]
            
            for pattern in delay_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    amount = match.group(1).strip()
                    unit = match.group(2).strip() if len(match.groups()) > 1 else ""
                    if unit:
                        return f"{amount} per {unit}"
                    return amount
            
            # Fallback to generic money pattern
            for pattern in self.compiled_money_patterns:
                match = pattern.search(text)
                if match:
                    return match.group(0).strip()
            
            # If redacted or not present, return "not specified"
            return "not specified"
        
        elif field_name == "defects_date":
            # Extract from Section 4 (Quality Management)
            # Search for key phrases: "defects date is", "after Completion ... the defects date", "52 weeks after Completion"
            defects_patterns = [
                r'defects\s+date\s+is\s+(\d+\s+weeks?\s+after\s+Completion|\d{1,2}\s+[A-Za-z]+\s+\d{4})',
                r'the\s+defects\s+date\s+is\s+(\d+\s+weeks?\s+after\s+Completion|\d{1,2}\s+[A-Za-z]+\s+\d{4})',
                r'after\s+Completion[^\d]*the\s+defects\s+date[^\d]*(\d+\s+weeks?)',
                r'(\d+\s+weeks?\s+after\s+Completion)',
            ]
            
            # Find the pattern closest to "defects date" keyword
            best_match = None
            min_distance = float('inf')
            
            for pattern in defects_patterns:
                matches = list(re.finditer(pattern, text, re.IGNORECASE))
                for match in matches:
                    # Find distance to nearest "defects date" keyword
                    match_pos = match.start()
                    defects_keyword_pos = text.lower().find("defects date", max(0, match_pos - 100), match_pos + 100)
                    if defects_keyword_pos != -1:
                        distance = abs(match_pos - defects_keyword_pos)
                        if distance < min_distance:
                            min_distance = distance
                            best_match = match
            
            if best_match:
                return best_match.group(1).strip()
            
            # Fallback: extract any duration near "defects"
            for pattern in self.compiled_duration_patterns:
                match = pattern.search(text)
                if match:
                    return match.group(0).strip()
        
        elif field_name == "defect_correction_period":
            # Extract from Section 4 (Quality Management)
            # Search for key phrases: "defect correction period is", "the defect correction period is", "correction period:", "within [X] weeks"
            correction_patterns = [
                r'defect\s+correction\s+period\s+is\s+(\d+\s+weeks?)',
                r'the\s+defect\s+correction\s+period\s+is\s+(\d+\s+weeks?)',
                r'correction\s+period[^\d]*(\d+\s+weeks?)',
                r'within\s+(\d+\s+weeks?)',
            ]
            
            # Find the pattern closest to "defect correction period" keyword
            best_match = None
            min_distance = float('inf')
            
            for pattern in correction_patterns:
                matches = list(re.finditer(pattern, text, re.IGNORECASE))
                for match in matches:
                    # Find distance to nearest "defect correction period" keyword
                    match_pos = match.start()
                    keyword_pos = text.lower().find("defect correction period", max(0, match_pos - 100), match_pos + 100)
                    if keyword_pos != -1:
                        distance = abs(match_pos - keyword_pos)
                        if distance < min_distance:
                            min_distance = distance
                            best_match = match
            
            if best_match:
                return best_match.group(1).strip()
            
            # Fallback: extract any duration
            for pattern in self.compiled_duration_patterns:
                match = pattern.search(text)
                if match:
                    return match.group(0).strip()
        
        elif field_name == "weather_recording_location":
            # Extract location after "recorded at" or "Met Office"
            location_match = re.search(
                r'(?:recorded\s+at|weather\s+station)\s+([A-Z][A-Za-z\s]+?)(?:\.|$|\n)',
                text,
                re.IGNORECASE
            )
            if location_match:
                return location_match.group(1).strip()
            # Check for "Met Office"
            if re.search(r'met\s+office', text, re.IGNORECASE):
                return "Met Office"
        
        elif field_name == "weather_measurements":
            # Extract measurement types
            measurements = []
            measurement_keywords = [
                r'cumulative\s+rainfall',
                r'days\s+with\s+rainfall',
                r'days\s+with\s+snow',
                r'days\s+with\s+min\s+temp',
                r'rainfall',
                r'temperature',
                r'wind\s+speed',
            ]
            for keyword in measurement_keywords:
                if re.search(keyword, text, re.IGNORECASE):
                    measurements.append(keyword.replace(r'\s+', ' ').replace(r'\\', ''))
            if measurements:
                return ", ".join(measurements)
        
        elif field_name == "historical_weather_source":
            # MUST extract "Met Office"
            if re.search(r'met\s+office', text, re.IGNORECASE):
                return "Met Office"
        
        # Payment Terms (Section 5 only)
        elif field_name == "assessment_interval":
            # Extract from Section 5 (Payment)
            # Look for "assessment interval" or "each assessment interval is"
            assessment_patterns = [
                r'assessment\s+interval\s+is\s+(\d+\s+weeks?)',
                r'each\s+assessment\s+interval\s+is\s+(\d+\s+weeks?)',
                r'assessment\s+interval[^\d]*(\d+\s+weeks?)',
            ]
            for pattern in assessment_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    return match.group(1).strip()
            # Fallback to duration pattern
            for pattern in self.compiled_duration_patterns:
                match = pattern.search(text)
                if match:
                    return match.group(0).strip()
        
        elif field_name == "payment_period":
            # Extract from Section 5 (Payment)
            # Look for "the payment period is"
            payment_patterns = [
                r'payment\s+period\s+is\s+(\d+\s+weeks?)',
                r'the\s+payment\s+period\s+is\s+(\d+\s+weeks?)',
            ]
            for pattern in payment_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    return match.group(1).strip()
            # Fallback to duration pattern
            for pattern in self.compiled_duration_patterns:
                match = pattern.search(text)
                if match:
                    return match.group(0).strip()
        
        elif field_name == "retention_percentage":
            # Extract from Section 5 (Payment)
            # Look for "retention is ...%", "retention percentage", "retains ...%"
            retention_patterns = [
                r'retention\s+is\s+(\d+%)',
                r'retention\s+percentage[^\d]*(\d+%)',
                r'retention\s+amount[^\d]*(\d+%)',
                r'retains\s+(\d+%)',
                r'retention[^\d]*(\d+%)',
            ]
            for pattern in retention_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    return match.group(1).strip()
            # Fallback to percentage pattern
            percentage_match = re.search(r'(\d+%)', text)
            if percentage_match:
                return percentage_match.group(1).strip()
        
        # Generic extraction for other fields
        # Try date patterns
        for pattern in self.compiled_date_patterns:
            matches = pattern.findall(text)
            if matches:
                return matches[0].strip()
        
        # Try money patterns
        if "retention" in field_name or "bond" in field_name:
            for pattern in self.compiled_money_patterns:
                match = pattern.search(text)
                if match:
                    return match.group(0).strip()
        
        # Try duration patterns
        if "interval" in field_name or "period" in field_name:
            for pattern in self.compiled_duration_patterns:
                match = pattern.search(text)
                if match:
                    return match.group(0).strip()
        
        return ""
    
    def _needs_ai_override(self, value: str, full_text: str, field_name: str) -> bool:
        """
        Determine if AI override is needed.
        
        AI override needed if:
        - Value is empty
        - Value is too short (< 4 chars)
        - Value is too long (> 80 chars) - contains sentences
        - Value contains no numbers/dates/money
        - Value appears to be hallucinated
        - Value is just the label text
        - Value doesn't match sanity filter for the field type
        """
        if not value or value.strip() == "":
            return True
        
        # Too short
        if len(value.strip()) < 4:
            return True
        
        # Too long (likely a sentence, not a value)
        if len(value) > 80:
            return True
        
        # Contains no numbers/dates/money patterns
        has_date = any(p.search(value) for p in self.compiled_date_patterns)
        has_money = any(p.search(value) for p in self.compiled_money_patterns)
        has_duration = any(p.search(value) for p in self.compiled_duration_patterns)
        has_number = re.search(r'\d', value)
        
        if not (has_date or has_money or has_duration or has_number):
            return True
        
        # Appears to be hallucinated (common garbage patterns)
        garbage_patterns = [
            r'^yap', r'^the\s+starting\s+date', r'^the\s+completion\s+date', 
            r'^is$', r'^for\s+the\s+whole', r'^the\s+contractor', r'^the\s+employer'
        ]
        if any(re.search(p, value, re.IGNORECASE) for p in garbage_patterns):
            return True
        
        # Value is just the label (left-hand column)
        label_patterns = self.compiled_keyword_patterns.get(field_name, [])
        for pattern in label_patterns:
            if pattern.search(value):
                return True
        
        # Sanity filter: Check if value matches expected format for field type
        if not self._passes_sanity_filter(value, field_name):
            return True
        
        # Contains multiple sentences (indicates extraction captured too much)
        if value.count('.') > 1 or 'and the' in value.lower() or 'which' in value.lower():
            return True
        
        return False
    
    def _passes_sanity_filter(self, value: str, field_name: str) -> bool:
        """
        Sanity filter for date/number fields.
        
        Valid formats:
        - DD Month YYYY
        - DD/MM/YYYY
        - Month YYYY
        - "52 weeks", "4 weeks" etc.
        - Currency amounts
        - Percentages
        """
        # Date fields must match date patterns
        if "date" in field_name.lower():
            date_formats = [
                r'\d{1,2}\s+[A-Za-z]+\s+\d{4}',  # DD Month YYYY
                r'\d{1,2}/\d{1,2}/\d{4}',  # DD/MM/YYYY
                r'[A-Za-z]+\s+\d{4}',  # Month YYYY
                r'\d+\s+weeks?\s+after',  # 52 weeks after Completion
            ]
            if not any(re.search(p, value, re.IGNORECASE) for p in date_formats):
                return False
        
        # Duration fields must match duration patterns
        if "period" in field_name.lower() or "interval" in field_name.lower() or "programme" in field_name.lower():
            duration_formats = [
                r'\d+\s+(?:week|weeks|day|days|month|months)',
                r'\d+\s+weeks?\s+after',
            ]
            if not any(re.search(p, value, re.IGNORECASE) for p in duration_formats):
                return False
        
        # Money fields must match money patterns
        if "damages" in field_name.lower() or "retention" in field_name.lower():
            money_formats = [
                r'[£$€]\s*[\d,]+',
                r'not\s+specified',
            ]
            if not any(re.search(p, value, re.IGNORECASE) for p in money_formats):
                return False
        
        return True
    
    def _ai_extract_value(self, field_name: str, context_text: str) -> str:
        """
        Uses LLM to extract ONLY the actual variable for a NEC field.
        
        Field-specific AI extraction with strict rules:
        - Extract ONLY dates, durations, numbers, places
        - Never return sentences or paragraphs
        - Block hallucinations
        - Return "not specified" if value not found
        """
        if not self.azure_client:
            return ""
        
        # Field-specific extraction rules
        field_rules = {
            "starting_date": {
                "description": "the starting date",
                "look_for": "The starting date is",
                "format": "DD Month YYYY or DD/MM/YYYY",
                "example": "28 March 2023"
            },
            "access_dates": {
                "description": "the access date(s) - return ALL dates if multiple",
                "look_for": "The access dates are",
                "format": "DD Month YYYY (comma-separated if multiple)",
                "example": "20 March 2023",
                "section": "Section 3 (Time)"
            },
            "completion_date": {
                "description": "the completion date",
                "look_for": "Completion Date for the whole of the works is",
                "format": "DD Month YYYY",
                "example": "31 March 2024"
            },
            "first_programme_submission": {
                "description": "the period within which first programme must be submitted",
                "look_for": "within which the Contractor is to submit a first programme",
                "format": "number + unit (e.g., '4 weeks')",
                "example": "4 weeks"
            },
            "revised_programme_interval": {
                "description": "the interval for revised programmes",
                "look_for": "submits revised programmes",
                "format": "number + unit (e.g., '4 weeks')",
                "example": "4 weeks"
            },
            "delay_damages": {
                "description": "delay damages amount",
                "look_for": "Option X7 section ONLY",
                "format": "currency amount or 'not specified' if redacted",
                "example": "£250,000 per week or 'not specified'",
                "restriction": "ONLY extract from Option X7, not from other sections"
            },
            "defects_date": {
                "description": "the defects date or period",
                "look_for": "defects date or period between Completion and defects date",
                "format": "duration (e.g., '52 weeks after Completion')",
                "example": "52 weeks after Completion"
            },
            "defect_correction_period": {
                "description": "the defect correction period",
                "look_for": "defect correction period is",
                "format": "duration (e.g., '2 weeks')",
                "example": "2 weeks"
            },
            "weather_recording_location": {
                "description": "weather recording location",
                "look_for": "weather is recorded at",
                "format": "location name",
                "example": "Ilkley or Met Office"
            },
            "weather_measurements": {
                "description": "weather measurement types",
                "look_for": "cumulative rainfall, days with rainfall, days with snow, days with min temp",
                "format": "comma-separated list",
                "example": "rainfall, temperature, wind speed"
            },
            "historical_weather_source": {
                "description": "historical weather data source",
                "look_for": "Met Office",
                "format": "source name",
                "example": "Met Office",
                "must_extract": "Met Office"
            },
        }
        
        field_rule = field_rules.get(field_name, {})
        field_desc = field_rule.get("description", field_name)
        look_for = field_rule.get("look_for", "")
        format_desc = field_rule.get("format", "")
        example = field_rule.get("example", "")
        restriction = field_rule.get("restriction", "")
        must_extract = field_rule.get("must_extract", "")
        
        # Semantic fallback meanings for AI
        semantic_meanings = {
            "starting_date": "When does the project start?",
            "access_dates": "When can the contractor access the site?",
            "delay_damages": "What are the delay penalties?",
            "defects_date": "How long after completion are defects corrected?",
            "defect_correction_period": "What is the defect correction period?",
            "assessment_interval": "How often is payment assessed?",
            "payment_period": "What is the payment period?",
        }
        semantic_meaning = semantic_meanings.get(field_name, "")
        
        prompt = f"""Extract ONLY the actual value for this NEC contract field. Return ONLY the value, no surrounding text.

Field: {field_desc}
Look for: {look_for}
Format: {format_desc}
Example: {example}
{f'Restriction: {restriction}' if restriction else ''}
{f'MUST extract: {must_extract}' if must_extract else ''}
{f'Semantic meaning: {semantic_meaning}' if semantic_meaning else ''}

CRITICAL RULES:
1. Extract ONLY the value (date, number, duration, location name)
2. Extract the NEAREST date/number/duration/amount to the keyword phrase
3. If multiple values exist (e.g., multiple access dates), return ALL separated by commas
4. NEVER return sentences, paragraphs, or labels
5. NEVER return text like "The starting date is" or "for the whole of the works is"
6. NEVER hallucinate or invent values - only extract values that truly exist in the contract
7. If value is redacted or not present, return "not specified"
8. Block hallucinations like "yap" or meaningless text
9. Reject blocks with no numeric/date patterns, over 25 words, or contract references
10. Output ONLY real text that exists in the PDF

Contract text:
{context_text[:8000]}

Extract ONLY the value for {field_name}. Return JSON: {{"value": "..."}}"""

        try:
            response = self.azure_client.chat.completions.create(
                model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini"),
                messages=[
                    {
                        "role": "system",
                        "content": "You extract ONLY literal values from NEC contracts. Never return sentences, paragraphs, or hallucinations. Block invented text. Return JSON with 'value' field. If value not found, return 'not specified'."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.0,
                max_tokens=100,
                response_format={"type": "json_object"}
            )
            
            result = response.choices[0].message.content.strip()
            
            # Parse JSON response
            import json
            try:
                parsed = json.loads(result)
                value = parsed.get("value", "").strip()
                
                # Clean value
                value = self._clean_value(value)
                
                # Block hallucinations
                if self._is_hallucination(value):
                    self.log(f"Blocked hallucination: {value}")
                    return "not specified"
                
                # Reject blocks with no numeric/date patterns, over 25 words, or multiple unrelated numbers
                if value:
                    words = value.split()
                    if len(words) > 25:
                        self.log(f"Value too long ({len(words)} words), rejecting: {value[:50]}")
                        return "not specified"
                    
                    # Check for contract references (clause numbers, section references)
                    if re.search(r'clause\s+\d+\.\d+|see\s+section\s+\d+|section\s+\d+', value, re.IGNORECASE):
                        self.log(f"Value contains contract reference, rejecting: {value}")
                        return "not specified"
                
                # AI is allowed to trim/extract - only validate sanity filter
                if value and value.lower() not in ["not specified", "not stated", "not found", "n/a", "not applicable", "not included", "specified but redacted"]:
                    # Apply sanity filter
                    if self._passes_sanity_filter(value, field_name):
                        return value
                    else:
                        self.log(f"Value failed sanity filter: {value}")
                        return "not specified"
                
                return value if value else "not specified"
            except json.JSONDecodeError:
                # Fallback: try to extract value from response
                value = result.strip('"\'{}')
                value = self._clean_value(value)
                if self._is_hallucination(value):
                    return "not specified"
                return value if value else "not specified"
        
        except Exception as e:
            self.log(f"AI extraction failed for {field_name}: {e}")
            return "not specified"
    
    def _is_hallucination(self, value: str) -> bool:
        """Check if value appears to be hallucinated."""
        if not value:
            return False
        
        # Common hallucination patterns
        hallucination_patterns = [
            r'^yap',
            r'^the\s+starting\s+date\s+is',
            r'^the\s+completion\s+date',
            r'^is$',
            r'^for\s+the\s+whole',
            r'^the\s+contractor',
            r'^the\s+employer',
            r'^according\s+to',
            r'^as\s+stated',
        ]
        
        # Check if value matches hallucination patterns
        if any(re.search(p, value, re.IGNORECASE) for p in hallucination_patterns):
            return True
        
        # Check if value is too generic or meaningless
        meaningless = ["is", "are", "the", "a", "an", "and", "or", "but"]
        if value.lower().strip() in meaningless:
            return True
        
        return False
    
    def _clean_value(self, value: str) -> str:
        """Clean extracted value."""
        if not value:
            return ""
        
        # Remove quotes
        value = value.strip('"\'')
        
        # Remove common prefixes
        prefixes = ["The value is:", "Value:", "Extracted:", "Answer:"]
        for prefix in prefixes:
            if value.lower().startswith(prefix.lower()):
                value = value[len(prefix):].strip()
        
        # Remove trailing punctuation (except % and currency)
        value = re.sub(r'[^\w\s\-/%,£$€]+$', '', value)
        
        return value.strip()
    
    def _validate_value_in_text(self, value: str, full_text: str) -> bool:
        """
        Validate that extracted value appears in contract text.
        
        This is a PERMISSIVE validator - allows AI to trim/extract values.
        Only checks that key components (dates, numbers) are present.
        """
        if not value or value.lower() in ["not stated", "not found", "n/a", "not specified", "not included", "specified but redacted"]:
            return True
        
        # For dates, check if date components appear (permissive - allows reformatting)
        date_match = re.search(r'(\d{1,2}\s+\w+\s+\d{4}|\d{1,2}/\d{1,2}/\d{4}|\d{4})', value, re.IGNORECASE)
        if date_match:
            # Extract date components
            date_components = re.findall(r'\d+', date_match.group(1))
            # Check if any date components appear in text
            for component in date_components:
                if component in full_text:
                    return True
        
        # For numbers/amounts, check if number appears
        number_match = re.search(r'(\d[\d,\.]*)', value)
        if number_match:
            number_str = number_match.group(1).replace(',', '').replace('.', '')
            if number_str in full_text.replace(',', '').replace('.', ''):
                return True
        
        # For durations, check if number + unit appear
        duration_match = re.search(r'(\d+)\s*(week|day|month)', value, re.IGNORECASE)
        if duration_match:
            number = duration_match.group(1)
            unit = duration_match.group(2)
            if number in full_text and unit.lower() in full_text.lower():
                return True
        
        # For percentages, check if number + % appear
        percentage_match = re.search(r'(\d+)%', value)
        if percentage_match:
            number = percentage_match.group(1)
            if number in full_text and '%' in full_text:
                return True
        
        # If value is short and contains key components, allow it
        if len(value) < 50:
            return True
        
        return False
    
    def _parse_multi_value(self, value: str) -> List[str]:
        """Parse multi-value fields (access_dates, etc.)."""
        if not value:
            return []
        
        # Split by comma, semicolon, or "and"
        values = re.split(r'[,;]|\s+and\s+', value)
        cleaned = [self._clean_value(v.strip()) for v in values if v.strip()]
        
        return cleaned
    
    def extract_scope_constraints_milestones(self, clean_text: str) -> Dict[str, Any]:
        """
        Extract scope, constraints, and milestones using AI semantic extraction.
        
        These sections vary heavily by contract and require LLM-based analysis.
        
        Keyword sections to extract from:
        - "Scope"
        - "Works Information"
        - "Constraints on the Contractor"
        - "Completion milestones"
        - "Key Dates" (but not weather key dates)
        
        Args:
            clean_text: Full clean text from PDF
            
        Returns:
            Dictionary with scope_items, constraints, milestones
        """
        if not self.azure_client:
            return {"scope_items": [], "constraints": [], "milestones": []}
        
        self.log("Extracting scope, constraints, and milestones using AI semantic extraction")
        
        prompt = f"""Extract scope items, constraints, and milestones from this NEC contract.

Extract from these keyword sections:
- Scope: Look for "Scope", "The Scope is...", "Works Information", "Contractor's Responsibilities"
- Constraints: Look for "Constraints on the Contractor", site constraints, restrictions, environmental rules, working hours
- Milestones: Look for "Completion milestones", "Key Dates" (but NOT weather key dates), sectional completions, staged delivery requirements

Rules:
- Extract ONLY actual items/constraints/milestones as text
- Return as lists of strings
- Do NOT include section headers or labels
- Do NOT hallucinate - only extract what is actually stated
- If section not found, return empty list

Return JSON format:
{{
  "scope_items": ["item1", "item2", ...],
  "constraints": ["constraint1", "constraint2", ...],
  "milestones": ["milestone1", "milestone2", ...]
}}

Contract text:
{clean_text[:10000]}

Extract scope, constraints, and milestones:"""

        try:
            response = self.azure_client.chat.completions.create(
                model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini"),
                messages=[
                    {
                        "role": "system",
                        "content": "You extract scope items, constraints, and milestones from NEC contracts. Return JSON with lists. Do not hallucinate - only extract what is actually stated in the contract."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.0,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )
            
            result = response.choices[0].message.content.strip()
            
            import json
            try:
                parsed = json.loads(result)
                return {
                    "scope_items": parsed.get("scope_items", []),
                    "constraints": parsed.get("constraints", []),
                    "milestones": parsed.get("milestones", [])
                }
            except json.JSONDecodeError:
                self.log("Failed to parse AI response for scope/constraints/milestones")
                return {"scope_items": [], "constraints": [], "milestones": []}
        
        except Exception as e:
            self.log(f"AI extraction failed for scope/constraints/milestones: {e}")
            return {"scope_items": [], "constraints": [], "milestones": []}
