"""
AI Validation & Correction Layer for NEC4 Contract Extraction (Option A Enhanced)

Uses AI to clean extracted values and ensure they match context.
Never hallucinates - only validates and corrects values present in contract.
"""

import re
import os
import json
from typing import Dict, Any, Optional, List

# LLM support
try:
    from openai import AzureOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    AzureOpenAI = None


class AICorrector:
    """
    AI validation and correction layer.
    
    Rules:
    1. clean() - If engine extracted a partial match → correct it
    2. clean() - If engine extracted something valid → return unchanged
    3. clean() - If engine extracted NONE → return None
    4. ai_fallback_extract() - FULL semantic extraction ONLY IF engine returned None
    5. NEVER fabricate values
    """
    
    def __init__(self, debug: bool = False, enable_ai: bool = True):
        """Initialize AI corrector."""
        self.debug = debug
        self.enable_ai = enable_ai
        self.azure_client = None
        
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
            print(f"[AI_CORRECTOR] {msg}")
    
    def clean(self, field_name: str, value: Optional[Any], context: str) -> Optional[Any]:
        """
        Clean extracted value using AI.
        
        Rules:
        - If engine extracted a partial match → correct it
        - If engine extracted something valid → return unchanged
        - If engine extracted NONE → return None
        - DO NOT fabricate values
        
        Args:
            field_name: Name of field being extracted
            value: Value extracted by phrase extractor (None if not found, can be str or list for access_dates)
            context: Full clean text from PDF
            
        Returns:
            Cleaned value, or None if value is None or cannot be cleaned
        """
        # If engine returned None, return None (don't clean)
        if value is None:
            return None
        
        # Special handling for access_dates (list)
        if field_name == "access_dates" and isinstance(value, list):
            # Clean each date in the list
            cleaned_dates = []
            for date_val in value:
                if date_val:
                    cleaned = self._clean_single_value(field_name, date_val, context)
                    if cleaned:
                        cleaned_dates.append(cleaned)
            return cleaned_dates if cleaned_dates else None
        
        # Special handling for weather_measurement_type (list)
        if field_name == "weather_measurement_type" and isinstance(value, list):
            # Clean each measurement type in the list
            cleaned_types = []
            for type_val in value:
                if type_val and isinstance(type_val, str):
                    cleaned = type_val.strip()
                    # Remove bullets, numbering, stray dots
                    cleaned = re.sub(r'^[-•*]\s*', '', cleaned)
                    cleaned = re.sub(r'^\d+[\.\)]\s*', '', cleaned)
                    cleaned = re.sub(r'^\.+\s*', '', cleaned)
                    cleaned = cleaned.strip()
                    if cleaned and not self._is_placeholder(cleaned) and cleaned not in cleaned_types:
                        cleaned_types.append(cleaned)
            return cleaned_types if cleaned_types else None
        
        # Special handling for key_dates (list of dicts) - don't clean, return as-is
        if field_name == "key_dates" and isinstance(value, list):
            # key_dates is a list of dictionaries, don't try to clean it
            return value if value else None
        
        # Special handling for key_persons (list of dicts) - don't clean, return as-is
        if field_name == "key_persons" and isinstance(value, list):
            # key_persons is a list of dictionaries, don't try to clean it
            return value if value else None
        
        # If no AI available, return value as-is
        if not self.azure_client:
            return value
        
        # Clean single value (must be a string)
        if not isinstance(value, str):
            # If value is not a string and not handled above, return as-is
            return value
        
        return self._clean_single_value(field_name, value, context)
    
    def _clean_single_value(self, field_name: str, value: str, context: str) -> Optional[str]:
        """
        Clean a single string value using AI.
        
        Args:
            field_name: Name of field being extracted
            value: Value extracted by phrase extractor (must be a string)
            context: Full clean text from PDF
            
        Returns:
            Cleaned value, or None if cannot be cleaned
        """
        # Safety check: only process strings
        if not isinstance(value, str):
            return value
        
        # If no AI available, return value as-is
        if not self.azure_client:
            return value
        
        # Get field definition
        field_def = self._get_field_definition(field_name)
        description = field_def.get("description", field_name)
        format_desc = field_def.get("format", "value")
        example = field_def.get("example", "")
        
        # Use ±300 chars context around where value might be
        # For simplicity, search for value in context and get surrounding text
        value_pos = context.lower().find(value.lower()) if value else -1
        if value_pos >= 0:
            start_pos = max(0, value_pos - 300)
            end_pos = min(len(context), value_pos + len(value) + 300)
            context_snippet = context[start_pos:end_pos]
        else:
            context_snippet = context[:2000]
        
        prompt = f"""You are cleaning an extracted value from an NEC contract.

Field: {description}
Extracted value: {value}
Expected format: {format_desc}
Example: {example}

Context text:
{context_snippet[:1000]}

CRITICAL RULES:
1. Normalize weeks → "4 weeks" (not "four weeks" or "4 week")
2. Normalize dates → "31 March 2024" (not "March 31, 2024" or "31/03/2024")
3. Remove junk text (keep only the value)
4. Verify the value EXISTS in the context text before accepting
5. If value is redacted (████) → return "specified but redacted"
6. If value cannot be determined → return "not specified"
7. NEVER invent dates, numbers, or values not present in context

Return JSON: {{"value": "...", "is_valid": true/false}}
If is_valid is false, the value should be rejected."""

        try:
            response = self.azure_client.chat.completions.create(
                model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini"),
                messages=[
                    {
                        "role": "system",
                        "content": "You clean extracted values from NEC contracts. Normalize dates, durations, and amounts. Extract ONLY literal values that exist in the provided context. Never invent values. Return JSON with 'value' and 'is_valid' fields."
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
            try:
                parsed = json.loads(result)
                ai_value = parsed.get("value", "").strip()
                is_valid = parsed.get("is_valid", True)
                
                # RULE 1: Do NOT overwrite any extracted date unless:
                # - LLM returns a date
                # - AND it exists in the source snippet
                # - AND the engine-extracted value is empty
                if field_name in ["starting_date", "completion_date", "access_dates"]:
                    # If engine extracted a valid date, don't overwrite it
                    if value and value.strip() and self.verify_value(field_name, value, context_snippet):
                        # Only allow AI to format/normalize, not replace
                        if not self._is_date_format(ai_value):
                            self.log(f"AI tried to replace date with non-date, keeping original: {value}")
                            return value
                        # Check if AI value is just a reformat of the original
                        if not self._is_same_date(value, ai_value):
                            self.log(f"AI tried to replace date with different date, keeping original: {value}")
                            return value
                
                # RULE 2: Never replace dates with numbers, clause IDs, or text
                if field_name in ["starting_date", "completion_date"]:
                    if re.search(r'\d+\.\d+\(', ai_value) or re.search(r'^\d+$', ai_value):
                        self.log(f"AI tried to replace date with number/clause ID, keeping original: {value}")
                        return value
                
                # RULE 3: Never overwrite correct values with ""
                if not ai_value or ai_value.strip() == "":
                    if value and value.strip():
                        self.log(f"AI returned empty, keeping original: {value}")
                        return value
                
                # If AI says invalid, return original value
                if not is_valid:
                    self.log(f"AI marked value as invalid, using original: {value}")
                    return value
                
                # Validate AI value matches context
                if not self._ensure_value_matches_context(ai_value, context_snippet):
                    self.log(f"AI value not in context, using original: {value}")
                    return value
                
                # Check for nonsense
                if self._is_nonsense(ai_value):
                    self.log(f"AI produced nonsense, using original: {value}")
                    return value
                
                # RULE 4: AI may format durations (4 week → 4 weeks)
                if field_name in ["first_programme_submission", "revised_programme_interval", 
                                 "defects_date", "defect_correction_period", "payment_period"]:
                    # Allow normalization of duration format
                    if self._is_duration_format(ai_value) and self._is_duration_format(value):
                        self.log(f"Cleaned {field_name}: {value} → {ai_value}")
                        return ai_value
                    # If AI changed format significantly, keep original
                    if not self._is_duration_format(ai_value):
                        self.log(f"AI changed duration format incorrectly, keeping original: {value}")
                        return value
                
                self.log(f"Cleaned {field_name}: {value} → {ai_value}")
                return ai_value if ai_value else value
                
            except json.JSONDecodeError:
                self.log("Failed to parse AI response, using original value")
                return value
        
        except Exception as e:
            self.log(f"AI correction failed: {e}, using original value")
            return value
    
    def verify_value(self, field_name: str, candidate: str, context: str) -> bool:
        """
        Verify if extracted value is valid.
        
        Rules:
        - Dates must match regex: \b\d{1,2} (January|February|...|December) \d{4}\b
        - Durations must match: \b\d+\s*(week|weeks|day|days|month|months)\b
        - Locations must be alphabetic or proper nouns, not "is", "bankn", or fragments
        - Reject junk values like "is", "TBC", etc.
        
        Args:
            field_name: Name of field being verified
            candidate: Candidate value to verify
            context: Context text where value was found
            
        Returns:
            True if value is valid, False otherwise
        """
        if not candidate or not candidate.strip():
            return False
        
        candidate = candidate.strip()
        
        # Reject common junk values
        junk_values = ["is", "are", "the", "a", "an", "and", "or", "but", "TBC", "tbc", "TBD", "tbd", "to be confirmed"]
        if candidate.lower() in junk_values:
            return False
        
        # Date fields validation
        if field_name in ["starting_date", "completion_date"]:
            # CRITICAL: Reject durations (e.g., "4 weeks") - these are NOT dates
            if re.search(r'\b\d+\s+(week|weeks|day|days|month|months)\b', candidate, re.IGNORECASE):
                return False  # This is a duration, not a date
            # Must match: DD Month YYYY or Month DD YYYY
            date_pattern = r'\b\d{1,2}\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b'
            if re.search(date_pattern, candidate, re.IGNORECASE):
                return True
            # Also check Month DD, YYYY format
            date_pattern2 = r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b'
            if re.search(date_pattern2, candidate, re.IGNORECASE):
                return True
            return False
        
        # Access dates validation (list or string)
        if field_name == "access_dates":
            if isinstance(candidate, list):
                # Validate each date in list
                for date_val in candidate:
                    if not self.verify_value("starting_date", date_val, context):
                        return False
                return True
            else:
                # Validate as single date
                return self.verify_value("starting_date", candidate, context)
        
        # Duration fields validation
        if field_name in ["first_programme_submission", "revised_programme_interval", 
                         "defects_date", "defect_correction_period"]:
            # Must match: \d+\s*(week|weeks|day|days|month|months)
            duration_pattern = r'\b\d+\s+(week|weeks|day|days|month|months)\b'
            if re.search(duration_pattern, candidate, re.IGNORECASE):
                return True
            # Also check "one week", "two weeks", etc.
            if re.search(r'\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+(week|weeks?|day|days?)\b', candidate, re.IGNORECASE):
                return True
            return False
        
        # Payment period validation (reject "Monthly" unless explicitly stated as payment timing)
        if field_name == "payment_period":
            # Reject "Monthly" - this is likely inferred from assessment_interval
            if candidate.strip() == "Monthly":
                return False
            # Must match: \d+\s*(week|weeks|day|days|month|months)
            duration_pattern = r'\b\d+\s+(week|weeks|day|days|month|months)\b'
            if re.search(duration_pattern, candidate, re.IGNORECASE):
                return True
            # Also check "one week", "two weeks", etc.
            if re.search(r'\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+(week|weeks?|day|days?)\b', candidate, re.IGNORECASE):
                return True
            return False
        
        # Assessment interval validation
        if field_name == "assessment_interval":
            # Can be duration or "Monthly", "Weekly", etc.
            if re.search(r'\b(Monthly|Weekly|Daily)\b', candidate, re.IGNORECASE):
                return True
            duration_pattern = r'\b\d+\s+(week|weeks|day|days|month|months)\b'
            if re.search(duration_pattern, candidate, re.IGNORECASE):
                return True
            return False
        
        # Location validation
        if field_name == "weather_location":
            # Must be proper noun (capitalized words), not fragments
            if not re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*$', candidate):
                return False
            # Reject common words
            reject_words = ["the", "and", "or", "for", "with", "from", "Met", "Office", "is", "are", "to", "be", "recorded"]
            if candidate in reject_words:
                return False
            # Must be alphabetic only
            if not re.match(r'^[A-Za-z\s]+$', candidate):
                return False
            return True
        
        # Measurement type validation (must be non-empty list)
        if field_name == "weather_measurement_type":
            # Must be a non-empty list
            if isinstance(candidate, list):
                if not candidate:
                    return False
                # All items must be non-empty strings
                for item in candidate:
                    if not item or not isinstance(item, str) or not item.strip():
                        return False
                    if self._is_placeholder(item):
                        return False
                return True
            # If it's a string, it's invalid (should be a list)
            return False
        
        # Source validation
        if field_name == "weather_historical_source":
            # Must be proper noun or "Met Office"
            if candidate == "Met Office":
                return True
            if re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*$', candidate):
                return True
            return False
        
        # Delay damages validation
        if field_name == "delay_damages":
            if candidate in ["specified but redacted", "not included"]:
                return True
            # Must match currency pattern
            currency_pattern = r'[£$€]?\s*\d[\d,\.]*\s+per\s+(day|week|month)'
            if re.search(currency_pattern, candidate, re.IGNORECASE):
                return True
            return False
        
        # Percentage validation
        if field_name == "retention_percentage":
            percentage_pattern = r'\b\d+(?:\.\d+)?%'
            if re.search(percentage_pattern, candidate):
                return True
            return False
        
        # Default: check if value appears in context
        if candidate.lower() in context.lower():
            return True
        
        return False
    
    def ai_fallback_extract(self, field_name: str, clean_text: str, section_text: str = "") -> Optional[str]:
        """
        FULL semantic extraction ONLY IF engine returned None.
        
        MUST return a literal clean value.
        NEVER return hallucinations.
        
        For Section 3 fields: Use FULL Section 3 block, prefer dates near keywords, never guess.
        
        Args:
            field_name: Name of field to extract
            clean_text: Full clean text from PDF
            section_text: Section text where field should be found (mandatory for Section 3)
            
        Returns:
            Extracted value, or None if not found
        """
        # If no AI available, return None
        if not self.azure_client:
            return None
        
        # For Section 3 fields, ALWAYS use full section_text if provided
        section_3_fields = ["starting_date", "access_dates", "completion_date", 
                           "first_programme_submission", "revised_programme_interval"]
        
        if field_name in section_3_fields:
            # Use FULL Section 3 block (not truncated)
            search_text = section_text if section_text else clean_text
            # For Section 3, use up to 8000 chars to ensure full section
            search_text = search_text[:8000] if len(search_text) > 8000 else search_text
        else:
            # For other sections, use section text if provided
            search_text = section_text if section_text else clean_text
            search_text = search_text[:4000]
        
        # Get field definition
        field_def = self._get_field_definition(field_name)
        description = field_def.get("description", field_name)
        format_desc = field_def.get("format", "value")
        example = field_def.get("example", "")
        
        # Special prompt for Section 3 fields
        if field_name in section_3_fields:
            prompt = f"""Extract the exact value for {description} from this NEC Section 3 (Time) text.

Expected format: {format_desc}
Example: {example}

FULL Section 3 Text:
{search_text}

CRITICAL RULES FOR SECTION 3:
1. Extract ONLY the literal value (date or duration) as written in Section 3
2. Prefer dates/durations that appear NEAR keywords like "starting date", "completion date", "programme", "weeks"
3. Normalize format: dates → "DD Month YYYY", durations → "X weeks"
4. If value is redacted (████) → return "specified but redacted"
5. NEVER return "not specified" if a date/duration exists anywhere in Section 3
6. Search the ENTIRE Section 3 text (including Contract Data rows) before giving up
7. NEVER invent dates, numbers, or values
8. NEVER return full sentences or paragraphs
9. Return ONLY the value itself
10. If you find a date/duration near the relevant keyword, extract it even if the exact phrase is not present
11. Contract Data rows may appear before clause headers - search ALL of Section 3 text

Return JSON: {{"value": "..."}}"""
        elif field_name == "weather_measurement_type":
            # Special prompt for weather_measurement_type (must return list)
            prompt = f"""Extract the weather measurement types from this NEC Section 6 (Compensation Events - Weather) text.

Expected format: {format_desc}
Example: {example}

FULL Section 6 Text:
{search_text}

CRITICAL RULES FOR WEATHER MEASUREMENT TYPE:
1. Find the label "The weather measurements to be recorded"
2. Capture ALL subsequent non-empty lines until "The weather measurements are supplied by" or another section header
3. Return a LIST of measurement strings (e.g., ["cumulative rainfall", "rainfall >5mm days", "min temperature <0C days"])
4. Remove bullets, numbering, stray dots from each item
5. Strip whitespace
6. Ignore placeholders like "insert details"
7. NEVER return empty list [] if bullet items exist in the text
8. NEVER invent measurement types
9. Return a list, never a single string

Return JSON: {{"value": ["measurement1", "measurement2", ...]}}"""
        else:
            prompt = f"""Extract the exact value for {description} from this specific NEC section.

Expected format: {format_desc}
Example: {example}

NEC Section Text:
{search_text}

CRITICAL RULES:
1. Extract ONLY the literal value (date, duration, number, amount, location)
2. Return the EXACT value as written in this section
3. Do NOT use information outside this section
4. Normalize format: dates → "DD Month YYYY", durations → "X weeks", amounts → "£X per week"
5. If value is redacted (████) → return "specified but redacted"
6. If field is not present in this section → return "not specified"
7. NEVER invent dates, numbers, or values
8. NEVER return full sentences or paragraphs
9. Return ONLY the value itself
10. If the value is not present in the section text above, return "not specified"

Return JSON: {{"value": "..."}}"""

        try:
            response = self.azure_client.chat.completions.create(
                model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini"),
                messages=[
                    {
                        "role": "system",
                        "content": "You extract literal values from NEC contracts. Extract ONLY dates, durations, numbers, amounts, or location names that are explicitly stated in the contract. Never invent values. Return JSON with 'value' field."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.0,
                max_tokens=200,
                response_format={"type": "json_object"}
            )
            
            result = response.choices[0].message.content.strip()
            
            # Parse JSON response
            try:
                parsed = json.loads(result)
                ai_value = parsed.get("value", "").strip()
                
                # For Section 3 fields, be more lenient - allow if value components appear
                section_3_fields = ["starting_date", "access_dates", "completion_date", 
                                   "first_programme_submission", "revised_programme_interval"]
                
                if field_name in section_3_fields:
                    # For Section 3, only reject if value is clearly not in section text
                    if ai_value and ai_value.lower() not in [
                        "not specified", "not included", "specified but redacted",
                        "not stated", "n/a", "not applicable"
                    ]:
                        # More lenient check for Section 3 - allow if date components or numbers appear
                        if not self._ensure_value_matches_context(ai_value, search_text):
                            # Check if it's a valid date/duration format even if not verbatim
                            if field_name in ["starting_date", "completion_date"]:
                                # CRITICAL: Reject durations for date fields
                                if re.search(r'\b\d+\s+(week|weeks|day|days|month|months)\b', ai_value, re.IGNORECASE):
                                    self.log(f"AI fallback returned duration for date field {field_name}, rejecting: {ai_value}")
                                    return None
                                if self._is_date_format(ai_value):
                                    self.log(f"AI fallback extracted {field_name} (date format valid): {ai_value}")
                                    return ai_value
                            elif field_name == "access_dates":
                                # For access_dates, check if it's a list or string of dates
                                if isinstance(ai_value, list):
                                    # Filter out durations from list
                                    valid_dates = [d for d in ai_value if isinstance(d, str) and 
                                                  not re.search(r'\b\d+\s+(week|weeks|day|days|month|months)\b', d, re.IGNORECASE) and
                                                  self._is_date_format(d)]
                                    if valid_dates:
                                        self.log(f"AI fallback extracted {field_name} (date list valid): {valid_dates}")
                                        return valid_dates
                                elif isinstance(ai_value, str) and self._is_date_format(ai_value):
                                    self.log(f"AI fallback extracted {field_name} (date format valid): {ai_value}")
                                    return [ai_value]
                            elif field_name in ["first_programme_submission", "revised_programme_interval"]:
                                if self._is_duration_format(ai_value):
                                    self.log(f"AI fallback extracted {field_name} (duration format valid): {ai_value}")
                                    return ai_value
                            self.log(f"AI fallback value not in section text, rejecting: {ai_value}")
                            return None
                else:
                    # For other sections, strict check
                    if ai_value and ai_value.lower() not in [
                        "not specified", "not included", "specified but redacted",
                        "not stated", "n/a", "not applicable"
                    ]:
                        if not self._ensure_value_matches_context(ai_value, search_text):
                            self.log(f"AI fallback value not in section text, rejecting: {ai_value}")
                            return None
                
                # Check for nonsense
                if ai_value and self._is_nonsense(ai_value):
                    self.log(f"AI fallback produced nonsense, rejecting: {ai_value}")
                    return None
                
                # For Section 3, never return "not specified" unless truly missing
                if field_name in section_3_fields:
                    if ai_value and ai_value.lower() == "not specified":
                        # Try one more time with a more aggressive search
                        self.log(f"AI returned 'not specified' for {field_name}, but continuing search...")
                        # Don't return None yet - let the value pass through if it's a valid format
                        if not self._is_date_format(ai_value) and not self._is_duration_format(ai_value):
                            return None
                    
                    # CRITICAL: Final validation - reject durations for date fields
                    if field_name in ["starting_date", "completion_date"]:
                        if isinstance(ai_value, str) and re.search(r'\b\d+\s+(week|weeks|day|days|month|months)\b', ai_value, re.IGNORECASE):
                            self.log(f"AI fallback final check: rejecting duration for date field {field_name}: {ai_value}")
                            return None
                
                # Special handling for weather_measurement_type (must return list)
                if field_name == "weather_measurement_type":
                    # Parse AI response - could be JSON array or comma-separated string
                    if isinstance(ai_value, str):
                        # Try to parse as JSON array
                        try:
                            parsed = json.loads(ai_value)
                            if isinstance(parsed, list):
                                ai_value = parsed
                        except:
                            # Not JSON, try comma-separated
                            if ',' in ai_value:
                                ai_value = [item.strip() for item in ai_value.split(',') if item.strip()]
                            else:
                                ai_value = [ai_value.strip()] if ai_value.strip() else []
                    
                    # Ensure it's a list
                    if not isinstance(ai_value, list):
                        ai_value = [ai_value] if ai_value else []
                    
                    # Filter out placeholders and empty values
                    cleaned_list = []
                    for item in ai_value:
                        if item and isinstance(item, str):
                            cleaned = item.strip()
                            if cleaned and not self._is_placeholder(cleaned):
                                cleaned_list.append(cleaned)
                    
                    if cleaned_list:
                        self.log(f"AI fallback extracted {field_name}: {cleaned_list}")
                        return cleaned_list
                    else:
                        self.log(f"AI fallback for {field_name} produced empty list")
                        return None
                
                self.log(f"AI fallback extracted {field_name}: {ai_value}")
                return ai_value if ai_value else None
                
            except json.JSONDecodeError:
                self.log("Failed to parse AI fallback response")
                return None
        
        except Exception as e:
            self.log(f"AI fallback extraction failed: {e}")
            return None
    
    def _get_field_definition(self, field_name: str) -> Dict[str, str]:
        """Get field definition for AI prompts."""
        field_definitions = {
            "starting_date": {
                "description": "starting date",
                "format": "DD Month YYYY or DD/MM/YYYY",
                "example": "20 March 2023"
            },
            "access_dates": {
                "description": "access date(s)",
                "format": "DD Month YYYY (array if multiple)",
                "example": "20 March 2023"
            },
            "completion_date": {
                "description": "completion date",
                "format": "DD Month YYYY",
                "example": "31 March 2024"
            },
            "first_programme_submission": {
                "description": "first programme submission interval",
                "format": "X weeks or X days",
                "example": "4 weeks"
            },
            "revised_programme_interval": {
                "description": "revised programme interval",
                "format": "X weeks or X days",
                "example": "4 weeks"
            },
            "delay_damages": {
                "description": "delay damages amount",
                "format": "£X per week/day or 'specified but redacted' or 'not included'",
                "example": "£250,000 per week"
            },
            "delay_damages_amount": {
                "description": "delay damages amount (extracted separately)",
                "format": "£X per week/day",
                "example": "£250,000 per week"
            },
            "defects_date": {
                "description": "defects date",
                "format": "X weeks after Completion",
                "example": "52 weeks"
            },
            "defect_correction_period": {
                "description": "defect correction period",
                "format": "X weeks or X days",
                "example": "2 weeks"
            },
            "assessment_interval": {
                "description": "assessment interval",
                "format": "X weeks, X days, or 'Monthly'",
                "example": "Monthly"
            },
            "payment_period": {
                "description": "payment period",
                "format": "X weeks, X days, or 'one week'",
                "example": "one week"
            },
            "retention_percentage": {
                "description": "retention percentage",
                "format": "X%",
                "example": "3%"
            },
            "weather_location": {
                "description": "weather recording location",
                "format": "Location name (proper place name)",
                "example": "Ilkley"
            },
            "weather_measurement_type": {
                "description": "weather measurement types (list)",
                "format": "List of measurement types (e.g., ['cumulative rainfall', 'rainfall >5mm days', 'min temperature <0C days'])",
                "example": "['cumulative rainfall', 'rainfall >5mm days']"
            },
            "weather_historical_source": {
                "description": "weather historical source",
                "format": "Source name",
                "example": "Met Office"
            },
        }
        
        return field_definitions.get(field_name, {
            "description": field_name,
            "format": "value",
            "example": ""
        })
    
    def _ensure_value_matches_context(self, candidate_value: str, context_text: str) -> bool:
        """
        Ensure AI-produced value is present in context text.
        
        Args:
            candidate_value: Value produced by AI
            context_text: Original context text
            
        Returns:
            True if value (or its components) appear in context, False otherwise
        """
        if not candidate_value or candidate_value.lower() in [
            "not specified", "not included", "specified but redacted", 
            "not stated", "n/a", "not applicable"
        ]:
            return True
        
        # For dates, check if date components appear
        date_match = re.search(r'(\d{1,2}\s+\w+\s+\d{4}|\d{1,2}/\d{1,2}/\d{4}|\d{4})', candidate_value, re.IGNORECASE)
        if date_match:
            date_components = re.findall(r'\d+', date_match.group(1))
            for component in date_components:
                if component in context_text:
                    return True
        
        # For numbers/amounts, check if number appears
        number_match = re.search(r'(\d[\d,\.]*)', candidate_value)
        if number_match:
            number_str = number_match.group(1).replace(',', '').replace('.', '')
            if number_str in context_text.replace(',', '').replace('.', ''):
                return True
        
        # For durations, check if number + unit appear
        duration_match = re.search(r'(\d+)\s*(week|day|month)', candidate_value, re.IGNORECASE)
        if duration_match:
            number = duration_match.group(1)
            unit = duration_match.group(2)
            if number in context_text and unit.lower() in context_text.lower():
                return True
        
        # For percentages, check if number + % appear
        percentage_match = re.search(r'(\d+)%', candidate_value)
        if percentage_match:
            number = percentage_match.group(1)
            if number in context_text and '%' in context_text:
                return True
        
        # For currency, check if amount appears
        currency_match = re.search(r'[£$€]?\s*(\d[\d,\.]*)', candidate_value)
        if currency_match:
            amount = currency_match.group(1).replace(',', '').replace('.', '')
            if amount in context_text.replace(',', '').replace('.', ''):
                return True
        
        # For location names, check if name appears
        if re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*$', candidate_value):
            if candidate_value.lower() in context_text.lower():
                return True
        
        # If value appears verbatim in context, allow it
        if candidate_value.lower() in context_text.lower():
            return True
        
        # If value is short and contains key components, allow it
        if len(candidate_value) < 50:
            words = candidate_value.split()
            significant_words = [w for w in words if len(w) > 2 and w.lower() not in ["the", "and", "or", "for", "with", "from"]]
            if significant_words:
                for word in significant_words:
                    if word.lower() in context_text.lower():
                        return True
        
        return False
    
    def _is_date_format(self, value: str) -> bool:
        """Check if value is a date format."""
        if not value:
            return False
        date_pattern = r'\b\d{1,2}\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b'
        if re.search(date_pattern, value, re.IGNORECASE):
            return True
        date_pattern2 = r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b'
        if re.search(date_pattern2, value, re.IGNORECASE):
            return True
        return False
    
    def _is_same_date(self, date1: str, date2: str) -> bool:
        """Check if two date strings represent the same date."""
        # Extract date components
        def extract_date_components(date_str):
            match = re.search(r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})', date_str, re.IGNORECASE)
            if match:
                return (int(match.group(1)), match.group(2).lower(), int(match.group(3)))
            return None
        
        comp1 = extract_date_components(date1)
        comp2 = extract_date_components(date2)
        
        if comp1 and comp2:
            return comp1 == comp2
        
        # If can't parse, check if strings are similar
        return date1.lower().strip() == date2.lower().strip()
    
    def _is_duration_format(self, value: str) -> bool:
        """Check if value is a duration format."""
        if not value:
            return False
        duration_pattern = r'\b\d+\s+(week|weeks|day|days|month|months)\b'
        if re.search(duration_pattern, value, re.IGNORECASE):
            return True
        if re.search(r'\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+(week|weeks?|day|days?)\b', value, re.IGNORECASE):
            return True
        return False
    
    def _is_nonsense(self, value: str) -> bool:
        """Check if value appears to be nonsense."""
        if not value:
            return False
        
        # Common nonsense patterns
        nonsense_patterns = [
            r'^yap',
            r'^the\s+starting\s+date\s+is',
            r'^the\s+completion\s+date',
            r'^is$',
            r'^for\s+the\s+whole',
            r'^the\s+contractor',
            r'^the\s+employer',
        ]
        
        if any(re.search(p, value, re.IGNORECASE) for p in nonsense_patterns):
            return True
        
        # Check if value is too generic
        meaningless = ["is", "are", "the", "a", "an", "and", "or", "but"]
        if value.lower().strip() in meaningless:
            return True
        
        return False
    
    def _is_placeholder(self, value: str) -> bool:
        """Check if value is a placeholder (TBC, insert date, none set, etc.)."""
        if not value:
            return True
        
        value_lower = value.strip().lower()
        placeholders = [
            "tbc", "tbd", "to be confirmed", "to be determined",
            "insert date", "insert details", "none set", "not set",
            "blank", "empty", "n/a", "na", "-", "...", "xxx"
        ]
        
        return value_lower in placeholders
