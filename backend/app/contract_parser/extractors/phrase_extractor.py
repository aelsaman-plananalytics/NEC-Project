"""
NEC Contract Phrase Extractor (Deterministic Phrase-Anchored Method)

Searches clean_text for EXACT phrases and extracts data immediately following or preceding.
Case-insensitive matching.
"""

import re
from typing import Dict, List, Any, Optional


class PhraseExtractor:
    """
    Deterministic phrase-based extractor for NEC4 contracts.
    
    Rules:
    - Search entire clean_text for EXACT phrases (case-insensitive)
    - Extract data immediately following or preceding the phrase
    - Return None if no match found (NOT empty string)
    """
    
    def __init__(self, debug: bool = False):
        """Initialize phrase extractor."""
        self.debug = debug
    
    def log(self, msg: str):
        """Debug logging."""
        # Always print DEBUG messages, even if debug=False
        if "DEBUG" in msg or self.debug:
            print(f"[PhraseExtractor] {msg}")
    
    def extract(self, clean_text: str) -> Dict[str, Any]:
        """
        Extract all fields from clean_text using exact phrase patterns.
        
        Args:
            clean_text: Full clean text from PDF (no slicing)
            
        Returns:
            Dictionary with extracted field values (None if not found)
        """
        results = {}
        
        # TIME SECTION (Section 3)
        results["starting_date"] = self.extract_starting_date(clean_text)
        results["access_dates"] = self.extract_access_dates(clean_text)
        results["completion_date"] = self.extract_completion_date(clean_text)
        results["first_programme_submission"] = self.extract_first_programme_submission(clean_text)
        results["revised_programme_interval"] = self.extract_revised_programme_interval(clean_text)
        
        # DEFECTS SECTION (Section 4)
        results["defects_date"] = self.extract_defects_date(clean_text)
        results["defect_correction_period"] = self.extract_defect_correction_period(clean_text)
        
        # OPTION X7 - DELAY DAMAGES
        results["delay_damages"] = self.extract_delay_damages(clean_text)
        
        # PAYMENTS SECTION (Section 5)
        results["assessment_interval"] = self.extract_assessment_interval(clean_text)
        results["payment_period"] = self.extract_payment_period(clean_text)
        results["retention_percentage"] = self.extract_retention_percentage(clean_text)
        
        # WEATHER DATA (Section 6)
        results["weather_location"] = self.extract_weather_location(clean_text)
        results["weather_measurement_type"] = self.extract_weather_measurement_type(clean_text)
        results["weather_historical_source"] = self.extract_weather_historical_source(clean_text)
        
        return results
    
    # TIME SECTION (Section 3)
    
    def extract_starting_date(self, text: str) -> Optional[str]:
        """Extract starting date - multiline label → value extraction."""
        # Detect label line - be more flexible with whitespace and variations
        label_patterns = [
            r'(?:The\s+)?starting\s+date\s+is',
            r'(?:The\s+)?Starting\s+Date\s+is',
            r'starting\s+date\s+is',
            r'Starting\s+Date\s+is',
            r'start\s+date',
            r'Start\s+Date',
            r'starting\s+date',
        ]
        
        self.log(f"DEBUG extract_starting_date: Searching in text ({len(text)} chars)")
        found_label = False
        
        # First, try exact label matching
        for label_pattern in label_patterns:
            matches = list(re.finditer(label_pattern, text, re.IGNORECASE))
            if matches:
                self.log(f"DEBUG extract_starting_date: Found {len(matches)} matches for pattern '{label_pattern}'")
                found_label = True
            for match in matches:
                # Look ahead up to 10 non-empty lines (table format may have more lines)
                start_pos = match.end()
                lines = text[start_pos:].split('\n')
                
                # Get next 10 non-empty lines
                non_empty_lines = []
                for line in lines[:30]:  # Check up to 30 lines to find 10 non-empty
                    stripped = line.strip()
                    if stripped:
                        non_empty_lines.append(stripped)
                        if len(non_empty_lines) >= 10:
                            break
                
                # Search for first valid DATE (not duration) in these lines
                self.log(f"DEBUG extract_starting_date: Checking {len(non_empty_lines)} non-empty lines after label")
                for i, line in enumerate(non_empty_lines):
                    # Strip leading table artefacts
                    cleaned_line = re.sub(r'^\d+\s+', '', line)
                    self.log(f"DEBUG extract_starting_date: Line {i+1}: '{cleaned_line[:100]}'")
                    # CRITICAL: Only extract dates, NOT durations (reject "4 weeks", etc.)
                    # Check if line contains a duration pattern first - if so, skip it
                    if re.search(r'\b\d+\s+(week|weeks|day|days|month|months)\b', cleaned_line, re.IGNORECASE):
                        self.log(f"DEBUG extract_starting_date: Line {i+1} contains duration, skipping")
                        continue  # Skip lines with durations
                    date_value = self._extract_date_from_context(cleaned_line)
                    if date_value:
                        self.log(f"DEBUG extract_starting_date: Found date value: {date_value}")
                        # Ignore placeholders
                        if not self._is_placeholder(date_value):
                            self.log(f"Found starting_date: {date_value}")
                            return date_value
                        else:
                            self.log(f"DEBUG extract_starting_date: Date value is placeholder: {date_value}")
                    else:
                        self.log(f"DEBUG extract_starting_date: No date found in line {i+1}")
        
        # FALLBACK: If no label found, search for dates near "starting" keyword
        if not found_label:
            self.log(f"DEBUG extract_starting_date: No label pattern matched, trying fallback search...")
            # Find all occurrences of "starting" (case insensitive)
            starting_matches = list(re.finditer(r'\bstarting\b', text, re.IGNORECASE))
            for match in starting_matches:
                # Look in a window around "starting" (200 chars before and after)
                start_pos = max(0, match.start() - 200)
                end_pos = min(len(text), match.end() + 200)
                context = text[start_pos:end_pos]
                
                # Extract all dates from this context
                dates = self._extract_all_dates_from_context(context)
                for date_val in dates:
                    if date_val and not self._is_placeholder(date_val):
                        # Check if it's not a duration
                        if not re.search(r'\b\d+\s+(week|weeks|day|days|month|months)\b', date_val, re.IGNORECASE):
                            self.log(f"DEBUG extract_starting_date: Found date near 'starting' via fallback: {date_val}")
                            return date_val
        
        if found_label:
            self.log(f"DEBUG extract_starting_date: Label found but no valid date extracted")
        else:
            self.log(f"DEBUG extract_starting_date: No label pattern matched and fallback found nothing")
        
        return None
    
    def extract_access_dates(self, text: str, starting_date: Optional[str] = None, completion_date: Optional[str] = None) -> Optional[List[str]]:
        """Extract access dates - multiline label → value extraction with cleaning."""
        # Detect label line - be more flexible with patterns
        # Note: Label may be "The access dates are part of the Site" - we need to match "are" and look further
        label_patterns = [
            r'(?:The\s+)?access\s+dates\s+are',
            r'(?:The\s+)?Access\s+dates\s+are',
            r'(?:The\s+)?Access\s+Dates\s+are',
            r'Access\s+Date\s*:',  # Handle "Access Date: 1 March 2026" format
            r'access\s+date\s*:',
            r'Access\s+Date',
            r'access\s+date',
            r'Access\s+dates',
        ]
        
        self.log(f"DEBUG extract_access_dates: Searching in text ({len(text)} chars)")
        all_dates = []
        found_label = False
        
        # Get starting_date to exclude it from access_dates if not provided
        if not starting_date:
            # Try to find starting_date pattern in text
            starting_date_match = re.search(r'The\s+starting\s+date\s+is\s+(\d{1,2}\s+\w+\s+\d{4})', text, re.IGNORECASE)
            if starting_date_match:
                starting_date = starting_date_match.group(1)
                self.log(f"DEBUG extract_access_dates: Found starting_date to exclude: {starting_date}")
        
        if starting_date:
            self.log(f"DEBUG extract_access_dates: Will exclude starting_date '{starting_date}' from results")
        
        for label_pattern in label_patterns:
            matches = list(re.finditer(label_pattern, text, re.IGNORECASE))
            if matches:
                self.log(f"DEBUG extract_access_dates: Found {len(matches)} matches for pattern '{label_pattern}'")
                found_label = True
            for match in matches:
                # Look ahead up to 20 non-empty lines (may have placeholders and other dates before access dates)
                start_pos = match.end()
                lines = text[start_pos:].split('\n')
                
                # Get next 20 non-empty lines (to skip past placeholders and find actual access dates)
                non_empty_lines = []
                for line in lines[:50]:  # Check up to 50 lines to find 20 non-empty
                    stripped = line.strip()
                    if stripped:
                        non_empty_lines.append(stripped)
                        if len(non_empty_lines) >= 20:
                            break
                
                # FIX 2: Extract all dates from these lines with table normalization
                # Check each line individually for dates (table format has one date per line)
                self.log(f"DEBUG extract_access_dates: Checking {len(non_empty_lines)} non-empty lines after label")
                for i, line in enumerate(non_empty_lines):
                    # FIX 2: Strip leading numeric table artefacts (e.g., "0 20 March 2023" → "20 March 2023")
                    # Remove leading digits that are likely table formatting
                    cleaned_line = re.sub(r'^\d+\s+', '', line)
                    self.log(f"DEBUG extract_access_dates: Line {i+1}: '{cleaned_line[:100]}'")
                    # FIX 2: Ignore placeholder strings ("insert details", "FastDraft", etc.)
                    if self._is_placeholder(cleaned_line):
                        self.log(f"DEBUG extract_access_dates: Line {i+1} is placeholder, skipping")
                        continue
                    # CRITICAL: Reject lines that contain FastDraft or placeholder text
                    # Even if they contain dates, these are placeholder dates, not real access dates
                    cleaned_lower = cleaned_line.lower()
                    if any(junk in cleaned_lower for junk in ["fastdraft", "asite"]):
                        self.log(f"DEBUG extract_access_dates: Line {i+1} contains FastDraft/Asite placeholder, skipping even if it has dates")
                        continue
                    
                    # Check if line contains a date
                    has_date = bool(self._extract_all_dates_from_context(cleaned_line))
                    if not has_date:
                        # Only reject if no date found
                        if any(junk in cleaned_lower for junk in ["insert", "tbc", "none set", "not set"]):
                            # But don't reject if it's just the word "date" - that might be part of a label
                            if cleaned_lower.strip() != "date":
                                self.log(f"DEBUG extract_access_dates: Line {i+1} contains junk and no date, skipping")
                                continue
                    
                    # Extract dates from this line
                    line_dates = self._extract_all_dates_from_context(cleaned_line)
                    self.log(f"DEBUG extract_access_dates: Line {i+1} extracted {len(line_dates)} dates: {line_dates}")
                    for date_val in line_dates:
                        if date_val and not self._is_placeholder(date_val):
                            # CRITICAL: Exclude starting_date and completion_date from access_dates
                            # Normalize dates for comparison (strip, lowercase, normalize whitespace)
                            date_val_normalized = re.sub(r'\s+', ' ', date_val.strip().lower())
                            if starting_date:
                                starting_date_normalized = re.sub(r'\s+', ' ', starting_date.strip().lower())
                                if date_val_normalized == starting_date_normalized:
                                    self.log(f"DEBUG extract_access_dates: Skipping date '{date_val}' - it's the starting_date '{starting_date}'")
                                    continue
                            if completion_date:
                                completion_date_normalized = re.sub(r'\s+', ' ', completion_date.strip().lower())
                                if date_val_normalized == completion_date_normalized:
                                    self.log(f"DEBUG extract_access_dates: Skipping date '{date_val}' - it's the completion_date '{completion_date}'")
                                    continue
                            
                            # Count how many times this date appears in all_dates so far
                            count_so_far = all_dates.count(date_val)
                            # Allow up to 2 occurrences (contract may list same date twice)
                            if count_so_far < 2:
                                all_dates.append(date_val)
                                self.log(f"DEBUG extract_access_dates: Added date: {date_val} (occurrence {count_so_far + 1})")
                            else:
                                self.log(f"DEBUG extract_access_dates: Skipping duplicate date (already appears {count_so_far} times): {date_val}")
        
        # FALLBACK: If no label found or no dates found, search for dates near "access dates" keyword (more specific)
        if not all_dates:
            self.log(f"DEBUG extract_access_dates: No dates found via label, trying fallback search...")
            # Find all occurrences of "access dates" or "access date" (case insensitive, more specific)
            access_patterns = [
                r'access\s+dates',
                r'access\s+date',
            ]
            seen_fallback_dates = set()
            for pattern in access_patterns:
                access_matches = list(re.finditer(pattern, text, re.IGNORECASE))
                for match in access_matches:
                    # Look in a window AFTER "access dates" (500 chars after, 100 chars before)
                    start_pos = max(0, match.start() - 100)
                    end_pos = min(len(text), match.end() + 500)
                    context = text[start_pos:end_pos]
                    
                    # Extract all dates from this context
                    # But check if context contains FastDraft - if so, skip these dates
                    context_lower = context.lower()
                    if "fastdraft" in context_lower or "asite" in context_lower:
                        self.log(f"DEBUG extract_access_dates: Fallback context contains FastDraft/Asite, skipping dates from this context")
                        continue
                    
                    dates = self._extract_all_dates_from_context(context)
                    for date_val in dates:
                        if date_val and not self._is_placeholder(date_val):
                            # CRITICAL: Exclude starting_date and completion_date from access_dates
                            # Normalize dates for comparison (strip, lowercase, normalize whitespace)
                            date_val_normalized = re.sub(r'\s+', ' ', date_val.strip().lower())
                            if starting_date:
                                starting_date_normalized = re.sub(r'\s+', ' ', starting_date.strip().lower())
                                if date_val_normalized == starting_date_normalized:
                                    self.log(f"DEBUG extract_access_dates: Skipping date '{date_val}' in fallback - it's the starting_date '{starting_date}'")
                                    continue
                            if completion_date:
                                completion_date_normalized = re.sub(r'\s+', ' ', completion_date.strip().lower())
                                if date_val_normalized == completion_date_normalized:
                                    self.log(f"DEBUG extract_access_dates: Skipping date '{date_val}' in fallback - it's the completion_date '{completion_date}'")
                                    continue
                            
                            # Check if it's not a duration
                            if not re.search(r'\b\d+\s+(week|weeks|day|days|month|months)\b', date_val, re.IGNORECASE):
                                # Only add if not already seen
                                if date_val not in seen_fallback_dates:
                                    seen_fallback_dates.add(date_val)
                                    all_dates.append(date_val)
                                    self.log(f"DEBUG extract_access_dates: Found date near '{pattern}' via fallback: {date_val}")
        
        # Deduplicate dates while preserving order
        # Keep unique dates, but preserve duplicates if they appear multiple times in the contract
        # (e.g., if "20 March 2023" appears twice in the contract, keep it twice)
        # Limit to max 2 occurrences per date to prevent excessive repetition
        final_dates = []
        date_counts = {}
        for date_val in all_dates:
            count = date_counts.get(date_val, 0)
            if count < 2:  # Allow up to 2 occurrences of the same date
                final_dates.append(date_val)
                date_counts[date_val] = count + 1
        
        if not final_dates:
            if found_label:
                self.log(f"DEBUG extract_access_dates: Label found but no valid dates extracted")
            else:
                self.log(f"DEBUG extract_access_dates: No label pattern matched and fallback found nothing")
            return None
        
        # Return dates (with limited duplicates)
        self.log(f"DEBUG extract_access_dates: Returning {len(final_dates)} dates: {final_dates}")
        return final_dates
    
    def extract_completion_date(self, text: str) -> Optional[str]:
        """Extract completion date - multiline extraction, prefer FINAL populated date."""
        # MANDATORY: First check for "Completion Date for the whole of the works is"
        mandatory_label = r'Completion\s+Date\s+for\s+the\s+whole\s+of\s+the\s+works\s+is'
        match = re.search(mandatory_label, text, re.IGNORECASE)
        if match:
            # Look ahead up to 3 non-empty lines
            start_pos = match.end()
            lines = text[start_pos:].split('\n')
            
            non_empty_lines = []
            for line in lines[:10]:
                stripped = line.strip()
                if stripped:
                    non_empty_lines.append(stripped)
                    if len(non_empty_lines) >= 3:
                        break
            
            for line in non_empty_lines:
                date_value = self._extract_date_from_context(line)
                if date_value and not self._is_placeholder(date_value):
                    self.log(f"Found completion_date (mandatory pattern): {date_value}")
                    return date_value
        
        # Fallback: collect ALL completion dates in Section 3, prefer the FINAL one
        label_patterns = [
            r'Completion\s+Date',
            r'completion\s+date',
            r'The\s+Completion\s+Date\s+is',
        ]
        
        all_completion_dates = []
        for label_pattern in label_patterns:
            matches = list(re.finditer(label_pattern, text, re.IGNORECASE))
            for match in matches:
                # Look ahead up to 3 non-empty lines
                start_pos = match.end()
                lines = text[start_pos:].split('\n')
                
                non_empty_lines = []
                for line in lines[:10]:
                    stripped = line.strip()
                    if stripped:
                        non_empty_lines.append(stripped)
                        if len(non_empty_lines) >= 3:
                            break
                
                for line in non_empty_lines:
                    date_value = self._extract_date_from_context(line)
                    if date_value and not self._is_placeholder(date_value):
                        all_completion_dates.append((match.start(), date_value))
        
        # Prefer the FINAL (last) populated date
        if all_completion_dates:
            # Sort by position (last occurrence)
            all_completion_dates.sort(key=lambda x: x[0])
            final_date = all_completion_dates[-1][1]
            self.log(f"Found completion_date (final): {final_date}")
            return final_date
        
        # Return "" if phrase found but no date (not None)
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in label_patterns):
            return ""
        
        return None
    
    def extract_first_programme_submission(self, text: str) -> Optional[str]:
        """Extract first programme submission - multiline label → value extraction."""
        # Detect label line - handle multiple formats
        # NOTE: "Programme submission interval" is for revised_programme_interval, not first_programme_submission
        label_patterns = [
            r'submit\s+a\s+first\s+programme',
            r'first\s+programme\s+for\s+acceptance',
            r'submit\s+the\s+first\s+programme',
            r'first\s+programme',
        ]
        
        for label_pattern in label_patterns:
            matches = list(re.finditer(label_pattern, text, re.IGNORECASE))
            for match in matches:
                # Look ahead up to 5 non-empty lines (to handle table formats)
                start_pos = match.end()
                lines = text[start_pos:].split('\n')
                
                # Get next 5 non-empty lines
                non_empty_lines = []
                for line in lines[:15]:
                    stripped = line.strip()
                    if stripped:
                        non_empty_lines.append(stripped)
                        if len(non_empty_lines) >= 5:
                            break
                
                # Search for first valid duration in these lines
                for line in non_empty_lines:
                    # Check for "Every X weeks" format first
                    every_match = re.search(r'Every\s+(\d+)\s+(week|weeks|month|months)', line, re.IGNORECASE)
                    if every_match:
                        duration_value = f"{every_match.group(1)} {every_match.group(2)}"
                        if not self._is_placeholder(duration_value):
                            self.log(f"Found first_programme_submission: {duration_value}")
                            return duration_value
                    
                    # Fallback to standard duration extraction
                    duration_value = self._extract_duration_from_context(line)
                    if duration_value:
                        # Ignore placeholders
                        if not self._is_placeholder(duration_value):
                            self.log(f"Found first_programme_submission: {duration_value}")
                            return duration_value
        
        return None
    
    def extract_revised_programme_interval(self, text: str) -> Optional[str]:
        """Extract revised programme interval - multiline label → value extraction."""
        # Detect label line - handle multiple formats
        label_patterns = [
            r'revised\s+programmes\s+at',
            r'submits\s+revised\s+programmes',
            r'intervals\s+no\s+longer\s+than',
            r'revised\s+programmes',
            r'Programme\s+submission\s+interval',  # Alternative: "Programme submission interval: Every 4 weeks"
            r'programme\s+submission\s+interval',
        ]
        
        for label_pattern in label_patterns:
            matches = list(re.finditer(label_pattern, text, re.IGNORECASE))
            for match in matches:
                # Look ahead up to 5 non-empty lines
                start_pos = match.end()
                lines = text[start_pos:].split('\n')
                
                # Get next 5 non-empty lines
                non_empty_lines = []
                for line in lines[:15]:
                    stripped = line.strip()
                    if stripped:
                        non_empty_lines.append(stripped)
                        if len(non_empty_lines) >= 5:
                            break
                
                # Search for first valid duration in these lines
                for line in non_empty_lines:
                    # Check for "Every X weeks" format first
                    every_match = re.search(r'Every\s+(\d+)\s+(week|weeks|month|months)', line, re.IGNORECASE)
                    if every_match:
                        duration_value = f"{every_match.group(1)} {every_match.group(2)}"
                        if not self._is_placeholder(duration_value):
                            self.log(f"Found revised_programme_interval: {duration_value}")
                            return duration_value
                    
                    # Fallback to standard duration extraction
                    duration_value = self._extract_duration_from_context(line)
                    if duration_value:
                        # Ignore placeholders
                        if not self._is_placeholder(duration_value):
                            self.log(f"Found revised_programme_interval: {duration_value}")
                            return duration_value
        
        return None
    
    # DEFECTS SECTION (Section 4)
    
    def extract_defects_date(self, text: str) -> Optional[str]:
        """Extract defects date - anchor 'the period between Completion' - extract durations only."""
        REQUIRED_PHRASES = [
            r"the\s+period\s+between\s+Completion",
            r"period\s+between\s+Completion",
        ]
        
        for phrase in REQUIRED_PHRASES:
            matches = list(re.finditer(phrase, text, re.IGNORECASE))
            for match in matches:
                # Extract text after phrase (up to 100 chars)
                start_pos = match.end()
                end_pos = min(len(text), start_pos + 100)
                context = text[start_pos:end_pos]
                
                # Extract duration only (e.g., "52 weeks")
                duration_value = self._extract_duration_from_context(context)
                if duration_value:
                    self.log(f"Found defects_date: {duration_value}")
                    return duration_value
        
        return None
    
    def extract_defect_correction_period(self, text: str) -> Optional[str]:
        """Extract defect correction period - look for 'The defect correction period is'."""
        # CRITICAL: Only extract if explicitly mentioned - don't confuse with defects_date
        # Must have explicit "defect correction period" label, not just "defects date"
        REQUIRED_PHRASES = [
            r"The\s+defect\s+correction\s+period\s+is",
            r"defect\s+correction\s+period\s+is",
            r"defect\s+correction\s+period\s*:",
        ]
        
        found_label = False
        for phrase in REQUIRED_PHRASES:
            matches = list(re.finditer(phrase, text, re.IGNORECASE))
            if matches:
                found_label = True
                for match in matches:
                    # Extract text after phrase (±200 chars)
                    start_pos = match.end()
                    end_pos = min(len(text), start_pos + 200)
                    context = text[start_pos:end_pos]
                    
                    # Extract duration
                    duration_value = self._extract_duration_from_context(context)
                    if duration_value:
                        self.log(f"Found defect_correction_period: {duration_value}")
                        return duration_value
        
        # If label found but no value, likely redacted
        if found_label:
            return "confidential"
        
        # If no label found, return None (will become "not specified")
        return None
    
    # OPTION X7 - DELAY DAMAGES
    
    def extract_delay_damages(self, text: str) -> Optional[str]:
        """Extract delay damages from X7."""
        X7_PATTERNS = [
            r"Delay\s+damages\s+for\s+Completion",
            r"OPTION\s+X7",
            r"\bX7\b",
        ]
        
        # Check if X7 exists
        has_x7 = any(re.search(pattern, text, re.IGNORECASE) for pattern in X7_PATTERNS)
        if not has_x7:
            return None
        
        # Check for redacted values
        if re.search(r'[█#\*]{3,}|\[REDACTED\]|redacted', text, re.IGNORECASE):
            return "confidential"
        
        # Look for the specific label pattern - handle multiple formats
        label_patterns = [
            r"Delay\s+damages\s+for\s+Completion\s+of\s+the\s+whole\s+of\s+the\s+works\s+are",
            r"Delay\s+damages\s+for\s+Completion\s+are",
            r"Delay\s+damages\s+for\s+Completion",
            r"Delay\s+damages\s*:",
            r"Delay\s+damages\s+are",
            r"Delay\s+damages",
        ]
        
        found_label = False
        for pattern in label_patterns:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            if matches:
                found_label = True
                for match in matches:
                    # Extract text around phrase (±300 chars)
                    start_pos = max(0, match.start() - 100)
                    end_pos = min(len(text), match.end() + 300)
                    context = text[start_pos:end_pos]
                    
                    # Extract currency amount
                    currency_value = self._extract_currency_from_context(context)
                    if currency_value:
                        self.log(f"Found delay_damages: {currency_value}")
                        return currency_value
        
        # Extract amount if present (fallback to old method)
        for pattern in X7_PATTERNS:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            for match in matches:
                # Extract text around phrase (±300 chars)
                start_pos = max(0, match.start() - 100)
                end_pos = min(len(text), match.end() + 300)
                context = text[start_pos:end_pos]
                
                # Extract currency amount
                currency_value = self._extract_currency_from_context(context)
                if currency_value:
                    self.log(f"Found delay_damages: {currency_value}")
                    return currency_value
        
        # If X7 exists but no amount found, likely redacted
        if has_x7 or found_label:
            return "confidential"
        
        return None
    
    def extract_delay_damages_amount(self, text: str) -> Optional[str]:
        """Extract delay damages amount separately."""
        delay_damages = self.extract_delay_damages(text)
        if not delay_damages:
            return None
        
        # If delay_damages is confidential, amount is also confidential
        if delay_damages == "confidential":
            return "confidential"
        
        # Extract amount from delay_damages string
        amount_match = re.search(r'([£$€]?\s*\d[\d,\.]*)\s*(per|a)\s*(day|week|month)', delay_damages, re.IGNORECASE)
        if amount_match:
            return amount_match.group(0).strip()
        
        # If delay_damages exists but no amount extracted, likely redacted
        return "confidential"
    
    # PAYMENTS SECTION (Section 5)
    
    def extract_assessment_interval(self, text: str) -> Optional[str]:
        """Extract assessment interval - anchor 'The assessment interval is' - extract single word."""
        REQUIRED_PHRASES = [
            r"The\s+assessment\s+interval\s+is",
            r"assessment\s+interval\s+is",
        ]
        
        for phrase in REQUIRED_PHRASES:
            matches = list(re.finditer(phrase, text, re.IGNORECASE))
            for match in matches:
                # Look ahead up to 3 non-empty lines (multiline support)
                start_pos = match.end()
                lines = text[start_pos:].split('\n')
                
                non_empty_lines = []
                for line in lines[:10]:
                    stripped = line.strip()
                    if stripped:
                        non_empty_lines.append(stripped)
                        if len(non_empty_lines) >= 3:
                            break
                
                # Check each line for the interval value
                for line in non_empty_lines:
                    # Extract single word (Monthly, Weekly, etc.)
                    word_match = re.search(r'\b([A-Z][a-z]+)\b', line)
                    if word_match:
                        word = word_match.group(1)
                        if word in ["Monthly", "Weekly", "Daily"]:
                            self.log(f"Found assessment_interval: {word}")
                            return word
                    
                    # Also check for duration format
                    duration_value = self._extract_duration_from_context(line)
                    if duration_value:
                        self.log(f"Found assessment_interval: {duration_value}")
                        return duration_value
        
        return None
    
    def extract_payment_period(self, text: str) -> Optional[str]:
        """Extract payment period - check Section 5 and Y(UK)2 clauses (Y(UK)2 overrides)."""
        # FIRST: Check Y(UK)2 clauses anywhere in document (overrides Section 5)
        yuk2_patterns = [
            r"Y\(UK\)2",
            r"Y\(UK\)\s*2",
            r"Y\(UK2\)",
            r"Y\(UK\)\s*2:",  # Handle colon after Y(UK)2
        ]
        
        yuk2_section = None
        for pattern in yuk2_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # Extract Y(UK)2 section (from match to next section or end)
                start_pos = match.start()
                # Find next section or end
                next_section = re.search(r'Section\s+\d+|Option\s+[A-Z]\d+', text[start_pos + 100:], re.IGNORECASE)
                if next_section:
                    end_pos = start_pos + 100 + next_section.start()
                else:
                    end_pos = len(text)
                yuk2_section = text[start_pos:end_pos]
                break
        
        # Extract from Y(UK)2 if found
        if yuk2_section:
            payment_label = r"The\s+period\s+for\s+payment\s+is"
            match = re.search(payment_label, yuk2_section, re.IGNORECASE)
            if match:
                # Look ahead up to 3 non-empty lines
                start_pos = match.end()
                lines = yuk2_section[start_pos:].split('\n')
                
                non_empty_lines = []
                for line in lines[:10]:
                    stripped = line.strip()
                    if stripped:
                        non_empty_lines.append(stripped)
                        if len(non_empty_lines) >= 3:
                            break
                
                for line in non_empty_lines:
                    # Extract duration
                    duration_value = self._extract_duration_from_context(line)
                    if duration_value:
                        # Normalize: "14 days after the date on which payment becomes due" → "14 days"
                        normalized = re.sub(r'\s+after.*$', '', duration_value, flags=re.IGNORECASE).strip()
                        self.log(f"Found payment_period from Y(UK)2: {normalized}")
                        return normalized
                    
                    # Check for "one week", "two weeks", etc.
                    word_match = re.search(r'\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+(week|weeks?|day|days?)\b', line, re.IGNORECASE)
                    if word_match:
                        normalized = word_match.group(0)
                        # Normalize: remove trailing text
                        normalized = re.sub(r'\s+after.*$', '', normalized, flags=re.IGNORECASE).strip()
                        self.log(f"Found payment_period from Y(UK)2: {normalized}")
                        return normalized
        
        # FALLBACK: Check Section 5
        section_5_patterns = [
            r"The\s+period\s+for\s+payment\s+is",
            r"period\s+for\s+payment\s+is",
            r"payment\s+period\s+is",
        ]
        
        for phrase in section_5_patterns:
            matches = list(re.finditer(phrase, text, re.IGNORECASE))
            for match in matches:
                # Look ahead up to 3 non-empty lines
                start_pos = match.end()
                lines = text[start_pos:].split('\n')
                
                non_empty_lines = []
                for line in lines[:10]:
                    stripped = line.strip()
                    if stripped:
                        non_empty_lines.append(stripped)
                        if len(non_empty_lines) >= 3:
                            break
                
                for line in non_empty_lines:
                    # Extract duration
                    duration_value = self._extract_duration_from_context(line)
                    if duration_value:
                        # Normalize: remove trailing text
                        normalized = re.sub(r'\s+after.*$', '', duration_value, flags=re.IGNORECASE).strip()
                        self.log(f"Found payment_period from Section 5: {normalized}")
                        return normalized
                    
                    # Check for "one week", "two weeks", etc.
                    word_match = re.search(r'\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+(week|weeks?|day|days?)\b', line, re.IGNORECASE)
                    if word_match:
                        normalized = word_match.group(0)
                        normalized = re.sub(r'\s+after.*$', '', normalized, flags=re.IGNORECASE).strip()
                        self.log(f"Found payment_period from Section 5: {normalized}")
                        return normalized
        
        return None
    
    def extract_retention_percentage(self, text: str) -> Optional[str]:
        """Extract retention percentage."""
        # Look for SPECIFIC label patterns that indicate retention percentage field exists
        # These patterns indicate the field is present in the contract (even if value is redacted)
        specific_label_patterns = [
            r"retention\s+percentage",
            r"retention.*percentage",
            r"The\s+retention\s+percentage\s+is",
            r"retention\s+percentage\s+is",
        ]
        
        found_specific_label = False
        for pattern in specific_label_patterns:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            if matches:
                found_specific_label = True
                for match in matches:
                    # Extract text around phrase (±200 chars)
                    start_pos = max(0, match.start() - 100)
                    end_pos = min(len(text), match.end() + 200)
                    context = text[start_pos:end_pos]
                    
                    # Extract percentage
                    percentage_value = self._extract_percentage_from_context(context)
                    if percentage_value:
                        self.log(f"Found retention_percentage: {percentage_value}")
                        return percentage_value
        
        # If specific label found but no value, it's redacted
        if found_specific_label:
            return "confidential"
        
        # If no specific label found, the field doesn't exist in the contract
        # Return None (will be converted to empty string in output)
        return None
    
    # WEATHER DATA (Section 6)
    
    def extract_weather_location(self, text: str) -> Optional[str]:
        """Extract weather location - anchor 'place where weather is to be recorded is' - extract next word."""
        REQUIRED_PHRASES = [
            r"place\s+where\s+weather\s+is\s+to\s+be\s+recorded\s+is",
        ]
        
        for phrase in REQUIRED_PHRASES:
            matches = list(re.finditer(phrase, text, re.IGNORECASE))
            for match in matches:
                # Extract text after phrase (up to 50 chars)
                start_pos = match.end()
                end_pos = min(len(text), start_pos + 50)
                context = text[start_pos:end_pos]
                
                # Extract next word (proper noun - capitalized)
                word_match = re.search(r'\b([A-Z][a-z]+)\b', context)
                if word_match:
                    location = word_match.group(1)
                    # Reject common words
                    if location.lower() not in ["the", "and", "or", "for", "with", "from", "is", "are", "to", "be", "recorded"]:
                        self.log(f"Found weather_location: {location}")
                        return location
        
        return None
    
    def extract_weather_measurement_type(self, text: str) -> Optional[List[str]]:
        """Extract weather measurement type - multiline measurement data as a list."""
        # Detect label line (handle typo "recorder" vs "recorded")
        label_patterns = [
            r"The\s+weather\s+measurements\s+to\s+be\s+recorder",  # Handle typo in contract
            r"The\s+weather\s+measurements\s+to\s+be\s+recorded",
            r"weather\s+measurements\s+to\s+be\s+recorder",
            r"weather\s+measurements\s+to\s+be\s+recorded",
        ]
        
        measurement_types = []
        for label_pattern in label_patterns:
            matches = list(re.finditer(label_pattern, text, re.IGNORECASE))
            for match in matches:
                # Capture ALL subsequent non-empty lines until:
                # - "The weather measurements are supplied by"
                # - OR another clause/section header
                start_pos = match.end()
                remaining_text = text[start_pos:]
                
                # Find stop markers
                stop_patterns = [
                    r"The\s+weather\s+measurements\s+are\s+supplied\s+by",
                    r"Section\s+\d+",
                    r"^\d+\s+[A-Z]",
                ]
                
                stop_pos = len(remaining_text)
                for stop_pattern in stop_patterns:
                    stop_match = re.search(stop_pattern, remaining_text, re.IGNORECASE | re.MULTILINE)
                    if stop_match:
                        stop_pos = min(stop_pos, stop_match.start())
                
                # Extract lines until stop marker
                context = remaining_text[:stop_pos]
                lines = context.split('\n')
                
                # Process each non-empty line
                for line in lines:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    
                    # Normalize: remove bullets, numbering, stray dots
                    normalized = re.sub(r'^[-•*]\s*', '', stripped)  # Remove bullets
                    normalized = re.sub(r'^\d+[\.\)]\s*', '', normalized)  # Remove numbering
                    normalized = re.sub(r'^\.+\s*', '', normalized)  # Remove stray dots
                    normalized = normalized.strip()
                    
                    # Ignore placeholders
                    if self._is_placeholder(normalized):
                        continue
                    
                    # Ignore if too short or just punctuation
                    if len(normalized) < 3:
                        continue
                    
                    # Ignore lines that are just numbers or table formatting
                    if re.match(r'^\d+$', normalized):
                        continue
                    
                    # CRITICAL: Filter out junk phrases
                    normalized_lower = normalized.lower()
                    junk_phrases = [
                        "for each calendar month are",
                        "hours gmt",
                        "and these measurements:",
                        "insert details",
                        "fastdraft",
                        "to be",
                        "not used"
                    ]
                    if any(junk in normalized_lower for junk in junk_phrases):
                        continue
                    
                    # Ignore if it's just a fragment (starts with lowercase and is short)
                    if len(normalized) < 10 and normalized[0].islower():
                        continue
                    
                    # Add to list if not already present
                    if normalized and normalized not in measurement_types:
                        measurement_types.append(normalized)
        
        return measurement_types if measurement_types else None
    
    def extract_weather_historical_source(self, text: str) -> Optional[str]:
        """Extract weather historical source - look for 'weather data are the records' or 'are available from'."""
        REQUIRED_PHRASES = [
            r"weather\s+data\s+are\s+the\s+records",
            r"are\s+available\s+from",
        ]
        
        for phrase in REQUIRED_PHRASES:
            matches = list(re.finditer(phrase, text, re.IGNORECASE))
            for match in matches:
                # Extract text after phrase (±200 chars)
                start_pos = match.end()
                end_pos = min(len(text), start_pos + 200)
                context = text[start_pos:end_pos]
                
                # Check for Met Office
                if re.search(r'met\s+office', context, re.IGNORECASE):
                    return "Met Office"
                
                # Extract source name (capitalized words)
                source_value = self._extract_source_from_context(context)
                if source_value:
                    self.log(f"Found weather_historical_source: {source_value}")
                    return source_value
        
        # Default to Met Office if mentioned anywhere
        if re.search(r'met\s+office', text, re.IGNORECASE):
            return "Met Office"
        
        return None
    
    # FINANCIAL/ADMINISTRATIVE FIELDS (Section 5 and General Contract Data)
    
    def extract_interest_rate(self, text: str) -> Optional[str]:
        """Extract interest rate - look for 'The interest rate is'."""
        label_patterns = [
            r'The\s+interest\s+rate\s+is',
            r'interest\s+rate\s+is',
            r'Interest\s+Rate\s+is',
        ]
        
        for pattern in label_patterns:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            for match in matches:
                start_pos = match.end()
                # Look ahead up to 5 lines
                lines = text[start_pos:].split('\n')
                for i, line in enumerate(lines[:5]):
                    line = line.strip()
                    if not line:
                        continue
                    # Look for percentage pattern: X.XX% or X%
                    percent_match = re.search(r'(\d+\.?\d*)\s*%', line)
                    if percent_match:
                        rate = percent_match.group(1)
                        if not self._is_placeholder(line):
                            self.log(f"Found interest_rate: {rate}%")
                            return f"{rate}%"
                    # Also check for "per annum" or "above the Base Bank of England"
                    if re.search(r'per\s+annum|above\s+the\s+Base', line, re.IGNORECASE):
                        # Extract number before "per annum"
                        num_match = re.search(r'(\d+\.?\d*)', line)
                        if num_match:
                            rate = num_match.group(1)
                            if not self._is_placeholder(line):
                                self.log(f"Found interest_rate: {rate}%")
                                return f"{rate}%"
        
        return None
    
    def extract_currency(self, text: str) -> Optional[str]:
        """Extract currency - look for 'The currency of the contract is'."""
        label_patterns = [
            r'The\s+currency\s+of\s+the\s+contract\s+is',
            r'currency\s+of\s+the\s+contract\s+is',
            r'Currency\s+of\s+the\s+contract\s+is',
        ]
        
        for pattern in label_patterns:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            for match in matches:
                start_pos = match.end()
                # Look ahead up to 3 lines
                lines = text[start_pos:].split('\n')
                for i, line in enumerate(lines[:3]):
                    line = line.strip()
                    if not line:
                        continue
                    # Check for currency mentions
                    if re.search(r'sterling|pound|£|gbp', line, re.IGNORECASE):
                        if 'sterling' in line.lower():
                            return "£ sterling"
                        elif 'pound' in line.lower():
                            return "£ sterling"
                        elif '£' in line:
                            return "£ sterling"
                    # Extract currency name if present
                    currency_match = re.search(r'the\s+([a-z\s]+)', line, re.IGNORECASE)
                    if currency_match:
                        currency = currency_match.group(1).strip()
                        if not self._is_placeholder(currency):
                            self.log(f"Found currency: {currency}")
                            return currency
        
        return None
    
    def extract_fee_percentage(self, text: str) -> Optional[str]:
        """Extract fee percentage - look for 'The fee percentage is'."""
        label_patterns = [
            r'The\s+fee\s+percentage\s+is',
            r'fee\s+percentage\s+is',
            r'Fee\s+percentage\s+is',
        ]
        
        for pattern in label_patterns:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            for match in matches:
                start_pos = match.end()
                # Look ahead up to 3 lines
                lines = text[start_pos:].split('\n')
                found_label = True
                for i, line in enumerate(lines[:3]):
                    line = line.strip()
                    if not line:
                        continue
                    # Look for percentage pattern
                    percent_match = re.search(r'(\d+\.?\d*)\s*%', line)
                    if percent_match:
                        fee = percent_match.group(1)
                        if not self._is_placeholder(line):
                            self.log(f"Found fee_percentage: {fee}%")
                            return f"{fee}%"
                
                # If label found but no valid value, likely redacted
                if found_label:
                    return "confidential"
        
        return None
    
    def extract_working_areas(self, text: str) -> Optional[str]:
        """Extract working areas - look for 'The working areas are'."""
        label_patterns = [
            r'The\s+working\s+areas\s+are',
            r'working\s+areas\s+are',
            r'Working\s+areas\s+are',
        ]
        
        # Stop patterns - if we hit these, we've gone too far
        stop_patterns = [
            r'The\s+key\s+persons\s+are',
            r'key\s+persons\s+are',
            r'^[0-9]+\s+',  # Section numbers
        ]
        
        for pattern in label_patterns:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            for match in matches:
                start_pos = match.end()
                # Look ahead up to 5 lines
                lines = text[start_pos:].split('\n')
                found_label = True
                for i, line in enumerate(lines[:5]):
                    line = line.strip()
                    if not line:
                        continue
                    # Stop if we hit another label
                    if any(re.search(stop, line, re.IGNORECASE) for stop in stop_patterns):
                        break
                    if not self._is_placeholder(line):
                        self.log(f"Found working_areas: {line}")
                        return line
                
                # If label found but no valid value, likely redacted
                if found_label:
                    return "confidential"
        
        return None
    
    def extract_key_persons(self, text: str) -> Optional[List[Dict[str, str]]]:
        """Extract key persons - look for 'The key persons are' and extract structured data."""
        label_patterns = [
            r'The\s+key\s+persons\s+are',
            r'key\s+persons\s+are',
            r'Key\s+persons\s+are',
        ]
        
        key_persons = []
        found_label = False
        current_person = {}  # Initialize outside loop to avoid UnboundLocalError
        
        for pattern in label_patterns:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            if matches:
                found_label = True
            for match in matches:
                start_pos = match.end()
                # Look ahead up to 50 lines (key persons can span multiple entries)
                lines = text[start_pos:start_pos + 2000].split('\n')
                
                # Reset current_person for each match
                current_person = {}
                for i, line in enumerate(lines[:50]):
                    line = line.strip()
                    if not line or self._is_placeholder(line):
                        continue
                    
                    # Look for structured fields: Name, Job, Responsibilities, Qualifications, Experience
                    if re.search(r'^Name\s*\(?\d+\)?', line, re.IGNORECASE):
                        # Save previous person if exists
                        if current_person.get('name'):
                            key_persons.append(current_person.copy())
                        current_person = {'name': ''}
                        # Extract name from next line
                        if i + 1 < len(lines):
                            name_line = lines[i + 1].strip()
                            if name_line and not self._is_placeholder(name_line):
                                current_person['name'] = name_line
                    elif re.search(r'^Job', line, re.IGNORECASE) and i + 1 < len(lines):
                        job_line = lines[i + 1].strip()
                        if job_line and not self._is_placeholder(job_line):
                            current_person['job'] = job_line
                    elif re.search(r'^Responsibilities', line, re.IGNORECASE) and i + 1 < len(lines):
                        resp_line = lines[i + 1].strip()
                        if resp_line and not self._is_placeholder(resp_line):
                            current_person['responsibilities'] = resp_line
                    elif re.search(r'^Qualifications', line, re.IGNORECASE) and i + 1 < len(lines):
                        qual_line = lines[i + 1].strip()
                        if qual_line and not self._is_placeholder(qual_line):
                            current_person['qualifications'] = qual_line
                    elif re.search(r'^Experience', line, re.IGNORECASE) and i + 1 < len(lines):
                        exp_line = lines[i + 1].strip()
                        if exp_line and not self._is_placeholder(exp_line):
                            current_person['experience'] = exp_line
                            # Save this person
                            if current_person.get('name'):
                                key_persons.append(current_person.copy())
                                current_person = {}
                
                # Save last person from this match if exists
                if current_person.get('name'):
                    key_persons.append(current_person.copy())
                    current_person = {}
        
        # No need to check current_person here since we save it after each match
        
        if key_persons:
            self.log(f"Found {len(key_persons)} key persons")
            return key_persons
        
        # If label found but no persons extracted, likely redacted
        if found_label:
            return "confidential"
        
        return None
    
    def extract_client_set_total(self, text: str) -> Optional[str]:
        """Extract client set total of the prices - look for 'The Client set total of the Prices is'."""
        label_patterns = [
            r'The\s+Client\s+set\s+total\s+of\s+the\s+Prices\s+is',
            r'Client\s+set\s+total\s+of\s+the\s+Prices\s+is',
            r'client\s+set\s+total\s+of\s+the\s+prices\s+is',
        ]
        
        # Stop patterns - if we hit these, we've gone too far
        stop_patterns = [
            r'The\s+interest\s+rate\s+is',
            r'interest\s+rate\s+is',
            r'^[0-9]+\s+',  # Section numbers
        ]
        
        for pattern in label_patterns:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            for match in matches:
                start_pos = match.end()
                # Look ahead up to 3 lines
                lines = text[start_pos:].split('\n')
                found_label = True
                for i, line in enumerate(lines[:3]):
                    line = line.strip()
                    if not line:
                        continue
                    # Stop if we hit another label
                    if any(re.search(stop, line, re.IGNORECASE) for stop in stop_patterns):
                        break
                    # Look for currency amount (prefer currency symbol)
                    currency_match = re.search(r'[£$€]\s*([\d,\.]+)', line)
                    if currency_match:
                        amount = currency_match.group(1)
                        if not self._is_placeholder(line):
                            self.log(f"Found client_set_total: £{amount}")
                            return f"£{amount}"
                    # Only check for number without currency if it's a large amount (likely a price)
                    # Skip small numbers like "2.00" which might be interest rates
                    num_match = re.search(r'([\d,\.]+)', line)
                    if num_match:
                        amount = num_match.group(1)
                        # Only accept if it looks like a price (has commas or is a large number)
                        if (',' in amount or float(amount.replace(',', '')) > 100) and not self._is_placeholder(line):
                            self.log(f"Found client_set_total: {amount}")
                            return amount
                
                # If label found but no valid value, likely redacted
                if found_label:
                    return "confidential"
        
        return None
    
    def extract_contractor_share(self, text: str) -> Optional[str]:
        """Extract contractor's share percentages - look for 'The Contractor's share percentages'."""
        label_patterns = [
            r"The\s+Contractor's\s+share\s+percentages",
            r"Contractor's\s+share\s+percentages",
            r"contractor's\s+share\s+percentages",
        ]
        
        for pattern in label_patterns:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            for match in matches:
                start_pos = match.end()
                # Look ahead up to 20 lines (share ranges can span multiple lines)
                lines = text[start_pos:start_pos + 1000].split('\n')
                share_info = []
                
                # Track if we found the label (to detect redaction)
                found_label = True
                
                for i, line in enumerate(lines[:20]):
                    line = line.strip()
                    if not line:
                        continue
                    if self._is_placeholder(line):
                        continue
                    
                    # Stop if we hit a section header (e.g., "6 Compensation events")
                    if re.search(r'^[0-9]+\s+[A-Z]', line):
                        break
                    
                    # Look for share range patterns with their percentages
                    # Pattern 1: "less than 80% 0%" - extract both the range and the percentage
                    if re.search(r'less\s+than\s+\d+\s*%', line, re.IGNORECASE):
                        # Try to find "less than X% Y%" pattern
                        match = re.search(r'less\s+than\s+(\d+)\s*%\s+(\d+)\s*%', line, re.IGNORECASE)
                        if match:
                            share_info.append(f"less than {match.group(1)}%: {match.group(2)}%")
                        else:
                            # Fallback: just extract "less than X% Y%"
                            match = re.search(r'less\s+than\s+\d+\s*%\s+\d+\s*%', line, re.IGNORECASE)
                            if match:
                                share_info.append(match.group(0).strip())
                    # Pattern 2: "from 80% to 120% as set out in Schedule 17"
                    elif re.search(r'from\s+\d+\s*%\s+to\s+\d+\s*%', line, re.IGNORECASE):
                        # Extract the full range with schedule reference
                        match = re.search(r'from\s+(\d+)\s*%\s+to\s+(\d+)\s*%(?:\s+as\s+set\s+out\s+in\s+Schedule\s+\d+)?', line, re.IGNORECASE)
                        if match:
                            schedule_part = ""
                            schedule_match = re.search(r'as\s+set\s+out\s+in\s+Schedule\s+\d+', line, re.IGNORECASE)
                            if schedule_match:
                                schedule_part = " " + schedule_match.group(0)
                            share_info.append(f"from {match.group(1)}% to {match.group(2)}%:{schedule_part}")
                    # Pattern 3: "greater than 120% as set out in Schedule 17"
                    elif re.search(r'greater\s+than\s+\d+\s*%', line, re.IGNORECASE):
                        # Extract the range and schedule reference
                        match = re.search(r'greater\s+than\s+(\d+)\s*%(?:\s+as\s+set\s+out\s+in\s+Schedule\s+\d+)?', line, re.IGNORECASE)
                        if match:
                            schedule_part = ""
                            schedule_match = re.search(r'as\s+set\s+out\s+in\s+Schedule\s+\d+', line, re.IGNORECASE)
                            if schedule_match:
                                schedule_part = " " + schedule_match.group(0)
                            share_info.append(f"greater than {match.group(1)}%:{schedule_part}")
                
                if share_info:
                    result = " | ".join(share_info)
                    self.log(f"Found contractor_share: {result}")
                    return result
                elif found_label:
                    # Label found but no data - likely redacted
                    return "confidential"
        
        return None
    
    def extract_retention_period(self, text: str) -> Optional[str]:
        """Extract retention period - look for 'The period for retention following Completion'."""
        label_patterns = [
            r'The\s+period\s+for\s+retention\s+following\s+Completion',
            r'period\s+for\s+retention\s+following\s+Completion',
            r'Period\s+for\s+retention',
        ]
        
        found_label = False
        for pattern in label_patterns:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            if matches:
                found_label = True
                for match in matches:
                    start_pos = match.end()
                    # Look ahead up to 5 lines
                    lines = text[start_pos:].split('\n')
                    for i, line in enumerate(lines[:5]):
                        line = line.strip()
                        if not line:
                            continue
                        # Look for duration pattern: X weeks/months/years
                        duration_match = re.search(r'(\d+)\s+(week|weeks|month|months|year|years)', line, re.IGNORECASE)
                        if duration_match:
                            duration = f"{duration_match.group(1)} {duration_match.group(2)}"
                            if not self._is_placeholder(line):
                                self.log(f"Found retention_period: {duration}")
                                return duration
        
        # If label found but no value, likely redacted
        if found_label:
            return "confidential"
        
        return None
    
    # Helper methods for extraction
    
    def _extract_date_from_context(self, context: str) -> Optional[str]:
        """Extract first valid date from context (DD Month YYYY format)."""
        # Pattern: DD Month YYYY
        pattern = r'\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b'
        match = re.search(pattern, context, re.IGNORECASE)
        if match:
            day = match.group(1)
            month = match.group(2).capitalize()
            year = match.group(3)
            return f"{day} {month} {year}"
        
        # Pattern: Month DD, YYYY
        pattern = r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b'
        match = re.search(pattern, context, re.IGNORECASE)
        if match:
            month = match.group(1).capitalize()
            day = match.group(2)
            year = match.group(3)
            return f"{day} {month} {year}"
        
        return None
    
    def _extract_all_dates_from_context(self, context: str) -> List[str]:
        """Extract all valid dates from context."""
        dates = []
        
        # Pattern: DD Month YYYY
        pattern = r'\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b'
        for match in re.finditer(pattern, context, re.IGNORECASE):
            day = match.group(1)
            month = match.group(2).capitalize()
            year = match.group(3)
            dates.append(f"{day} {month} {year}")
        
        # Pattern: Month DD, YYYY
        pattern = r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b'
        for match in re.finditer(pattern, context, re.IGNORECASE):
            month = match.group(1).capitalize()
            day = match.group(2)
            year = match.group(3)
            dates.append(f"{day} {month} {year}")
        
        return dates
    
    def _extract_duration_from_context(self, context: str) -> Optional[str]:
        """Extract duration (number + unit)."""
        # Pattern: X weeks/days/months
        pattern = r'\b(\d+)\s+(week|weeks|day|days|month|months)\b'
        match = re.search(pattern, context, re.IGNORECASE)
        if match:
            number = match.group(1)
            unit = match.group(2).lower()
            # Normalize to singular/plural
            if unit in ["week", "weeks"]:
                return f"{number} weeks" if int(number) != 1 else "1 week"
            elif unit in ["day", "days"]:
                return f"{number} days" if int(number) != 1 else "1 day"
            elif unit in ["month", "months"]:
                return f"{number} months" if int(number) != 1 else "1 month"
        
        return None
    
    def _extract_currency_from_context(self, context: str) -> Optional[str]:
        """Extract currency amount with unit."""
        # Pattern: £X per week/day/month
        pattern = r'[£$€]\s*([\d,]+(?:\.[\d]{2})?)\s+per\s+(day|week|month)'
        match = re.search(pattern, context, re.IGNORECASE)
        if match:
            amount = match.group(1)
            unit = match.group(2)
            return f"£{amount} per {unit}"
        
        # Pattern: X per week/day/month (without currency symbol)
        pattern = r'([\d,]+(?:\.[\d]{2})?)\s+per\s+(day|week|month)'
        match = re.search(pattern, context, re.IGNORECASE)
        if match:
            amount = match.group(1)
            unit = match.group(2)
            return f"£{amount} per {unit}"
        
        return None
    
    def _extract_percentage_from_context(self, context: str) -> Optional[str]:
        """Extract percentage value."""
        pattern = r'\b(\d+(?:\.\d+)?)%'
        match = re.search(pattern, context)
        if match:
            return match.group(1) + "%"
        return None
    
    def _extract_interval_from_context(self, context: str) -> Optional[str]:
        """Extract interval (duration or 'Monthly', 'Weekly', etc.)."""
        # Check for "Monthly", "Weekly", "Daily"
        if re.search(r'\b(Monthly|Weekly|Daily)\b', context, re.IGNORECASE):
            match = re.search(r'\b(Monthly|Weekly|Daily)\b', context, re.IGNORECASE)
            return match.group(1)
        
        # Check for duration
        duration = self._extract_duration_from_context(context)
        if duration:
            return duration
        
        return None
    
    def _extract_location_from_context(self, context: str) -> Optional[str]:
        """Extract location name (proper noun)."""
        # Pattern: Capitalized word(s) - proper noun
        # Reject common words
        reject_words = {"the", "and", "or", "for", "with", "from", "Met", "Office", "is", "are", "to", "be", "recorded"}
        
        # Look for capitalized words (proper nouns)
        pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b'
        matches = re.finditer(pattern, context)
        for match in matches:
            location = match.group(1).strip()
            # Reject if it's a common word or too short
            if location.lower() not in reject_words and len(location) > 2:
                # Reject if it contains numbers or special chars
                if re.match(r'^[A-Za-z\s]+$', location):
                    return location
        
        return None
    
    def _extract_measurement_type_from_context(self, context: str) -> Optional[str]:
        """Extract first measurement term (Rainfall, Wind, Temperature, etc.)."""
        # Look for measurement types
        if re.search(r'\brainfall\b', context, re.IGNORECASE):
            return "Rainfall"
        if re.search(r'\btemperature\b', context, re.IGNORECASE):
            return "Temperature"
        if re.search(r'\bwind\b', context, re.IGNORECASE):
            return "Wind"
        if re.search(r'\bsnowfall\b', context, re.IGNORECASE):
            return "Snowfall"
        if re.search(r'\bsunshine\b', context, re.IGNORECASE):
            return "Sunshine hours"
        
        return None
    
    def _extract_source_from_context(self, context: str) -> Optional[str]:
        """Extract source name."""
        # Check for Met Office
        if re.search(r'met\s+office', context, re.IGNORECASE):
            return "Met Office"
        
        # Look for capitalized words (proper noun)
        pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b'
        matches = re.finditer(pattern, context)
        for match in matches:
            source = match.group(1).strip()
            reject_words = {"the", "and", "or", "for", "with", "from", "is", "are", "to", "be", "available"}
            if source.lower() not in reject_words and len(source) > 2:
                if re.match(r'^[A-Za-z\s]+$', source):
                    return source
        
        return None
    
    def _is_placeholder(self, value: str) -> bool:
        """Check if value is a placeholder (TBC, insert date, none set, etc.)."""
        if not value:
            return True
        
        value_lower = value.strip().lower()
        placeholders = [
            "tbc", "tbd", "to be confirmed", "to be determined",
            "insert date", "insert details", "none set", "not set",
            "not stated", "not specified",
            "blank", "empty", "n/a", "na", "-", "...", "xxx",
            "fastdraft", "insert", "to be", "not used"
        ]
        
        # Check if value contains any placeholder
        if value_lower in placeholders:
            return True
        # Check if value starts with placeholder
        for placeholder in placeholders:
            if value_lower.startswith(placeholder):
                return True
        
        return False
    
    def extract_period_for_reply(self, text: str) -> Optional[str]:
        """Extract period for reply to a programme submission."""
        label_patterns = [
            r'Period\s+for\s+reply\s+to\s+a\s+programme\s+submission\s*:',
            r'period\s+for\s+reply\s+to\s+a\s+programme\s+submission\s*:',
            r'Period\s+for\s+reply\s+to\s+a\s+programme\s+submission',
            r'period\s+for\s+reply\s+to\s+a\s+programme\s+submission',
            r'Period\s+for\s+reply\s+to\s+programme',
            r'period\s+for\s+reply',
        ]
        
        for pattern in label_patterns:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            for match in matches:
                start_pos = match.end()
                # Look ahead up to 5 non-empty lines
                lines = text[start_pos:].split('\n')
                non_empty_lines = []
                for line in lines[:10]:
                    stripped = line.strip()
                    if stripped:
                        non_empty_lines.append(stripped)
                        if len(non_empty_lines) >= 5:
                            break
                
                for line in non_empty_lines:
                    # Extract duration
                    duration_value = self._extract_duration_from_context(line)
                    if duration_value:
                        if not self._is_placeholder(duration_value):
                            self.log(f"Found period_for_reply: {duration_value}")
                            return duration_value
        
        return None
    
    def extract_key_dates(self, text: str) -> Optional[List[Dict[str, str]]]:
        """Extract key dates - look for 'Key Date' patterns."""
        key_dates = []
        seen_ids = set()  # Track seen IDs to avoid duplicates
        
        # Pattern for "Key Date 1 (KD-01): Description"
        patterns = [
            r'Key\s+Date\s+(\d+)\s*\(KD-(\d+)\)\s*:\s*(.+?)(?=\n|Key\s+Date|$)',
            r'Key\s+Date\s+(\d+)\s*\(KD-(\d+)\)\s*(.+?)(?=\n|Key\s+Date|$)',
            r'Key\s+Date\s+(\d+)\s*:\s*(.+?)(?=\n|Key\s+Date|$)',
            r'KD-(\d+)\s*:\s*(.+?)(?=\n|KD-|Key\s+Date|$)',
        ]
        
        for pattern in patterns:
            matches = list(re.finditer(pattern, text, re.IGNORECASE | re.DOTALL))
            for match in matches:
                groups = match.groups()
                if len(groups) >= 2:
                    # Extract key date number and description
                    kd_number = groups[-2] if len(groups) >= 2 else groups[0]
                    description = groups[-1].strip()
                    
                    # Clean up description (remove leading colons, trailing punctuation, normalize whitespace)
                    description = re.sub(r'^:\s*', '', description)  # Remove leading colon
                    description = re.sub(r'[\.;:]+$', '', description)  # Remove trailing punctuation
                    description = re.sub(r'\s+', ' ', description).strip()  # Normalize whitespace
                    # Remove "from the" at the end if it's incomplete
                    description = re.sub(r'\s+from\s+the\s*$', '', description, flags=re.IGNORECASE)
                    
                    if description and not self._is_placeholder(description):
                        kd_id = f"KD-{kd_number.zfill(2)}"  # Ensure 2-digit format (KD-01, not KD-1)
                        
                        # Deduplicate by ID - keep the first (longest) description
                        if kd_id not in seen_ids:
                            seen_ids.add(kd_id)
                            key_date = {
                                "id": kd_id,
                                "description": description
                            }
                            key_dates.append(key_date)
                            self.log(f"Found key date: {key_date['id']} - {key_date['description']}")
                        else:
                            # If duplicate, check if this description is longer/better
                            existing_idx = next(i for i, kd in enumerate(key_dates) if kd["id"] == kd_id)
                            if len(description) > len(key_dates[existing_idx]["description"]):
                                key_dates[existing_idx]["description"] = description
                                self.log(f"Updated key date {kd_id} with longer description")
        
        if key_dates:
            return key_dates
        
        return None
