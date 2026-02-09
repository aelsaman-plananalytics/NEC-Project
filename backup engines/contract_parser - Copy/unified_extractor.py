"""
Unified NEC Contract Extraction System

Single extractor that combines:
1. Phrase-based deterministic scanning
2. AI-based value correction
3. Section-aware filtering
4. Scope/constraints/milestones extraction
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


class UnifiedExtractor:
    """
    Unified extractor for NEC contracts.
    
    Pipeline:
    1. Detect sections (Section 3, 4, 5, 6, Option X7)
    2. Extract scope/constraints/milestones (AI semantic)
    3. Phrase-based scanning for all fields
    4. AI correction for extracted values
    5. Enforce section constraints
    6. Return structured JSON
    """
    
    # Section mapping: field -> correct section
    FIELD_SECTIONS = {
        "starting_date": "section_3",
        "access_dates": "section_3",
        "completion_date": "section_3",
        "first_programme_submission": "section_3",
        "revised_programme_interval": "section_3",
        "delay_damages": "option_x7",
        "defects_date": "section_4",
        "defect_correction_period": "section_4",
        "assessment_interval": "section_5",
        "payment_period": "section_5",
        "retention_percentage": "section_5",
        "weather_location": "section_6",
        "weather_measurement_type": "section_6",
        "weather_historical_source": "section_6",
    }
    
    # Phrase patterns for each field
    PHRASE_PATTERNS = {
        "starting_date": [
            r"(starting\s+date(?:\s+is|:)?\s*)([^\n\.]+)",
            r"(start\s+date(?:\s+is|:)?\s*)([^\n\.]+)",
        ],
        "access_dates": [
            r"(access\s+to\s+the\s+site\s+is\s*)([^\n\.]+)",
            r"(access\s+dates?\s+(?:are|is)\s*)([^\n\.]+)",
            r"(the\s+site\s+is\s+available\s+from\s*)([^\n\.]+)",
        ],
        "completion_date": [
            r"(completion\s+date(?:\s+for\s+the\s+whole\s+of\s+the\s+works)?(?:\s+is|:)?\s*)([^\n\.]+)",
            r"(completion\s+is\s+due\s+on\s*)([^\n\.]+)",
        ],
        "first_programme_submission": [
            r"(the\s+period\s+after\s+the\s+contract\s+date\s+within\s+which\s+the\s+contractor\s+is\s+to\s+submit\s+a\s+first\s+programme\s*)([^\n\.]+)",
            r"(submit\s+a\s+first\s+programme\s*)([^\n\.]+)",
        ],
        "revised_programme_interval": [
            r"(the\s+contractor\s+submits\s+revised\s+programmes\s+at\s*)([^\n\.]+)",
            r"(revised\s+programmes\s+at\s*)([^\n\.]+)",
            r"(interval\s+for\s+revised\s+programmes\s*)([^\n\.]+)",
        ],
        "delay_damages": [
            r"(delay\s+damages\s+are\s*)([^\n\.]+)",
            r"(rate\s+of\s+delay\s+damages\s*)([^\n\.]+)",
        ],
        "defects_date": [
            r"(the\s+period\s+between\s+completion\s+.*?\s+and\s+the\s+defects\s+date\s+is\s*)([^\n\.]+)",
        ],
        "defect_correction_period": [
            r"(the\s+defect\s+correction\s+period\s+is\s*)([^\n\.]+)",
            r"(correction\s+period\s+is\s*)([^\n\.]+)",
        ],
        "assessment_interval": [
            r"(assessment\s+interval(?:\s+is|:)?\s*)([^\n\.]+)",
            r"(assessment\s+date(?:\s+is|:)?\s*)([^\n\.]+)",
        ],
        "payment_period": [
            r"(payment\s+is\s+made\s*)([^\n\.]+)",
            r"(payment\s+interval(?:\s+is|:)?\s*)([^\n\.]+)",
        ],
        "retention_percentage": [
            r"(retention(?:\s+percentage)?(?:\s+is|:)?\s*)([^\n\.]+)",
        ],
        "weather_location": [
            r"(the\s+place\s+where\s+weather\s+is\s+to\s+be\s+recorded\s+is\s*)([^\n\.]+)",
        ],
        "weather_measurement_type": [
            r"(the\s+weather\s+measurements.*?\s+are\s*)(.*?)(?:\n|\.|$)",
        ],
        "weather_historical_source": [
            r"(historical\s+records\s+are\s+supplied\s+by\s*)([^\n\.]+)",
        ],
    }
    
    # Date patterns
    DATE_PATTERNS = [
        r'\b(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})\b',
        r'\b((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})\b',
        r'\b(\d{1,2}/\d{1,2}/\d{4})\b',
        r'\b(\d{1,2}-\d{1,2}-\d{4})\b',
    ]
    
    # Duration patterns
    DURATION_PATTERNS = [
        r'(\d+)\s+(?:week|weeks|day|days|month|months)',
    ]
    
    # Currency patterns
    CURRENCY_PATTERNS = [
        r'[£$€]\s*([\d,]+(?:\.[\d]{2})?)\s+per\s+(?:day|week|month)',
        r'([\d,]+(?:\.[\d]{2})?)\s+per\s+(?:day|week|month)',
    ]
    
    # Percentage patterns
    PERCENTAGE_PATTERNS = [
        r'(\d+(?:\.\d+)?)%',
    ]
    
    def __init__(self, debug: bool = False, enable_ai: bool = True):
        """Initialize unified extractor."""
        self.debug = debug
        self.enable_ai = enable_ai
        self.azure_client = None
        self.sections = {}
        
        if self.enable_ai and OPENAI_AVAILABLE:
            endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
            api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
            if endpoint and api_key:
                self.azure_client = AzureOpenAI(
                    api_key=api_key,
                    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
                    azure_endpoint=endpoint
                )
    
    def log(self, msg: str):
        """Debug logging."""
        if self.debug:
            print(f"[UnifiedExtractor] {msg}")
    
    def extract(self, text: str, tables: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Main extraction method.
        
        Args:
            text: Clean text from PDF
            tables: Optional list of extracted tables
            
        Returns:
            Structured JSON with all extracted fields
        """
        self.log("Starting unified extraction")
        
        # Step 1: Detect sections
        self.sections = self.detect_sections(text)
        
        # Step 2: Extract scope/constraints/milestones (AI semantic)
        semantic_data = self.extract_scope_constraints_milestones(text)
        
        # Step 3: Phrase-based scanning for all fields
        raw_extractions = self.phrase_scan_all_fields(text)
        # Store for section checking
        self._raw_extractions = raw_extractions
        
        # Step 4: AI correction for extracted values
        corrected_extractions = self.ai_correct_values(raw_extractions, text)
        
        # Step 5: Enforce section constraints
        final_extractions = self.enforce_section_constraints(corrected_extractions)
        
        # Step 6: Build structured output
        return self.build_structured_output(final_extractions, semantic_data)
    
    def detect_sections(self, text: str) -> Dict[str, Tuple[int, int]]:
        """
        Detect NEC section boundaries.
        
        Returns:
            Dictionary mapping section names to (start_pos, end_pos) tuples
        """
        sections = {}
        
        # Section 3: Time
        section_3_patterns = [
            r"section\s+3\s*[:\-]?\s*time",
            r"3\s*[:\-]?\s*time",
        ]
        section_3_start = None
        for pattern in section_3_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                section_3_start = match.start()
                break
        
        # Section 4: Quality
        section_4_patterns = [
            r"section\s+4\s*[:\-]?\s*quality",
            r"4\s*[:\-]?\s*quality",
        ]
        section_4_start = None
        for pattern in section_4_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                section_4_start = match.start()
                break
        
        # Section 5: Payment
        section_5_patterns = [
            r"section\s+5\s*[:\-]?\s*payment",
            r"5\s*[:\-]?\s*payment",
        ]
        section_5_start = None
        for pattern in section_5_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                section_5_start = match.start()
                break
        
        # Section 6: Compensation events
        section_6_patterns = [
            r"section\s+6\s*[:\-]?\s*compensation",
            r"6\s*[:\-]?\s*compensation",
        ]
        section_6_start = None
        for pattern in section_6_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                section_6_start = match.start()
                break
        
        # Option X7: Delay damages
        x7_patterns = [
            r"option\s+x7",
            r"secondary\s+option\s+x7",
        ]
        x7_start = None
        for pattern in x7_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                x7_start = match.start()
                break
        
        # Determine section boundaries
        section_starts = {
            "section_3": section_3_start,
            "section_4": section_4_start,
            "section_5": section_5_start,
            "section_6": section_6_start,
            "option_x7": x7_start,
        }
        
        # Sort by position
        sorted_sections = sorted(
            [(k, v) for k, v in section_starts.items() if v is not None],
            key=lambda x: x[1]
        )
        
        # Assign boundaries
        for i, (section_name, start_pos) in enumerate(sorted_sections):
            if i + 1 < len(sorted_sections):
                end_pos = sorted_sections[i + 1][1]
            else:
                end_pos = len(text)
            sections[section_name] = (start_pos, end_pos)
        
        self.log(f"Detected {len(sections)} sections")
        return sections
    
    def extract_scope_constraints_milestones(self, text: str) -> Dict[str, Any]:
        """
        Extract scope, constraints, and milestones using AI semantic extraction.
        
        Returns:
            Dictionary with scope_items, constraints, milestones
        """
        if not self.azure_client:
            return {
                "scope_items": [],
                "constraints": [],
                "milestones": []
            }
        
        prompt = f"""Extract scope items, constraints, and milestones from this NEC contract.

CONTRACT TEXT:
{text[:5000]}

Extract:
1. SCOPE: Items listing works to be performed (from "Scope" section or sentences beginning "The scope is...")
2. CONSTRAINTS: Restrictions, obligations, warnings, things the Contractor "shall not" or "must" follow (from "Site Information" or similar)
3. MILESTONES: Dates other than start/completion dates, "The Contractor shall submit ... within ...", "By week ...", "Completion of X task by ..."

Return JSON:
{{
    "scope_items": ["item1", "item2", ...],
    "constraints": ["constraint1", "constraint2", ...],
    "milestones": ["milestone1", "milestone2", ...]
}}"""

        try:
            response = self.azure_client.chat.completions.create(
                model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini"),
                messages=[
                    {
                        "role": "system",
                        "content": "Extract scope items, constraints, and milestones from NEC contracts. Return JSON with arrays."
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
            return json.loads(result)
        
        except Exception as e:
            self.log(f"AI semantic extraction failed: {e}")
            return {
                "scope_items": [],
                "constraints": [],
                "milestones": []
            }
    
    def phrase_scan_all_fields(self, text: str) -> Dict[str, Dict[str, Any]]:
        """
        Scan all fields using phrase patterns.
        
        Returns:
            Dictionary mapping field names to extraction results:
            {
                "field_name": {
                    "value": "...",
                    "context": "...",
                    "section": "section_3",
                    "position": 1234
                }
            }
        """
        results = {}
        
        for field_name, patterns in self.PHRASE_PATTERNS.items():
            best_match = None
            best_context = ""
            best_section = None
            best_position = None
            
            for pattern in patterns:
                matches = list(re.finditer(pattern, text, re.IGNORECASE | re.DOTALL))
                for match in matches:
                    value = match.group(2).strip() if len(match.groups()) >= 2 else ""
                    if value:
                        # Extract context (200-300 chars)
                        start_pos = max(0, match.start() - 100)
                        end_pos = min(len(text), match.end() + 200)
                        context = text[start_pos:end_pos]
                        
                        # Determine which section this match is in
                        section = self._get_section_for_position(match.start())
                        
                        # Store best match (closest to correct section)
                        if not best_match or (section == self.FIELD_SECTIONS.get(field_name)):
                            best_match = value
                            best_context = context
                            best_section = section
                            best_position = match.start()
            
            if best_match:
                results[field_name] = {
                    "value": best_match,
                    "context": best_context,
                    "section": best_section,
                    "position": best_position
                }
                self.log(f"Found {field_name}: {best_match[:50]} (section: {best_section})")
        
        return results
    
    def ai_correct_values(self, raw_extractions: Dict[str, Dict[str, Any]], full_text: str) -> Dict[str, str]:
        """
        AI correction: Extract ONLY the exact date, number, or duration from context.
        
        Args:
            raw_extractions: Raw extraction results from phrase scanning
            full_text: Full contract text
            
        Returns:
            Dictionary mapping field names to corrected values
        """
        corrected = {}
        
        if not self.azure_client:
            # No AI - return raw values
            for field_name, data in raw_extractions.items():
                corrected[field_name] = data["value"]
            return corrected
        
        for field_name, data in raw_extractions.items():
            context = data["context"]
            raw_value = data["value"]
            
            # Field-specific guidance
            field_guidance = {
                "starting_date": "Extract ONLY the date (DD Month YYYY or DD/MM/YYYY format)",
                "access_dates": "Extract ALL dates (comma-separated if multiple)",
                "completion_date": "Extract ONLY the date (DD Month YYYY format)",
                "first_programme_submission": "Extract ONLY the duration (e.g., '4 weeks')",
                "revised_programme_interval": "Extract ONLY the duration (e.g., '4 weeks')",
                "delay_damages": "Extract ONLY the currency amount (e.g., '£250,000 per week')",
                "defects_date": "Extract ONLY the duration (e.g., '52 weeks after Completion')",
                "defect_correction_period": "Extract ONLY the duration (e.g., '2 weeks')",
                "assessment_interval": "Extract ONLY the duration or word (e.g., '4 weeks' or 'monthly')",
                "payment_period": "Extract ONLY the duration (e.g., '21 days')",
                "retention_percentage": "Extract ONLY the percentage (e.g., '3%')",
                "weather_location": "Extract ONLY the location name",
                "weather_measurement_type": "Extract ONLY the measurement types (comma-separated)",
                "weather_historical_source": "Extract ONLY the source name (usually 'Met Office')",
            }
            
            guidance = field_guidance.get(field_name, "Extract the value")
            
            prompt = f"""You must return ONLY the exact date, number, or duration found inside the provided text.

Field: {field_name}
{guidance}

CONTEXT TEXT:
{context}

CRITICAL RULES:
1. Extract ONLY the exact value (date, duration, amount, location, etc.)
2. It must appear EXACTLY in the context text
3. No rewriting. No hallucination.
4. If nothing is extractable, return: null

Return JSON: {{"value": "..." or null}}"""

            try:
                response = self.azure_client.chat.completions.create(
                    model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini"),
                    messages=[
                        {
                            "role": "system",
                            "content": "Extract ONLY the exact date, number, or duration from contract text. It must appear EXACTLY in the context. No rewriting. No hallucination. Return JSON with 'value' field."
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
                import json
                parsed = json.loads(result)
                ai_value = parsed.get("value", "")
                
                # Reject AI output if not in original text
                if ai_value and ai_value != "null" and ai_value.lower() != "null":
                    if self._value_exists_in_text(ai_value, context):
                        corrected[field_name] = ai_value
                        self.log(f"AI corrected {field_name}: {raw_value[:50]} → {ai_value[:50]}")
                    else:
                        # AI hallucinated - use raw value
                        corrected[field_name] = raw_value
                        self.log(f"AI value not in context, using raw: {field_name}")
                else:
                    # AI returned null - use raw value
                    corrected[field_name] = raw_value
                    self.log(f"AI returned null, using raw: {field_name}")
            
            except Exception as e:
                self.log(f"AI correction failed for {field_name}: {e}")
                corrected[field_name] = raw_value
        
        return corrected
    
    def enforce_section_constraints(self, extractions: Dict[str, str]) -> Dict[str, str]:
        """
        Enforce section constraints: discard values found in wrong sections.
        
        Args:
            extractions: Dictionary of field -> value mappings
            
        Returns:
            Filtered extractions with only values from correct sections
        """
        filtered = {}
        
        # Get raw extractions with section info (stored during phrase scanning)
        if not hasattr(self, '_raw_extractions'):
            self._raw_extractions = {}
        
        for field_name, value in extractions.items():
            if not value:
                continue
            
            expected_section = self.FIELD_SECTIONS.get(field_name)
            if not expected_section:
                # No section constraint - keep value
                filtered[field_name] = value
                continue
            
            # Check if value was found in correct section
            if field_name in self._raw_extractions:
                actual_section = self._raw_extractions[field_name].get("section")
                if actual_section == expected_section:
                    filtered[field_name] = value
                    self.log(f"Section check passed: {field_name} in {expected_section}")
                else:
                    self.log(f"Section check failed: {field_name} found in {actual_section}, expected {expected_section} - DISCARDED")
            else:
                # No section info - keep value (might be from AI correction)
                filtered[field_name] = value
        
        return filtered
    
    def build_structured_output(
        self,
        extractions: Dict[str, str],
        semantic_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build final structured JSON output.
        
        Args:
            extractions: Field -> value mappings
            semantic_data: Scope, constraints, milestones
            
        Returns:
            Structured JSON matching API expectations
        """
        # Parse access_dates (may be comma-separated)
        access_dates_str = extractions.get("access_dates", "")
        access_dates_list = []
        if access_dates_str:
            if isinstance(access_dates_str, list):
                access_dates_list = access_dates_str
            elif isinstance(access_dates_str, str):
                access_dates_list = [d.strip() for d in access_dates_str.split(",") if d.strip()]
        
        # Extract delay damages amount
        delay_damages = extractions.get("delay_damages", "")
        delay_damages_amount = ""
        if delay_damages:
            amount_match = re.search(r'([£$€]?\s*\d[\d,\.]*)\s*(per|a)\s*(day|week|month)', delay_damages, re.IGNORECASE)
            if amount_match:
                delay_damages_amount = amount_match.group(0).strip()
        
        return {
            "scope_items": semantic_data.get("scope_items", []),
            "constraints": semantic_data.get("constraints", []),
            "milestones": semantic_data.get("milestones", []),
            "contract_dates": {
                "starting_date": extractions.get("starting_date", ""),
                "access_dates": access_dates_list,
                "completion_date": extractions.get("completion_date", ""),
                "programme_submission_rules": extractions.get("first_programme_submission", ""),
                "programme_revision_rules": extractions.get("revised_programme_interval", ""),
            },
            "programme_requirements": {
                "submit_first_programme_within": extractions.get("first_programme_submission", ""),
                "revised_programme_interval": extractions.get("revised_programme_interval", ""),
            },
            "delay_damages": delay_damages,
            "delay_damages_amount": delay_damages_amount,
            "defects": {
                "defects_date": extractions.get("defects_date", ""),
                "defect_correction_period": extractions.get("defect_correction_period", ""),
            },
            "payment_terms": {
                "assessment_interval": extractions.get("assessment_interval", ""),
                "payment_period": extractions.get("payment_period", ""),
                "retention_percentage": extractions.get("retention_percentage", ""),
            },
            "weather_data": {
                "recording_location": extractions.get("weather_location", ""),
                "measurement_data": extractions.get("weather_measurement_type", ""),
                "historical_records_source": extractions.get("weather_historical_source", ""),
            },
            "key_dates": [],  # Will be populated separately if needed
            "contract_completeness": {
                "document_type": "completed" if extractions.get("starting_date") else "partial",
                "is_template": False
            }
        }
    
    def _get_section_for_position(self, position: int) -> Optional[str]:
        """Determine which section a position belongs to."""
        for section_name, (start_pos, end_pos) in self.sections.items():
            if start_pos <= position < end_pos:
                return section_name
        return None
    
    def _value_exists_in_text(self, value: str, text: str) -> bool:
        """Check if value exists in text (allowing minor formatting differences)."""
        if not value or not text:
            return False
        
        value_clean = value.strip().lower()
        text_lower = text.lower()
        
        # Exact match
        if value_clean in text_lower:
            return True
        
        # Check if all significant words appear
        value_words = [w for w in value_clean.split() if len(w) > 2]
        if value_words:
            all_words_present = all(word in text_lower for word in value_words)
            if all_words_present:
                return True
        
        # For dates: check if date components appear
        date_match = re.search(r'(\d{1,2}\s+\w+\s+\d{4}|\d{1,2}/\d{1,2}/\d{4})', value, re.IGNORECASE)
        if date_match:
            date_str = date_match.group(1)
            if date_str.lower() in text_lower:
                return True
        
        # For numbers: check if number appears
        number_match = re.search(r'(\d[\d,\.]*)', value)
        if number_match:
            number_str = number_match.group(1).replace(',', '').replace('.', '')
            if number_str in text.replace(',', '').replace('.', ''):
                return True
        
        return False
