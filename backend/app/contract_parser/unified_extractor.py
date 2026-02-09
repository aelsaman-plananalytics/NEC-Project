"""
Unified Contract Data Extraction Pipeline (Section-Based Method).

Orchestrates section-based extraction with AI validation:
1. Detect NEC sections (3, 4, 5, 6, X7)
2. PhraseExtractor - extract from assigned sections only
3. AICorrector - AI validation using section text
4. AI fallback - only if engine fails, using section text
"""

import re
from typing import Dict, List, Any, Optional, Union
from app.contract_parser.extractors.phrase_extractor import PhraseExtractor
from app.contract_parser.extractors.ai_corrector import AICorrector
from app.contract_parser.utils import detect_nec_sections


class UnifiedExtractor:
    """
    Unified extractor using strict section-based extraction with AI validation.
    
    Rules:
    - Detect NEC sections first
    - Extract each field ONLY from its assigned section
    - AI validation uses section text, not full text
    - Never extract from wrong sections
    """
    
    def __init__(self, debug: bool = False, enable_ai: bool = True):
        """
        Initialize unified extractor.
        
        Args:
            debug: Enable debug logging
            enable_ai: Enable AI correction and fallback
        """
        self.debug = debug
        self.enable_ai = enable_ai
        self.phrase_extractor = PhraseExtractor(debug=debug)
        self.ai_corrector = AICorrector(debug=debug, enable_ai=enable_ai)
        self.sections = {}
    
    def log(self, msg: str):
        """Log debug message."""
        # Always print DEBUG messages, even if debug=False
        if "DEBUG" in msg or self.debug:
            print(f"[UnifiedExtractor] {msg}")
    
    def extract(self, clean_text: str) -> Dict[str, Any]:
        """
        Extract all NEC contract data using section-based method with AI validation.
        
        Args:
            clean_text: Clean text extracted from PDF
            
        Returns:
            Dictionary with extracted fields:
            {
                "starting_date": ...,
                "access_dates": [...],
                "completion_date": ...,
                "first_programme_submission": ...,
                "revised_programme_interval": ...,
                "defects_date": ...,
                "defect_correction_period": ...,
                "delay_damages": ...,
                "delay_damages_amount": ...,
                "assessment_interval": ...,
                "payment_period": ...,
                "retention_percentage": ...,
                "weather_location": ...,
                "weather_measurement_type": ...,
                "weather_historical_source": ...
            }
        """
        self.log("Starting unified extraction pipeline (section-based method)")
        
        # STEP 1: Detect NEC sections
        self.log("Step 1: Detecting NEC sections...")
        self.sections = detect_nec_sections(clean_text)
        
        section_counts = {k: len(v) for k, v in self.sections.items()}
        self.log(f"Section detection: {section_counts}")
        
        # STEP 1.5: Scan for Contract Data rows and inject into sections
        self.log("Step 1.5: Scanning for Contract Data rows and injecting into sections...")
        injected_blocks = self._inject_contract_data_rows(clean_text)
        
        # STEP 2: Extract from assigned sections only (now with injected Contract Data)
        self.log("Step 2: Extracting from assigned sections...")
        results_engine = {}
        
        # PART 2: Section 3 (Time) - Build effective section text with injected Contract Data
        injected_section_3 = injected_blocks.get("3", "")
        original_section_3 = self.sections.get("3", "")
        effective_section_3 = (injected_section_3 + "\n\n" + original_section_3) if injected_section_3 else original_section_3
        
        if effective_section_3:
            # Extract from effective Section 3 (includes injected Contract Data rows)
            self.log(f"DEBUG: Extracting from effective_section_3 (length: {len(effective_section_3)} chars)")
            self.log(f"DEBUG: effective_section_3 preview (first 500 chars): {effective_section_3[:500]}")
            
            results_engine["starting_date"] = self.phrase_extractor.extract_starting_date(effective_section_3)
            self.log(f"DEBUG: extract_starting_date returned: {results_engine['starting_date']} (type: {type(results_engine['starting_date'])})")
            
            # If not found in section, try full text as fallback
            if not results_engine["starting_date"]:
                self.log(f"DEBUG: starting_date not found in section, trying full text...")
                results_engine["starting_date"] = self.phrase_extractor.extract_starting_date(clean_text)
                self.log(f"DEBUG: extract_starting_date (full text) returned: {results_engine['starting_date']}")
            
            # Extract completion_date first (needed to exclude from access_dates)
            results_engine["completion_date"] = self.phrase_extractor.extract_completion_date(effective_section_3)
            
            # Extract access_dates, passing starting_date and completion_date to exclude them
            results_engine["access_dates"] = self.phrase_extractor.extract_access_dates(
                effective_section_3, 
                starting_date=results_engine.get("starting_date"),
                completion_date=results_engine.get("completion_date")
            )
            self.log(f"DEBUG: extract_access_dates returned: {results_engine['access_dates']} (type: {type(results_engine['access_dates'])})")
            
            # If not found in section, try full text as fallback
            if not results_engine["access_dates"]:
                self.log(f"DEBUG: access_dates not found in section, trying full text...")
                results_engine["access_dates"] = self.phrase_extractor.extract_access_dates(
                    clean_text, 
                    starting_date=results_engine.get("starting_date"),
                    completion_date=results_engine.get("completion_date")
                )
                self.log(f"DEBUG: extract_access_dates (full text) returned: {results_engine['access_dates']}")
            
            # CRITICAL: Filter out starting_date and completion_date from access_dates if they appear
            # But only if access_dates has OTHER dates - don't empty it completely
            if results_engine.get("access_dates") and isinstance(results_engine["access_dates"], list):
                starting_date = results_engine.get("starting_date")
                completion_date = results_engine.get("completion_date")
                dates_to_exclude = []
                if starting_date:
                    dates_to_exclude.append(starting_date)
                if completion_date:
                    dates_to_exclude.append(completion_date)
                
                if dates_to_exclude:
                    # Normalize dates for comparison
                    dates_to_exclude_normalized = [re.sub(r'\s+', ' ', d.strip().lower()) if d else "" for d in dates_to_exclude]
                    other_dates = []
                    for d in results_engine["access_dates"]:
                        d_normalized = re.sub(r'\s+', ' ', d.strip().lower()) if d else ""
                        if d_normalized not in dates_to_exclude_normalized:
                            other_dates.append(d)
                    
                    if other_dates:
                        # We have other dates, so filter out excluded dates
                        results_engine["access_dates"] = other_dates
                        self.log(f"DEBUG: Filtered out {dates_to_exclude} from access_dates, kept {len(other_dates)} other dates")
                    else:
                        # All dates are excluded - this shouldn't happen, but log a warning
                        self.log(f"DEBUG: All access_dates are in excluded list {dates_to_exclude}, setting to empty")
                        results_engine["access_dates"] = []
            results_engine["first_programme_submission"] = self.phrase_extractor.extract_first_programme_submission(effective_section_3)
            results_engine["revised_programme_interval"] = self.phrase_extractor.extract_revised_programme_interval(effective_section_3)
            # If not found in section, try full text (may be in Contract Data before section)
            if not results_engine["revised_programme_interval"]:
                results_engine["revised_programme_interval"] = self.phrase_extractor.extract_revised_programme_interval(clean_text)
            
            # Extract period for reply (separate from revised programme interval)
            results_engine["period_for_reply"] = self.phrase_extractor.extract_period_for_reply(effective_section_3)
            # If not found in section, try full text (may be in Contract Data before section)
            if not results_engine["period_for_reply"]:
                results_engine["period_for_reply"] = self.phrase_extractor.extract_period_for_reply(clean_text)
            # Extract key dates (can be anywhere in contract)
            results_engine["key_dates"] = self.phrase_extractor.extract_key_dates(clean_text)
            
            # RULE 4: Section 3 hard requirements
            # If PhraseExtractor returns None or placeholder, try AI fallback
            # But only if no value exists yet (write-once guarantee)
            section_3_fields = ["starting_date", "access_dates", "completion_date", 
                              "first_programme_submission", "revised_programme_interval"]
            for field in section_3_fields:
                value = results_engine.get(field)
                if value is None or self._is_placeholder_value(value):
                    # Try AI fallback only if engine found nothing
                    ai_fallback = self.ai_corrector.ai_fallback_extract(field, clean_text, effective_section_3)
                    if ai_fallback and not self._is_placeholder_value(ai_fallback):
                        # CRITICAL: For date fields, reject durations from AI fallback
                        if field in ["starting_date", "completion_date"]:
                            if isinstance(ai_fallback, str) and re.search(r'\b\d+\s+(week|weeks|day|days|month|months)\b', ai_fallback, re.IGNORECASE):
                                self.log(f"AI fallback returned duration for date field {field}, rejecting: {ai_fallback}")
                                continue  # Skip this field, don't set it
                        results_engine[field] = ai_fallback
        else:
            results_engine["starting_date"] = None
            results_engine["access_dates"] = None
            results_engine["completion_date"] = None
            results_engine["first_programme_submission"] = None
            results_engine["revised_programme_interval"] = None
        
        # Section 4 (Quality Management)
        section_4 = self.sections.get("4", "")
        if section_4:
            results_engine["defects_date"] = self.phrase_extractor.extract_defects_date(section_4)
            # CRITICAL: defect_correction_period is different from defects_date
            # Only extract if explicitly mentioned, don't confuse with defects_date
            results_engine["defect_correction_period"] = self.phrase_extractor.extract_defect_correction_period(section_4)
        else:
            results_engine["defects_date"] = None
            results_engine["defect_correction_period"] = None
        
        # Section 5 (Payment) - Build effective section text with injected Contract Data
        injected_section_5 = injected_blocks.get("5", "")
        original_section_5 = self.sections.get("5", "")
        effective_section_5 = (injected_section_5 + "\n\n" + original_section_5) if injected_section_5 else original_section_5
        
        if effective_section_5:
            results_engine["assessment_interval"] = self.phrase_extractor.extract_assessment_interval(effective_section_5)
            # payment_period: Check full text (Y(UK)2 can be anywhere, overrides Section 5)
            results_engine["payment_period"] = self.phrase_extractor.extract_payment_period(clean_text)
            results_engine["retention_percentage"] = self.phrase_extractor.extract_retention_percentage(effective_section_5)
        else:
            results_engine["assessment_interval"] = None
            # payment_period: Check full text even if Section 5 not found (Y(UK)2 might exist)
            results_engine["payment_period"] = self.phrase_extractor.extract_payment_period(clean_text)
            results_engine["retention_percentage"] = None
        
        # Section X7 (Delay Damages)
        section_x7 = self.sections.get("X7", "")
        if section_x7:
            results_engine["delay_damages"] = self.phrase_extractor.extract_delay_damages(section_x7)
            results_engine["delay_damages_amount"] = self.phrase_extractor.extract_delay_damages_amount(section_x7)
        else:
            results_engine["delay_damages"] = None
            results_engine["delay_damages_amount"] = None
        
        # PART 3: Section 6 (Compensation Events - Weather) - Build effective section text with injected Contract Data
        injected_section_6 = injected_blocks.get("6", "")
        original_section_6 = self.sections.get("6", "")
        effective_section_6 = (injected_section_6 + "\n\n" + original_section_6) if injected_section_6 else original_section_6
        
        if effective_section_6:
            results_engine["weather_location"] = self.phrase_extractor.extract_weather_location(effective_section_6)
            # PART 3: extract_weather_measurement_type returns a list
            results_engine["weather_measurement_type"] = self.phrase_extractor.extract_weather_measurement_type(effective_section_6)
            results_engine["weather_historical_source"] = self.phrase_extractor.extract_weather_historical_source(effective_section_6)
            
            # RULE 5: Section 6 hard requirements
            # weather_measurement_type must be a list
            # If PhraseExtractor didn't return a valid list, try AI fallback
            weather_measurements = results_engine.get("weather_measurement_type")
            if not isinstance(weather_measurements, list) or not weather_measurements or self._is_placeholder_value(weather_measurements):
                ai_fallback = self.ai_corrector.ai_fallback_extract("weather_measurement_type", clean_text, effective_section_6)
                if ai_fallback and isinstance(ai_fallback, list) and ai_fallback and not self._is_placeholder_value(ai_fallback):
                    results_engine["weather_measurement_type"] = ai_fallback
        else:
            results_engine["weather_location"] = None
            results_engine["weather_measurement_type"] = None
            results_engine["weather_historical_source"] = None
        
        # PART 4: Financial/Administrative Fields (Section 5 and General Contract Data)
        # These can appear in Section 5 or in general contract data sections
        # Extract from full text or effective_section_5
        results_engine["interest_rate"] = self.phrase_extractor.extract_interest_rate(clean_text)
        results_engine["currency"] = self.phrase_extractor.extract_currency(clean_text)
        results_engine["fee_percentage"] = self.phrase_extractor.extract_fee_percentage(clean_text)
        results_engine["working_areas"] = self.phrase_extractor.extract_working_areas(clean_text)
        results_engine["key_persons"] = self.phrase_extractor.extract_key_persons(clean_text)
        results_engine["client_set_total"] = self.phrase_extractor.extract_client_set_total(clean_text)
        results_engine["contractor_share"] = self.phrase_extractor.extract_contractor_share(clean_text)
        results_engine["retention_period"] = self.phrase_extractor.extract_retention_period(clean_text)
        
        filled_count = sum(1 for v in results_engine.values() if v is not None)
        self.log(f"Phrase extraction: {filled_count} fields found")
        
        # STEP 3: AI validation and correction (using section text)
        self.log("Step 3: AI validation and correction (section-scoped)...")
        results_final = {}
        
        # Field to section mapping
        field_sections = {
            "starting_date": "3",
            "access_dates": "3",
            "completion_date": "3",
            "first_programme_submission": "3",
            "revised_programme_interval": "3",
            "period_for_reply": "3",
            "key_dates": "3",
            "defects_date": "4",
            "defect_correction_period": "4",
            "assessment_interval": "5",
            "payment_period": "5",
            "retention_percentage": "5",
            "delay_damages": "X7",
            "delay_damages_amount": "X7",
            "weather_location": "6",
            "weather_measurement_type": "6",
            "weather_historical_source": "6",
            # Financial/Administrative fields (can be in Section 5 or general contract data)
            "interest_rate": "5",
            "currency": "5",
            "fee_percentage": "5",
            "working_areas": "5",
            "key_persons": "5",
            "client_set_total": "5",
            "contractor_share": "5",
            "retention_period": "5",
        }
        
        # PART 5: REGRESSION GUARDS - Track valid values to prevent overwriting
        valid_values = {}  # Store valid extracted values
        
        # Build effective section texts for AI fallback (includes injected Contract Data)
        # Use the effective_section_X variables we already built
        effective_sections = {
            "3": effective_section_3,
            "4": self.sections.get("4", ""),
            "5": effective_section_5,
            "6": effective_section_6,
            "X7": self.sections.get("X7", ""),
        }
        
        # Debug: Log if Contract Data was injected
        if injected_blocks.get("3"):
            self.log(f"Contract Data injected for Section 3: {len(injected_blocks['3'])} chars")
        else:
            self.log("WARNING: No Contract Data injected for Section 3")
        
        # PRODUCTION HARDENING: Enforce engine authority and write-once semantics
        for field, value in results_engine.items():
            section_id = field_sections.get(field, "")
            section_text = effective_sections.get(section_id, "")
            
            # RULE 1: PhraseExtractor decides existence
            # RULE 2: Placeholder elimination (early)
            # RULE 7: Write-once field guarantee
            
            # Check if value is placeholder (treat as NULL)
            # CRITICAL: Also reject durations for date fields
            # NOTE: "confidential" is a valid value (indicates redaction), not a placeholder
            is_placeholder = False
            if value is None:
                is_placeholder = True
            elif isinstance(value, str):
                # "confidential" is a valid value, not a placeholder
                if value.strip().lower() == "confidential":
                    is_placeholder = False  # Keep "confidential" as valid value
                elif not value.strip() or self._is_placeholder_value(value):
                    is_placeholder = True
                # CRITICAL: Reject durations for date fields
                elif field in ["starting_date", "completion_date"]:
                    if re.search(r'\b\d+\s+(week|weeks|day|days|month|months)\b', value, re.IGNORECASE):
                        is_placeholder = True  # Treat duration as placeholder for date fields
            elif isinstance(value, list):
                if not value:
                    is_placeholder = True
                # For key_persons (list of dicts), check if all dicts are placeholders
                elif field == "key_persons" and value and len(value) > 0 and isinstance(value[0], dict):
                    if all(self._is_placeholder_value(item) for item in value):
                        is_placeholder = True
                # For string lists (like access_dates), check if all items are placeholders
                elif all(not item or (isinstance(item, str) and (not item.strip() or self._is_placeholder_value(item))) for item in value):
                    is_placeholder = True
                # CRITICAL: For access_dates, reject durations
                elif field == "access_dates":
                    # Filter out any items that are durations or placeholders
                    valid_items = [item for item in value if isinstance(item, str) and item.strip() and 
                                 not self._is_placeholder_value(item) and 
                                 not re.search(r'\b\d+\s+(week|weeks|day|days|month|months)\b', item, re.IGNORECASE)]
                    if not valid_items:
                        is_placeholder = True
                    else:
                        # Replace value with filtered list
                        value = valid_items
            
            # FIX 1: If PhraseExtractor returned a non-empty, non-placeholder value:
            # - It is FINAL for existence
            # - It may ONLY be cleaned (formatted) by AICorrector
            # - It MUST NOT be erased, rejected, or replaced
            if not is_placeholder and value is not None:
                # Write-once: If field already has a valid value, keep it
                if field in valid_values:
                    results_final[field] = valid_values[field]
                    continue
                
                # FIX 1: For date fields, if syntactically valid (DD Month YYYY), it MUST survive
                # CRITICAL: Reject durations (e.g., "4 weeks") for date fields
                if field in ["starting_date", "completion_date"]:
                    # Check if value is a syntactically valid date (NOT a duration)
                    if isinstance(value, str):
                        # Reject if it's a duration
                        if re.search(r'\b\d+\s+(week|weeks|day|days|month|months)\b', value, re.IGNORECASE):
                            # This is a duration, not a date - treat as placeholder to allow AI fallback
                            self.log(f"Rejecting duration for {field}: {value}")
                            is_placeholder = True
                            # Don't set results_final yet - let it fall through to AI fallback
                        elif self._is_valid_date_format(value):
                            # Valid date format - it is FINAL, only format it
                            cleaned = self.ai_corrector.clean(field, value, section_text)
                            # If cleaning fails or returns placeholder, keep original
                            if cleaned and not self._is_placeholder_value(cleaned) and self._is_valid_date_format(cleaned):
                                valid_values[field] = cleaned
                                results_final[field] = cleaned
                            else:
                                valid_values[field] = value
                                results_final[field] = value
                            continue
                        # If not a valid date format, treat as placeholder to allow AI fallback
                        is_placeholder = True
                elif field == "access_dates" and isinstance(value, list):
                    # For access_dates list, check if all items are valid dates (NOT durations)
                    valid_dates = []
                    for d in value:
                        if isinstance(d, str):
                            # Reject durations
                            if re.search(r'\b\d+\s+(week|weeks|day|days|month|months)\b', d, re.IGNORECASE):
                                continue  # Skip durations
                            if self._is_valid_date_format(d) and not self._is_placeholder_value(d):
                                valid_dates.append(d)
                    if valid_dates:
                        # Valid dates found - they are FINAL, only format them
                        cleaned = self.ai_corrector.clean(field, valid_dates, section_text)
                        # If cleaning fails or returns empty, keep original
                        if cleaned and isinstance(cleaned, list) and cleaned and not self._is_placeholder_value(cleaned):
                            # Verify all cleaned items are still dates
                            all_valid = all(self._is_valid_date_format(d) for d in cleaned if isinstance(d, str))
                            if all_valid:
                                valid_values[field] = cleaned
                                results_final[field] = cleaned
                            else:
                                valid_values[field] = valid_dates
                                results_final[field] = valid_dates
                        else:
                            valid_values[field] = valid_dates
                            results_final[field] = valid_dates
                        continue
                
                # Clean value (formatting only, not replacement)
                cleaned = self.ai_corrector.clean(field, value, section_text)
                
                # If cleaning returns None, empty list, or placeholder, keep original engine value
                if cleaned is None:
                    # Keep original engine value
                    valid_values[field] = value
                    results_final[field] = value
                elif isinstance(cleaned, list) and not cleaned:
                    # FIX 3: Empty list is failure - treat as None to allow AI fallback
                    if isinstance(value, list) and value:
                        # Original had values but cleaning returned empty - keep original
                        valid_values[field] = value
                        results_final[field] = value
                    else:
                        # Both original and cleaned are empty - treat as None (don't set valid_values)
                        # This allows AI fallback to run
                        results_final[field] = None
                elif self._is_placeholder_value(cleaned):
                    # Placeholder from cleaning - keep original engine value
                    valid_values[field] = value
                    results_final[field] = value
                else:
                    # Use cleaned value (formatted version)
                    valid_values[field] = cleaned
                    results_final[field] = cleaned
            else:
                # Engine returned None or placeholder → AI fallback ONLY if no value exists
                if field not in valid_values:
                    fallback = self.ai_corrector.ai_fallback_extract(field, clean_text, section_text)
                    if fallback and not self._is_placeholder_value(fallback):
                        # CRITICAL: For date fields, reject durations from AI fallback
                        if field in ["starting_date", "completion_date"]:
                            if isinstance(fallback, str) and re.search(r'\b\d+\s+(week|weeks|day|days|month|months)\b', fallback, re.IGNORECASE):
                                self.log(f"AI fallback returned duration for date field {field}, rejecting: {fallback}")
                                fallback = None
                        if fallback:
                            valid_values[field] = fallback
                            results_final[field] = fallback
                        else:
                            results_final[field] = None
                    else:
                        # No valid value found - set to None (will be converted to "" or [] at end)
                        results_final[field] = None
                else:
                    # Field already has value (write-once guarantee)
                    results_final[field] = valid_values[field]
        
        # FIX 3: Handle None values in final output (convert to empty string/list for output format)
        # But first, try AI fallback for None values that should have been extracted
        # NOTE: Skip AI fallback for less critical financial/administrative fields to avoid "not specified"
        skip_ai_fallback_fields = ["fee_percentage", "working_areas", "key_persons", "client_set_total", 
                                   "contractor_share", "retention_period"]
        
        for field in results_final:
            if results_final[field] is None:
                # Try AI fallback one more time if we haven't tried yet
                # Skip AI fallback for less critical fields (they often have placeholders)
                if field not in valid_values and field not in skip_ai_fallback_fields:
                    section_id = field_sections.get(field, "")
                    section_text = effective_sections.get(section_id, "")
                    fallback = self.ai_corrector.ai_fallback_extract(field, clean_text, section_text)
                    if fallback and not self._is_placeholder_value(fallback):
                        # CRITICAL: For date fields, reject durations
                        if field in ["starting_date", "completion_date"]:
                            if isinstance(fallback, str) and re.search(r'\b\d+\s+(week|weeks|day|days|month|months)\b', fallback, re.IGNORECASE):
                                # Fallback returned duration - reject it
                                fallback = None
                        # CRITICAL: For list fields, ensure AI returns correct type
                        if field == "key_persons":
                            # key_persons must be a list of dicts, not a string
                            if not isinstance(fallback, list):
                                fallback = None
                            elif fallback and not isinstance(fallback[0], dict):
                                fallback = None
                        if fallback:
                            valid_values[field] = fallback
                            results_final[field] = fallback
                            continue
                
                # Convert None to "not specified" for required fields
                # NOTE: key_persons can be "confidential" (string) or list, so handle specially
                if field == "key_persons":
                    # key_persons might be "confidential" string from extraction
                    if results_final.get(field) == "confidential":
                        results_final[field] = "confidential"  # Keep as string
                    elif results_final.get(field) is None:
                        results_final[field] = "not specified"  # Field doesn't exist
                    # Otherwise keep the existing value (list or "confidential")
                elif field == "key_dates":
                    # key_dates should be empty list if None (not "not specified")
                    results_final[field] = []
                elif field == "access_dates" or field == "weather_measurement_type":
                    # For list fields, use empty list if None (will be converted to "not specified" in final_output)
                    results_final[field] = []
                else:
                    # For string fields, use "not specified" if None (field doesn't exist in contract)
                    results_final[field] = "not specified"
        
        # RULE 7: Write-once field guarantee is enforced in the main loop
        # No additional logic needed - valid_values dict ensures first valid value wins
        
        # CRITICAL: Final validation - reject durations for date fields (safety net)
        # BUT: Only reject if it's actually a duration, don't reject empty strings
        if results_final.get("starting_date"):
            if isinstance(results_final["starting_date"], str) and results_final["starting_date"].strip():
                if re.search(r'\b\d+\s+(week|weeks|day|days|month|months)\b', results_final["starting_date"], re.IGNORECASE):
                    self.log(f"FINAL CHECK: Rejecting duration for starting_date: {results_final['starting_date']}")
                    results_final["starting_date"] = ""
        if results_final.get("completion_date"):
            if isinstance(results_final["completion_date"], str) and results_final["completion_date"].strip():
                if re.search(r'\b\d+\s+(week|weeks|day|days|month|months)\b', results_final["completion_date"], re.IGNORECASE):
                    self.log(f"FINAL CHECK: Rejecting duration for completion_date: {results_final['completion_date']}")
                    results_final["completion_date"] = ""
        
        # FIX 4: Payment logic isolation - assessment_interval MUST NOT be overwritten by payment_period
        # Ensure assessment_interval is isolated and protected
        if "assessment_interval" in valid_values:
            # assessment_interval already extracted - protect it from any overwriting
            results_final["assessment_interval"] = valid_values["assessment_interval"]
        
        # FIX 4: payment_period MUST NOT be inferred from assessment_interval
        # If payment_period == "Monthly", it's likely inferred - reject it
        payment_period_value = results_final.get("payment_period", "")
        if payment_period_value == "Monthly" and "payment_period" not in valid_values:
            # Only reject if we haven't already written a value (write-once guarantee)
            # Re-run extraction from full text (Y(UK)2 override)
            effective_section_5 = effective_sections.get("5", "")
            payment_period_retry = self.phrase_extractor.extract_payment_period(clean_text)
            if payment_period_retry and payment_period_retry != "Monthly" and not self._is_placeholder_value(payment_period_retry):
                valid_values["payment_period"] = payment_period_retry
                results_final["payment_period"] = payment_period_retry
            else:
                # Try AI fallback only if no value exists yet
                if "payment_period" not in valid_values:
                    ai_fallback = self.ai_corrector.ai_fallback_extract("payment_period", clean_text, effective_section_5)
                    if ai_fallback and ai_fallback != "Monthly" and not self._is_placeholder_value(ai_fallback):
                        valid_values["payment_period"] = ai_fallback
                        results_final["payment_period"] = ai_fallback
                    else:
                        results_final["payment_period"] = ""
        
        
        # Ensure all required fields are present in output
        # FIX 3: weather_measurement_type is a list field
        # Helper function to convert empty values to "not specified"
        def format_field_value(value, field_name):
            """Convert empty values to 'not specified', preserve 'confidential' and valid values."""
            # Preserve "confidential" values
            if value == "confidential":
                return "confidential"
            
            # Handle list fields (access_dates, weather_measurement_type, key_persons, key_dates)
            if isinstance(value, list):
                if not value:
                    # Empty list means field not found - return "not specified" for simple lists
                    # But key_dates should return empty list, not "not specified"
                    if field_name == "key_dates":
                        return []
                    return "not specified"
                # Non-empty list - return as is
                return value
            
            # Handle string fields
            if isinstance(value, str):
                if not value.strip() or value == "":
                    return "not specified"
                return value
            
            # None or other types - field not found
            return "not specified"
        
        # FINAL SAFETY CHECK: Filter out starting_date and completion_date from access_dates one more time
        # This ensures they're removed even if they were added back during AI processing
        access_dates_final = results_final.get("access_dates", [])
        if isinstance(access_dates_final, list) and access_dates_final:
            starting_date_final = results_final.get("starting_date", "")
            completion_date_final = results_final.get("completion_date", "")
            if starting_date_final or completion_date_final:
                dates_to_exclude = []
                if starting_date_final:
                    dates_to_exclude.append(re.sub(r'\s+', ' ', starting_date_final.strip().lower()))
                if completion_date_final:
                    dates_to_exclude.append(re.sub(r'\s+', ' ', completion_date_final.strip().lower()))
                
                filtered_dates = []
                for d in access_dates_final:
                    if isinstance(d, str):
                        d_normalized = re.sub(r'\s+', ' ', d.strip().lower())
                        if d_normalized not in dates_to_exclude:
                            filtered_dates.append(d)
                
                if filtered_dates:
                    results_final["access_dates"] = filtered_dates
                    self.log(f"FINAL FILTER: Removed starting_date/completion_date from access_dates, kept {len(filtered_dates)} dates")
                else:
                    results_final["access_dates"] = []
                    self.log(f"FINAL FILTER: All access_dates were starting_date/completion_date, set to empty")
        
        final_output = {
            "starting_date": format_field_value(results_final.get("starting_date", ""), "starting_date"),
            "access_dates": format_field_value(results_final.get("access_dates", []), "access_dates"),
            "completion_date": format_field_value(results_final.get("completion_date", ""), "completion_date"),
            "first_programme_submission": format_field_value(results_final.get("first_programme_submission", ""), "first_programme_submission"),
            "revised_programme_interval": format_field_value(results_final.get("revised_programme_interval", ""), "revised_programme_interval"),
            "period_for_reply": format_field_value(results_final.get("period_for_reply", ""), "period_for_reply"),
            "key_dates": format_field_value(results_final.get("key_dates", []), "key_dates"),
            "defects_date": format_field_value(results_final.get("defects_date", ""), "defects_date"),
            "defect_correction_period": format_field_value(results_final.get("defect_correction_period", ""), "defect_correction_period"),
            "assessment_interval": format_field_value(results_final.get("assessment_interval", ""), "assessment_interval"),
            "payment_period": format_field_value(results_final.get("payment_period", ""), "payment_period"),
            "retention_percentage": format_field_value(results_final.get("retention_percentage", ""), "retention_percentage"),
            "delay_damages": format_field_value(results_final.get("delay_damages", ""), "delay_damages"),
            "delay_damages_amount": format_field_value(results_final.get("delay_damages_amount", ""), "delay_damages_amount"),
            "weather_location": format_field_value(results_final.get("weather_location", ""), "weather_location"),
            "weather_measurement_type": format_field_value(results_final.get("weather_measurement_type", []), "weather_measurement_type"),
            "weather_historical_source": format_field_value(results_final.get("weather_historical_source", ""), "weather_historical_source"),
            # Financial/Administrative fields
            "interest_rate": format_field_value(results_final.get("interest_rate", ""), "interest_rate"),
            "currency": format_field_value(results_final.get("currency", ""), "currency"),
            "fee_percentage": format_field_value(results_final.get("fee_percentage", ""), "fee_percentage"),
            "working_areas": format_field_value(results_final.get("working_areas", ""), "working_areas"),
            "key_persons": format_field_value(results_final.get("key_persons", []), "key_persons"),
            "client_set_total": format_field_value(results_final.get("client_set_total", ""), "client_set_total"),
            "contractor_share": format_field_value(results_final.get("contractor_share", ""), "contractor_share"),
            "retention_period": format_field_value(results_final.get("retention_period", ""), "retention_period")
        }
        
        filled_count_after_ai = sum(1 for v in final_output.values() if v and (isinstance(v, str) and v.strip() or isinstance(v, list) and v))
        self.log(f"After AI validation: {filled_count_after_ai} fields filled")
        
        return final_output
    
    def _inject_contract_data_rows(self, clean_text: str) -> Dict[str, str]:
        """
        Scan full clean_text for Contract Data rows and return injected blocks.
        
        Contract Data rows appear in tables BEFORE clause headers, so they're not captured
        by section detection. This method finds them and returns them for injection.
        
        Returns:
            Dictionary mapping section IDs to injected Contract Data text:
            {
                "3": "<contract data text>",
                "5": "<payment contract data text>",
                "6": "<weather contract data text>"
            }
        """
        # Contract Data label patterns mapped to their target sections
        # These labels appear in Contract Data tables BEFORE clause headers
        # Exact labels as they appear in the contract
        contract_data_patterns = {
            "3": [
                r"The\s+starting\s+date\s+is",
                r"The\s+access\s+dates\s+are",
                r"The\s+Completion\s+Date\s+for\s+the\s+whole\s+of\s+the\s+works\s+is",
                r"The\s+period\s+after\s+the\s+Contract\s+Date\s+within\s+which\s+the\s+Contractor\s+is\s+to\s+submit\s+a\s+first\s+programme",
                r"The\s+Contractor\s+submits\s+revised\s+programmes\s+at",
                # Also catch variations for robustness
                r"starting\s+date",
                r"access\s+date",
                r"Completion\s+Date",
                r"first\s+programme",
                r"revised\s+programmes",
            ],
            "5": [
                r"The\s+assessment\s+interval\s+is",
                r"assessment\s+interval\s+is",
                r"The\s+period\s+for\s+payment\s+is",
                r"period\s+for\s+payment",
            ],
            "6": [
                r"The\s+weather\s+measurements\s+to\s+be\s+recorder",  # Handle typo "recorder" vs "recorded"
                r"The\s+weather\s+measurements\s+to\s+be\s+recorded",
                r"The\s+weather\s+measurements",
                r"weather\s+measurements",
                r"The\s+place\s+where\s+weather\s+is\s+to\s+be\s+recorded\s+is",
                r"weather\s+data\s+are\s+the\s+records",
            ],
        }
        
        # Collect Contract Data blocks for each section
        contract_data_blocks = {"3": [], "5": [], "6": []}
        
        # Scan full text for Contract Data labels
        self.log(f"DEBUG: Scanning full text ({len(clean_text)} chars) for Contract Data labels...")
        for section_id, patterns in contract_data_patterns.items():
            for pattern in patterns:
                matches = list(re.finditer(pattern, clean_text, re.IGNORECASE))
                if matches:
                    self.log(f"DEBUG: Found {len(matches)} matches for pattern '{pattern[:50]}...' in section {section_id}")
                for match in matches:
                    # Capture label line + next 3 non-empty lines
                    start_pos = match.start()
                    end_pos = match.end()
                    
                    # Get text after label
                    text_after = clean_text[end_pos:]
                    lines_after = text_after.split('\n')
                    
                    # Collect label line + next 5 non-empty lines (table format may have more lines)
                    block_lines = [clean_text[start_pos:end_pos]]
                    non_empty_count = 0
                    
                    # For access_dates, capture more lines (may have multiple dates)
                    max_lines = 8 if "access" in pattern.lower() else 5
                    for line in lines_after[:30]:  # Check up to 30 lines to find non-empty lines
                        stripped = line.strip()
                        if stripped:
                            block_lines.append(stripped)
                            non_empty_count += 1
                            if non_empty_count >= max_lines:
                                break
                    
                    # Create block text
                    block_text = '\n'.join(block_lines)
                    
                    # Check if this block is already in the section text (avoid duplication)
                    section_text = self.sections.get(section_id, "")
                    # Use a more lenient check - if the label pattern already exists in section, skip
                    label_in_section = re.search(pattern, section_text, re.IGNORECASE)
                    if not label_in_section:
                        contract_data_blocks[section_id].append(block_text)
                        self.log(f"Found Contract Data row for Section {section_id}: {pattern[:50]}...")
                    else:
                        self.log(f"Skipping duplicate Contract Data row for Section {section_id}: {pattern[:50]}...")
        
        # Build injected blocks dictionary
        injected_blocks = {}
        for section_id, blocks in contract_data_blocks.items():
            if blocks:
                injected_text = '\n'.join(blocks)
                injected_blocks[section_id] = injected_text
                self.log(f"Prepared {len(blocks)} Contract Data block(s) for Section {section_id}")
            else:
                injected_blocks[section_id] = ""
        
        return injected_blocks
    
    def _is_valid_date_format(self, value: str) -> bool:
        """Check if value is a syntactically valid date (DD Month YYYY format)."""
        if not value or not isinstance(value, str):
            return False
        # CRITICAL: Reject durations - dates can NEVER be durations
        if re.search(r'\b\d+\s+(week|weeks|day|days|month|months)\b', value, re.IGNORECASE):
            return False
        # Pattern: DD Month YYYY
        pattern = r'\b\d{1,2}\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b'
        return bool(re.search(pattern, value, re.IGNORECASE))
    
    def _is_placeholder_value(self, value: Any) -> bool:
        """
        Check if value is a placeholder (treat as NULL).
        
        RULE 2: Placeholder elimination (early & final)
        Placeholders are NEVER valid values and must NEVER survive to output.
        """
        if value is None:
            return True
        
        if isinstance(value, list):
            # For lists, check if all items are placeholders
            if not value:
                return True
            return all(self._is_placeholder_value(item) for item in value)
        
        if isinstance(value, dict):
            # For dictionaries (e.g., key_persons), check if all values are placeholders
            if not value:
                return True
            return all(self._is_placeholder_value(v) for v in value.values())
        
        if not isinstance(value, str):
            return False
        
        if not value.strip():
            return True
        
        value_lower = value.strip().lower()
        placeholders = [
            "tbc", "tbd", "to be confirmed", "to be determined",
            "insert date", "insert details", "none set", "not set",
            "not stated", "specified but redacted", "not specified",
            "blank", "empty", "n/a", "na", "-", "...", "xxx",
            "fastdraft", "insert", "to be", "not used"
        ]
        
        # Check exact match
        if value_lower in placeholders:
            return True
        # Check if value contains placeholder
        for placeholder in placeholders:
            if placeholder in value_lower:
                return True
        
        return False
