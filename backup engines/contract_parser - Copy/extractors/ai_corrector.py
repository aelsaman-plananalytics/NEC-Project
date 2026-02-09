"""
AI Validation & Correction Layer for NEC4 Contract Extraction

Layer 2: Uses AI to clean extracted values and ensure they match context.
"""

import re
import os
from typing import Dict, Any, Optional

# LLM support
try:
    from openai import AzureOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    AzureOpenAI = None


class AICorrector:
    """
    AI Verifier and Corrector layer.
    
    Two-step process:
    1. AI Verifier: Checks if engine value appears verbatim in contract text
    2. AI Corrector: Extracts better value from line if engine found wrong part
    
    NEVER fabricates values - only validates or corrects what exists in contract.
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
    
    def verify_value(self, candidate_value: str, contract_text: str) -> str:
        """
        RULE 3 — AI VERIFIER:
        Check if candidate value appears verbatim in contract text.
        
        Prompt: "Does VALUE `{value}` appear **verbatim** in the following CONTRACT TEXT? 
        If yes, return SAME VALUE. If no, return 'INVALID'."
        
        Args:
            candidate_value: Value extracted by phrase extractor
            contract_text: Original contract text line where value was found
            
        Returns:
            Same value if it appears verbatim, or 'INVALID' if not found
        """
        if not self.azure_client or not candidate_value:
            # If no AI, check manually if value exists in text
            if candidate_value and self._value_exists_in_text(candidate_value, contract_text):
                return candidate_value
            return "INVALID"
        
        prompt = f"""Does VALUE `{candidate_value}` appear **verbatim** in the following CONTRACT TEXT?

CONTRACT TEXT:
{contract_text[:1000]}

CRITICAL RULES:
1. Check if the value appears word-for-word (or with minor formatting differences like spaces/punctuation) in the contract text
2. If YES → return the SAME VALUE exactly as it appears
3. If NO → return 'INVALID'
4. NEVER invent or modify values
5. ONLY return values that actually exist in the contract text

Return JSON: {{"value": "..." or "INVALID", "valid": true/false}}"""

        try:
            response = self.azure_client.chat.completions.create(
                model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini"),
                messages=[
                    {
                        "role": "system",
                        "content": "You verify if a value appears verbatim in contract text. If yes, return SAME VALUE. If no, return 'INVALID'. Return JSON with 'value' and 'valid' fields."
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
                ai_value = parsed.get("value", "")
                is_valid = parsed.get("valid", False)
                
                # If AI returned INVALID or valid=false, return INVALID
                if ai_value == "INVALID" or not is_valid or not ai_value:
                    self.log(f"AI verifier: value NOT found in contract text: {candidate_value}")
                    return "INVALID"
                
                # Double-check: ensure AI value exists in contract text
                if not self._value_exists_in_text(ai_value, contract_text):
                    self.log(f"AI verifier: value not found in contract text, rejecting: {ai_value}")
                    return "INVALID"
                
                self.log(f"AI verifier: value confirmed in contract text: {ai_value}")
                return ai_value
                
            except json.JSONDecodeError:
                self.log("Failed to parse AI verifier response, checking manually")
                # Fallback: check manually
                if self._value_exists_in_text(candidate_value, contract_text):
                    return candidate_value
                return "INVALID"
        
        except Exception as e:
            self.log(f"AI verifier failed: {e}, checking manually")
            # Fallback: check manually
            if self._value_exists_in_text(candidate_value, contract_text):
                return candidate_value
            return "INVALID"
    
    def correct_value(self, field_name: str, original_line: str) -> str:
        """
        RULE 4 — AI CORRECTOR:
        Extract better value from line if engine found wrong part.
        
        Prompt: "Extract ONLY the numeric/date/duration/location value that completes 
        the meaning of this line. Do NOT invent anything. Only return exact text that appears in the line."
        
        Args:
            field_name: Name of field being extracted
            original_line: Full line from contract where phrase was found
            
        Returns:
            Corrected value if found in line, or empty string if not found
        """
        if not self.azure_client:
            return ""
        
        # Field-specific extraction guidance
        field_guidance = {
            "starting_date": "Extract the date (DD Month YYYY or DD/MM/YYYY format)",
            "access_dates": "Extract all dates (comma-separated if multiple)",
            "completion_date": "Extract the date (DD Month YYYY format)",
            "first_programme_submission": "Extract duration (e.g., '4 weeks')",
            "revised_programme_interval": "Extract duration (e.g., '4 weeks')",
            "delay_damages": "Extract currency amount (e.g., '£250,000 per week')",
            "defects_date": "Extract duration (e.g., '52 weeks after Completion')",
            "defect_correction_period": "Extract duration (e.g., '2 weeks')",
            "assessment_interval": "Extract duration or word (e.g., '4 weeks' or 'monthly')",
            "payment_period": "Extract duration (e.g., '21 days')",
            "retention_percentage": "Extract percentage (e.g., '3%') or text value",
            "weather_location": "Extract location name",
            "weather_measurement_type": "Extract measurement types (comma-separated)",
            "weather_historical_source": "Extract source name (usually 'Met Office')",
        }
        
        guidance = field_guidance.get(field_name, "Extract the value")
        
        prompt = f"""Extract ONLY the numeric/date/duration/location value that completes the meaning of this line.

Field: {field_name}
{guidance}

CONTRACT LINE:
{original_line}

CRITICAL RULES:
1. Extract ONLY the exact value (date, duration, amount, location, etc.)
2. Do NOT invent anything
3. Only return exact text that appears in the line
4. If no valid value found → return NULL
5. NEVER return sentences or paragraphs
6. NEVER return partial words or incomplete values

Return JSON: {{"value": "..." or null}}"""

        try:
            response = self.azure_client.chat.completions.create(
                model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini"),
                messages=[
                    {
                        "role": "system",
                        "content": "Extract ONLY the numeric/date/duration/location value from the contract line. Do NOT invent anything. Only return exact text that appears in the line. Return JSON with 'value' field."
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
                ai_value = parsed.get("value", "")
                
                # If AI returned NULL, return empty string
                if ai_value is None or ai_value == "null" or ai_value == "":
                    self.log(f"AI corrector: no value found in line for {field_name}")
                    return ""
                
                ai_value = str(ai_value).strip()
                
                # RULE 5 — NO HALLUCINATION GUARANTEE: Validate that value exists in original line
                if not self._value_exists_in_text(ai_value, original_line):
                    self.log(f"AI corrector: value not found in original line, rejecting: {ai_value}")
                    return ""
                
                self.log(f"AI corrector: extracted value for {field_name}: {ai_value}")
                return ai_value
                
            except json.JSONDecodeError:
                self.log("Failed to parse AI corrector response")
                return ""
        
        except Exception as e:
            self.log(f"AI corrector failed: {e}")
            return ""
    
    def clean_value(self, field_name: str, candidate_value: str, context_text: str) -> str:
        """
        AI Validation (Step 2): Validate that candidate value exists in original text.
        
        System prompt: "You are validating NEC4 contract extraction.  
        Return ONLY the correct value if it appears inside the original text.  
        If the value is not present word-for-word in original text, return NULL."
        
        Args:
            field_name: Name of field being extracted
            candidate_value: Value extracted by phrase extractor
            context_text: Original line/substring where value was found
            
        Returns:
            Validated value if it exists in original text, or empty string if NULL
        """
        if not self.azure_client or not candidate_value:
            return candidate_value if candidate_value else ""
        
        # Find the original line where candidate_value was found
        original_line = self._find_original_line(candidate_value, context_text)
        if not original_line:
            original_line = context_text[:500]  # Fallback to first 500 chars
        
        prompt = f"""You are validating NEC4 contract extraction.

Field: {field_name}
Candidate value extracted: {candidate_value}
Original text line: {original_line}

CRITICAL RULES:
1. Check if the candidate value appears word-for-word (or with minor formatting differences) in the original text line
2. If the value IS present in the original text → return it exactly as found
3. If the value is NOT present word-for-word in original text → return NULL
4. NEVER invent or modify values
5. ONLY return values that actually exist in the original text

Return JSON: {{"value": "..." or null, "valid": true/false}}
If value is not in original text, set value to null and valid to false."""

        try:
            response = self.azure_client.chat.completions.create(
                model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini"),
                messages=[
                    {
                        "role": "system",
                        "content": "You are validating NEC4 contract extraction. Return ONLY the correct value if it appears inside the original text. If the value is not present word-for-word in original text, return NULL. Return JSON with 'value' and 'valid' fields."
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
                ai_value = parsed.get("value", "")
                is_valid = parsed.get("valid", False)
                
                # If AI returned NULL or valid=false, discard engine value
                if ai_value is None or ai_value == "null" or ai_value == "" or not is_valid:
                    self.log(f"AI validation failed: value not in original text, discarding: {candidate_value}")
                    return ""  # Return empty to trigger fallback
                
                ai_value = str(ai_value).strip()
                
                # Double-check: ensure AI value exists in original line
                if not self._value_exists_in_text(ai_value, original_line):
                    self.log(f"AI value not found in original line, discarding: {ai_value}")
                    return ""  # Return empty to trigger fallback
                
                self.log(f"Validated {field_name}: {candidate_value} → {ai_value}")
                return ai_value
                
            except json.JSONDecodeError:
                self.log("Failed to parse AI response, checking if candidate exists in original text")
                # Fallback: check if candidate exists in original line
                if self._value_exists_in_text(candidate_value, original_line):
                    return candidate_value
                return ""
        
        except Exception as e:
            self.log(f"AI validation failed: {e}, checking if candidate exists in original text")
            # Fallback: check if candidate exists in original line
            if self._value_exists_in_text(candidate_value, original_line):
                return candidate_value
            return ""
    
    def fallback_extract(self, field_name: str, full_text: str) -> str:
        """
        Fallback AI Extraction (Step 3): Extract value if engine failed.
        
        Prompt: "Extract ONLY the NEC contract value for FIELD_NAME from the text.  
        Return exactly the value, no explanation. If not present, return NULL."
        
        Args:
            field_name: Name of field being extracted
            full_text: Full contract text (or large context window)
            
        Returns:
            Extracted value, or empty string if NULL
        """
        if not self.azure_client:
            return ""
        
        # Field-specific extraction guidance
        field_guidance = {
            "starting_date": "Extract the starting date (DD Month YYYY format)",
            "access_dates": "Extract all access dates (comma-separated if multiple)",
            "completion_date": "Extract the completion date (DD Month YYYY format)",
            "first_programme_submission": "Extract duration (e.g., '4 weeks')",
            "revised_programme_interval": "Extract duration (e.g., '4 weeks')",
            "delay_damages": "Extract currency amount (e.g., '£250,000 per week') or 'Not specified (redacted)'",
            "defects_date": "Extract duration (e.g., '52 weeks after Completion')",
            "defect_correction_period": "Extract duration (e.g., '2 weeks')",
            "assessment_interval": "Extract duration or word (e.g., '4 weeks' or 'monthly')",
            "payment_period": "Extract duration (e.g., '21 days')",
            "retention_percentage": "Extract percentage (e.g., '3%') or text value",
            "weather_location": "Extract location name",
            "weather_measurement_type": "Extract measurement types (comma-separated)",
            "weather_historical_source": "Extract source name (usually 'Met Office')",
        }
        
        guidance = field_guidance.get(field_name, "Extract the value")
        
        prompt = f"""Extract ONLY the NEC contract value for {field_name} from the text.

{guidance}

CRITICAL RULES:
1. Extract ONLY the exact value (date, duration, amount, location, etc.)
2. Return exactly the value, no explanation
3. If not present, return NULL
4. NEVER invent values
5. NEVER return sentences or paragraphs

Contract text:
{full_text[:3000]}

Return JSON: {{"value": "..." or null}}"""

        try:
            response = self.azure_client.chat.completions.create(
                model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini"),
                messages=[
                    {
                        "role": "system",
                        "content": "Extract ONLY the NEC contract value. Return exactly the value, no explanation. If not present, return NULL. Return JSON with 'value' field."
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
                ai_value = parsed.get("value", "")
                
                # If AI returned NULL, return empty string
                if ai_value is None or ai_value == "null" or ai_value == "":
                    self.log(f"Fallback AI extraction returned NULL for {field_name}")
                    return ""
                
                ai_value = str(ai_value).strip()
                
                # Validate that value exists in full_text
                if not self._value_exists_in_text(ai_value, full_text):
                    self.log(f"Fallback AI value not found in text, rejecting: {ai_value}")
                    return ""
                
                self.log(f"Fallback extracted {field_name}: {ai_value}")
                return ai_value
                
            except json.JSONDecodeError:
                self.log("Failed to parse fallback AI response")
                return ""
        
        except Exception as e:
            self.log(f"Fallback AI extraction failed: {e}")
            return ""
    
    def _find_original_line(self, value: str, context_text: str) -> str:
        """Find the original line where value was extracted from."""
        if not value:
            return context_text[:500]
        
        # Split context into lines
        lines = context_text.split('\n')
        
        # Find line containing the value (or parts of it)
        value_parts = value.split()
        for line in lines:
            # Check if line contains any significant part of the value
            if len(value_parts) > 0:
                # Check if first word of value appears in line
                if value_parts[0].lower() in line.lower():
                    return line
        
        # Fallback: return first 500 chars
        return context_text[:500]
    
    def _value_exists_in_text(self, value: str, text: str) -> bool:
        """
        Check if value exists in text (word-for-word or with minor formatting differences).
        
        More permissive than exact match - allows for:
        - Whitespace differences
        - Case differences
        - Minor punctuation differences
        """
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
    
    def ensure_value_matches_context(self, candidate_value: str, context_text: str) -> bool:
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
        
        # If value is short and contains key components, allow it
        if len(candidate_value) < 50:
            # Check if any significant words appear in context
            words = candidate_value.split()
            significant_words = [w for w in words if len(w) > 2 and w.lower() not in ["the", "and", "or", "for", "with", "from"]]
            if significant_words:
                for word in significant_words:
                    if word.lower() in context_text.lower():
                        return True
        
        # If value appears verbatim in context, allow it
        if candidate_value.lower() in context_text.lower():
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
