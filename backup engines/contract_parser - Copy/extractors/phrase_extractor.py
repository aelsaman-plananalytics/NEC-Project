"""
Phrase-Based Deterministic Extraction for NEC4 Contracts

Layer 1: Searches entire clean_text (no slicing) to locate values
by matching phrases and extracting numbers/dates/units.
"""

import re
from typing import Dict, List, Any, Optional, Tuple


class PhraseExtractor:
    """
    Phrase-based deterministic extractor.
    
    Searches the entire clean_text and extracts values by matching
    phrases and extracting numbers/dates/units that follow or precede them.
    """
    
    # Date patterns
    DATE_PATTERNS = [
        r'\b(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})\b',  # DD Month YYYY
        r'\b((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})\b',  # Month DD YYYY
        r'\b(\d{1,2}/\d{1,2}/\d{4})\b',  # DD/MM/YYYY
        r'\b(\d{1,2}-\d{1,2}-\d{4})\b',  # DD-MM-YYYY
        r'\b(\d{4}-\d{2}-\d{2})\b',  # YYYY-MM-DD
    ]
    
    # Duration patterns
    DURATION_PATTERNS = [
        r'(\d+)\s+(?:week|weeks|day|days|month|months)',
        r'(\d+)\s+weeks?\s+after',
    ]
    
    # Currency patterns
    CURRENCY_PATTERNS = [
        r'[£$€]\s*([\d,]+(?:\.[\d]{2})?)',
        r'([\d,]+(?:\.[\d]{2})?)\s*(?:per|a)\s*(?:day|week|month)',
    ]
    
    # Percentage patterns
    PERCENTAGE_PATTERNS = [
        r'(\d+(?:\.\d+)?)%',
    ]
    
    def __init__(self, debug: bool = False):
        """Initialize phrase extractor."""
        self.debug = debug
        self.compiled_date_patterns = [re.compile(p, re.IGNORECASE) for p in self.DATE_PATTERNS]
        self.compiled_duration_patterns = [re.compile(p, re.IGNORECASE) for p in self.DURATION_PATTERNS]
        self.compiled_currency_patterns = [re.compile(p, re.IGNORECASE) for p in self.CURRENCY_PATTERNS]
        self.compiled_percentage_patterns = [re.compile(p, re.IGNORECASE) for p in self.PERCENTAGE_PATTERNS]
    
    def log(self, msg: str):
        """Debug logging."""
        if self.debug:
            print(f"[PHRASE_EXTRACTOR] {msg}")
    
    def extract(self, clean_text: str) -> Dict[str, Any]:
        """
        Extract all fields from clean_text using phrase-based detection.
        
        Args:
            clean_text: Full clean text from PDF (no slicing)
            
        Returns:
            Dictionary with extracted field values
        """
        results = {}
        
        # Extract each field
        results["starting_date"] = self.extract_starting_date(clean_text)
        results["access_dates"] = self.extract_access_dates(clean_text)
        results["completion_date"] = self.extract_completion_date(clean_text)
        results["first_programme_submission"] = self.extract_first_programme_submission(clean_text)
        results["revised_programme_interval"] = self.extract_revised_programme_interval(clean_text)
        results["delay_damages"] = self.extract_delay_damages(clean_text)
        results["defects_date"] = self.extract_defects_date(clean_text)
        results["defect_correction_period"] = self.extract_defect_correction_period(clean_text)
        results["assessment_interval"] = self.extract_assessment_interval(clean_text)
        results["payment_period"] = self.extract_payment_period(clean_text)
        results["retention_percentage"] = self.extract_retention_percentage(clean_text)
        results["bond_amount"] = self.extract_bond_amount(clean_text)
        results["weather_location"] = self.extract_weather_location(clean_text)
        results["weather_measurement_type"] = self.extract_weather_measurement_type(clean_text)
        results["weather_historical_source"] = self.extract_weather_historical_source(clean_text)
        
        return results
    
    def extract_starting_date(self, text: str) -> str:
        """Extract starting date using phrase patterns."""
        # Phrase patterns (case-insensitive)
        phrases = [
            r"the\s+starting\s+date\s+is",
            r"starting\s+date",
            r"start\s+date",
        ]
        
        for phrase in phrases:
            match = re.search(phrase, text, re.IGNORECASE)
            if match:
                # Extract text after phrase (up to 200 chars)
                start_pos = match.end()
                context = text[start_pos:start_pos + 200]
                
                # Extract date using DATE_PATTERNS
                date_value = self.extract_date(context)
                if date_value:
                    self.log(f"Found starting_date: {date_value}")
                    return date_value
        
        return ""
    
    def extract_access_dates(self, text: str) -> str:
        """Extract access dates using phrase patterns."""
        # Phrase patterns (case-insensitive)
        phrases = [
            r"access\s+to\s+the\s+site\s+is",
            r"access\s+dates\s+are",
            r"access\s+date\s+is",
            r"the\s+site\s+is\s+available\s+from",
        ]
        
        all_dates = []
        for phrase in phrases:
            match = re.search(phrase, text, re.IGNORECASE)
            if match:
                # Extract text after phrase (up to 300 chars for multiple dates)
                start_pos = match.end()
                context = text[start_pos:start_pos + 300]
                
                # Extract ALL dates in context
                dates = self.extract_all_dates(context)
                all_dates.extend(dates)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_dates = []
        for d in all_dates:
            if d not in seen:
                seen.add(d)
                unique_dates.append(d)
        
        if unique_dates:
            self.log(f"Found access_dates: {unique_dates}")
            return ", ".join(unique_dates)
        
        return ""
    
    def extract_completion_date(self, text: str) -> str:
        """Extract completion date using phrase patterns."""
        # Phrase patterns (case-insensitive)
        phrases = [
            r"the\s+completion\s+date\s+for\s+the\s+whole\s+of\s+the\s+works\s+is",
            r"completion\s+date\s+is",
            r"completion\s+is\s+due\s+on",
        ]
        
        for phrase in phrases:
            match = re.search(phrase, text, re.IGNORECASE)
            if match:
                # Extract text after phrase (up to 200 chars)
                start_pos = match.end()
                context = text[start_pos:start_pos + 200]
                
                # Try date first
                date_value = self.extract_date(context)
                if date_value:
                    self.log(f"Found completion_date: {date_value}")
                    return date_value
                
                # Try duration (e.g., "52 weeks after Completion")
                duration_value = self.extract_duration(context)
                if duration_value:
                    self.log(f"Found completion_date (duration): {duration_value}")
                    return duration_value
        
        return ""
    
    def extract_first_programme_submission(self, text: str) -> str:
        """Extract first programme submission using phrase patterns."""
        # Phrase patterns (case-insensitive)
        phrases = [
            r"the\s+period\s+after\s+the\s+contract\s+date\s+within\s+which\s+the\s+contractor\s+is\s+to\s+submit\s+a\s+first\s+programme",
            r"submit\s+a\s+first\s+programme",
            r"first\s+programme",
        ]
        
        for phrase in phrases:
            match = re.search(phrase, text, re.IGNORECASE)
            if match:
                # Extract text after phrase (up to 100 chars)
                start_pos = match.end()
                context = text[start_pos:start_pos + 100]
                
                duration_value = self.extract_duration(context)
                if duration_value:
                    self.log(f"Found first_programme_submission: {duration_value}")
                    return duration_value
        
        return ""
    
    def extract_revised_programme_interval(self, text: str) -> str:
        """Extract revised programme interval using phrase patterns."""
        # Phrase patterns (case-insensitive)
        phrases = [
            r"revised\s+programmes\s+at",
            r"the\s+contractor\s+submits\s+revised\s+programmes",
            r"interval\s+for\s+revised\s+programmes",
        ]
        
        for phrase in phrases:
            match = re.search(phrase, text, re.IGNORECASE)
            if match:
                # Extract text after phrase (up to 100 chars)
                start_pos = match.end()
                context = text[start_pos:start_pos + 100]
                
                duration_value = self.extract_duration(context)
                if duration_value:
                    self.log(f"Found revised_programme_interval: {duration_value}")
                    return duration_value
        
        return ""
    
    def extract_delay_damages(self, text: str) -> str:
        """Extract delay damages (X7) - ONLY inside Option X7 block."""
        # RULE: Look ONLY inside Option X7 block
        # First, find Option X7 section boundaries
        x7_start_pattern = r"option\s+x7|secondary\s+option\s+x7"
        x7_start_match = re.search(x7_start_pattern, text, re.IGNORECASE)
        
        if not x7_start_match:
            return "not included"
        
        # Find end of X7 section (next section header or end of text)
        x7_start_pos = x7_start_match.start()
        # Look for next section (Option X8, Section, etc.)
        next_section_pattern = r"(?:option\s+x\d+|section\s+\d+|part\s+\w+)"
        next_section_match = re.search(next_section_pattern, text[x7_start_pos + 100:], re.IGNORECASE)
        
        if next_section_match:
            x7_end_pos = x7_start_pos + 100 + next_section_match.start()
        else:
            x7_end_pos = len(text)
        
        # Extract X7 section text
        x7_section_text = text[x7_start_pos:x7_end_pos]
        
        # Now search for delay damages phrases ONLY within X7 section
        phrases = [
            r"delay\s+damages\s+are",
            r"delay\s+damages",
            r"rate\s+of\s+delay\s+damages",
        ]
        
        for phrase in phrases:
            match = re.search(phrase, x7_section_text, re.IGNORECASE)
            if match:
                # Extract text after phrase (up to 200 chars)
                start_pos = match.end()
                context = x7_section_text[start_pos:start_pos + 200]
                
                # Check for redacted values
                if re.search(r'[█#\*]{3,}|\[REDACTED\]|redacted', context, re.IGNORECASE):
                    return "Not specified (redacted)"
                
                # Extract currency
                currency_value = self.extract_currency_with_unit(context)
                if currency_value:
                    self.log(f"Found delay_damages: {currency_value}")
                    return currency_value
        
        # If X7 exists but no numeric value found
        return "Not specified (redacted)"
    
    def extract_defects_date(self, text: str) -> str:
        """Extract defects date using phrase patterns."""
        # Phrase pattern (case-insensitive)
        phrase = r"the\s+period\s+between\s+completion\s+.*?\s+and\s+the\s+defects\s+date\s+is"
        
        match = re.search(phrase, text, re.IGNORECASE)
        if match:
            # Extract text after phrase (up to 200 chars)
            start_pos = match.end()
            context = text[start_pos:start_pos + 200]
            
            # Try duration first (e.g., "52 weeks after Completion")
            duration_value = self.extract_duration(context)
            if duration_value:
                self.log(f"Found defects_date: {duration_value}")
                return duration_value
            
            # Try date
            date_value = self.extract_date(context)
            if date_value:
                self.log(f"Found defects_date: {date_value}")
                return date_value
        
        return ""
    
    def extract_defect_correction_period(self, text: str) -> str:
        """Extract defect correction period using phrase patterns."""
        # Phrase patterns (case-insensitive)
        phrases = [
            r"the\s+defect\s+correction\s+period\s+is",
            r"correction\s+period\s+is",
        ]
        
        for phrase in phrases:
            match = re.search(phrase, text, re.IGNORECASE)
            if match:
                # Extract text after phrase (up to 100 chars)
                start_pos = match.end()
                context = text[start_pos:start_pos + 100]
                
                duration_value = self.extract_duration(context)
                if duration_value:
                    self.log(f"Found defect_correction_period: {duration_value}")
                    return duration_value
        
        return ""
    
    def extract_assessment_interval(self, text: str) -> str:
        """Extract assessment interval using phrase patterns (Section 5 - Payments)."""
        # Phrase patterns (case-insensitive)
        phrases = [
            r"assessment\s+interval",
            r"assessment\s+date",
        ]
        
        for phrase in phrases:
            match = re.search(phrase, text, re.IGNORECASE)
            if match:
                # Extract text after phrase (up to 100 chars)
                start_pos = match.end()
                context = text[start_pos:start_pos + 100]
                
                # Try duration first
                duration_value = self.extract_duration(context)
                if duration_value:
                    self.log(f"Found assessment_interval: {duration_value}")
                    return duration_value
        
        return ""
    
    def extract_payment_period(self, text: str) -> str:
        """Extract payment period using phrase patterns (Section 5 - Payments)."""
        # Phrase patterns (case-insensitive)
        phrases = [
            r"payment\s+is\s+made",
            r"payment\s+interval",
        ]
        
        for phrase in phrases:
            match = re.search(phrase, text, re.IGNORECASE)
            if match:
                # Extract text after phrase (up to 100 chars)
                start_pos = match.end()
                context = text[start_pos:start_pos + 100]
                
                duration_value = self.extract_duration(context)
                if duration_value:
                    self.log(f"Found payment_period: {duration_value}")
                    return duration_value
        
        return ""
    
    def extract_retention_percentage(self, text: str) -> str:
        """Extract retention using phrase patterns (Section 5 - Payments)."""
        # Phrase pattern (case-insensitive)
        phrase = r"retention"
        
        match = re.search(phrase, text, re.IGNORECASE)
        if match:
            # Extract text after phrase (up to 100 chars)
            start_pos = match.end()
            context = text[start_pos:start_pos + 100]
            
            # Try percentage first
            percentage_value = self.extract_percentage(context)
            if percentage_value:
                self.log(f"Found retention_percentage: {percentage_value}")
                return percentage_value
        
        return ""
    
    def extract_bond_amount(self, text: str) -> str:
        """Extract bond amount."""
        patterns = [
            r"bond",
            r"performance\s+bond",
            r"amount\s+of\s+bond",
        ]
        
        for pattern in patterns:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            for match in matches:
                # Search ±100 chars around match
                start_pos = max(0, match.start() - 100)
                end_pos = min(len(text), match.end() + 100)
                context = text[start_pos:end_pos]
                
                currency_value = self.extract_currency(context)
                if currency_value:
                    self.log(f"Found bond_amount: {currency_value}")
                    return currency_value
        
        return ""
    
    def extract_weather_location(self, text: str) -> str:
        """Extract weather recording location using phrase patterns (Section 6 - Compensation events)."""
        # Phrase pattern (case-insensitive)
        phrase = r"the\s+place\s+where\s+weather\s+is\s+to\s+be\s+recorded\s+is"
        
        match = re.search(phrase, text, re.IGNORECASE)
        if match:
            # Extract text after phrase (up to 100 chars)
            start_pos = match.end()
            context = text[start_pos:start_pos + 100]
            
            # Extract location name (capitalized words)
            location_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', context)
            if location_match:
                location = location_match.group(1).strip()
                if location.lower() not in ["the", "and", "or", "for", "with", "from", "Met", "Office"]:
                    self.log(f"Found weather_location: {location}")
                    return location
        
        return ""
    
    def extract_weather_measurement_type(self, text: str) -> str:
        """Extract weather measurement type using phrase patterns (Section 6 - Compensation events)."""
        # Phrase pattern (case-insensitive)
        phrase = r"the\s+weather\s+measurements\s+to\s+be\s+recorded\s+are"
        
        match = re.search(phrase, text, re.IGNORECASE)
        if match:
            # Extract text after phrase (up to 500 chars for list items)
            start_pos = match.end()
            context = text[start_pos:start_pos + 500]
            
            # Extract list items (beginning with "•" or tokens ending with "mm", "°C", "days")
            measurements = []
            
            # Look for bullet points
            bullet_items = re.findall(r'[•\-\*]\s*([^\n]+)', context)
            for item in bullet_items:
                item_clean = item.strip()
                if item_clean:
                    measurements.append(item_clean)
            
            # Look for tokens ending with "mm", "°C", "days"
            measurement_tokens = re.findall(r'\b([^\s,]+(?:mm|°C|days?))\b', context, re.IGNORECASE)
            measurements.extend(measurement_tokens)
            
            # Also look for common measurement phrases
            if re.search(r'cumulative\s+rainfall', context, re.IGNORECASE):
                measurements.append("cumulative rainfall")
            if re.search(r'average\s+air\s+temperature', context, re.IGNORECASE):
                measurements.append("average air temperature")
            if re.search(r'wind\s+speed', context, re.IGNORECASE):
                measurements.append("wind speed")
            
            if measurements:
                # Remove duplicates
                unique_measurements = []
                seen = set()
                for m in measurements:
                    m_lower = m.lower()
                    if m_lower not in seen:
                        seen.add(m_lower)
                        unique_measurements.append(m)
                
                if unique_measurements:
                    self.log(f"Found weather_measurement_type: {unique_measurements}")
                    return ", ".join(unique_measurements)
        
        return ""
    
    def extract_weather_historical_source(self, text: str) -> str:
        """Extract weather historical source using phrase patterns (Section 6 - Compensation events)."""
        # Phrase pattern (case-insensitive)
        phrase = r"historical\s+records\s+are\s+supplied\s+by"
        
        match = re.search(phrase, text, re.IGNORECASE)
        if match:
            # Extract text after phrase (up to 100 chars)
            start_pos = match.end()
            context = text[start_pos:start_pos + 100]
            
            # Extract source name (capitalized words)
            source_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', context)
            if source_match:
                source = source_match.group(1).strip()
                if source.lower() not in ["the", "and", "or", "for", "with", "from"]:
                    self.log(f"Found weather_historical_source: {source}")
                    return source
        
        # Default to Met Office if mentioned anywhere
        if re.search(r'met\s+office', text, re.IGNORECASE):
            return "Met Office"
        
        return ""
    
    # Helper methods
    
    def extract_date(self, text: str) -> str:
        """Extract first valid date from text."""
        for pattern in self.compiled_date_patterns:
            match = pattern.search(text)
            if match:
                return match.group(1).strip()
        return ""
    
    def extract_all_dates(self, text: str) -> List[str]:
        """Extract all dates from text."""
        dates = []
        for pattern in self.compiled_date_patterns:
            matches = pattern.findall(text)
            dates.extend([m if isinstance(m, str) else m[0] for m in matches])
        return dates
    
    def extract_duration(self, text: str) -> str:
        """Extract duration (number + unit)."""
        for pattern in self.compiled_duration_patterns:
            match = pattern.search(text)
            if match:
                return match.group(0).strip()
        return ""
    
    def extract_currency(self, text: str) -> str:
        """Extract currency amount."""
        for pattern in self.compiled_currency_patterns:
            match = pattern.search(text)
            if match:
                amount = match.group(1) if match.lastindex else match.group(0)
                # Add currency symbol if missing
                if not amount.startswith(('£', '$', '€')):
                    return f"£{amount}"
                return amount
        return ""
    
    def extract_currency_with_unit(self, text: str) -> str:
        """Extract currency amount with unit (e.g., '£25,000 per week')."""
        # Look for pattern: currency + "per" + unit
        pattern = r'([£$€]?\s*[\d,]+(?:\.[\d]{2})?)\s+per\s+(day|week|month)'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            amount = match.group(1).strip()
            unit = match.group(2).strip()
            if not amount.startswith(('£', '$', '€')):
                return f"£{amount} per {unit}"
            return f"{amount} per {unit}"
        return ""
    
    def extract_percentage(self, text: str) -> str:
        """Extract percentage value."""
        for pattern in self.compiled_percentage_patterns:
            match = pattern.search(text)
            if match:
                return match.group(1) + "%"
        return ""
