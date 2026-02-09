"""
NEC Value Extractor Layer (Option B).

Extracts literal values (dates, durations, amounts, etc.) from raw NEC contract text.
Never returns clause numbers or unrelated text.

Philosophy:
- Takes raw extracted text block
- Returns ONLY the meaningful value
- Uses deterministic regex patterns
- Never hallucinates or invents values
"""

import re
from typing import Dict, List, Any, Optional


class NECValueExtractor:
    """
    Extracts literal values from NEC contract text blocks.
    
    Removes clause numbers, extracts dates, durations, amounts, and other
    programme-critical values using deterministic regex patterns.
    """
    
    # Date patterns (NEC4 style)
    DATE_PATTERNS = [
        r'\d{1,2}\s+\w+\s+\d{4}',  # 14 October 2024, 1 March 2026
        r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',  # 14/10/2024, 14-10-2024
        r'\w+\s+\d{4}',  # October 2024, March 2026
        r'\d{1,2}\s+\w+',  # 14 October (if year is elsewhere)
    ]
    
    # Duration patterns
    DURATION_PATTERNS = [
        r'\d+\s+weeks?\s+(?:after|before|from)',  # 52 weeks after Completion
        r'\d+\s+weeks?',  # 4 weeks, 2 weeks
        r'\d+\s+days?',  # 14 days, 2 days
        r'\d+\s+months?',  # 6 months, 12 months
    ]
    
    # Currency amount patterns
    CURRENCY_PATTERNS = [
        r'[£$€]\s*\d[\d,\.]*\s*(?:per|a)\s*(?:day|week|month)',  # £250,000 per week
        r'[£$€]\s*\d[\d,\.]*',  # £10,000, £250k
        r'\d[\d,\.]*\s*(?:per|a)\s*(?:day|week|month)',  # 250,000 per week
    ]
    
    # Percentage patterns
    PERCENTAGE_PATTERNS = [
        r'\d+%',  # 3%, 5%
        r'\d+\s+percent',  # 3 percent
    ]
    
    # Time interval patterns
    TIME_INTERVAL_PATTERNS = [
        r'within\s+\d+\s+weeks?',  # within 4 weeks
        r'every\s+\d+\s+weeks?',  # every 4 weeks
        r'at\s+intervals\s+no\s+longer\s+than\s+\d+\s+weeks?',  # at intervals no longer than 4 weeks
    ]
    
    def __init__(self, debug: bool = False):
        """Initialize NEC value extractor."""
        self.debug = debug
        
        # Compile patterns
        self.compiled_date_patterns = [re.compile(p, re.IGNORECASE) for p in self.DATE_PATTERNS]
        self.compiled_duration_patterns = [re.compile(p, re.IGNORECASE) for p in self.DURATION_PATTERNS]
        self.compiled_currency_patterns = [re.compile(p, re.IGNORECASE) for p in self.CURRENCY_PATTERNS]
        self.compiled_percentage_patterns = [re.compile(p, re.IGNORECASE) for p in self.PERCENTAGE_PATTERNS]
        self.compiled_time_interval_patterns = [re.compile(p, re.IGNORECASE) for p in self.TIME_INTERVAL_PATTERNS]
    
    def log(self, msg: str):
        """Log debug message."""
        if self.debug:
            print(f"[NECValueExtractor] {msg}")
    
    def extract(self, field_name: str, text_block: str) -> str:
        """
        Extract literal value from text block for a specific field.
        
        Args:
            field_name: Name of field (e.g., "starting_date", "completion_date")
            text_block: Raw text block containing the field
            
        Returns:
            Literal value only (date, number, duration, etc.) or empty string
        """
        if not text_block or not text_block.strip():
            return ""
        
        # Clean text block
        cleaned = self._clean_text_block(text_block)
        
        # Field-specific extraction
        if field_name in ["starting_date", "completion_date", "access_date", "defects_date"]:
            return self._extract_date(cleaned, field_name)
        elif field_name in ["first_programme_submission", "revised_programme_interval"]:
            return self._extract_time_interval(cleaned, field_name)
        elif field_name in ["delay_damages", "delay_damages_amount"]:
            return self._extract_currency_amount(cleaned, field_name)
        elif field_name in ["defect_correction_period", "defects_period"]:
            return self._extract_duration(cleaned, field_name)
        elif field_name in ["retention_percentage", "retention"]:
            return self._extract_percentage(cleaned, field_name)
        elif field_name in ["assessment_interval", "payment_period"]:
            return self._extract_time_interval(cleaned, field_name)
        elif field_name in ["bond_amount", "bond"]:
            return self._extract_currency_amount(cleaned, field_name)
        elif field_name in ["weather_location", "weather_measurement_location"]:
            return self._extract_weather_location(cleaned)
        elif field_name in ["weather_measurement_type", "weather_measurements"]:
            return self._extract_weather_measurement_type(cleaned)
        elif field_name in ["weather_historical_source", "weather_source"]:
            return self._extract_weather_source(cleaned)
        else:
            # Generic extraction: try date, then duration, then currency
            value = self._extract_date(cleaned, field_name)
            if value:
                return value
            
            value = self._extract_duration(cleaned, field_name)
            if value:
                return value
            
            value = self._extract_currency_amount(cleaned, field_name)
            if value:
                return value
            
            return ""
    
    def _clean_text_block(self, text: str) -> str:
        """
        Clean text block by removing clause numbers and noise.
        
        Args:
            text: Raw text block
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        # Remove PDF artifacts
        text = re.sub(r'\(cid:\d+\)', '', text)
        
        # Remove clause numbers (e.g., "60.1", "21.3", "3.1")
        text = re.sub(r'\b\d+\.\d+\b', '', text)
        
        # Remove section numbers at start of line
        text = re.sub(r'^\s*\d+\.\d+\s+', '', text, flags=re.MULTILINE)
        
        # Remove TOC leaders
        text = re.sub(r'\.{3,}', '', text)
        
        # Remove page numbers
        text = re.sub(r'\bPage\s+\d+\b', '', text, flags=re.IGNORECASE)
        
        # Collapse whitespace
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    def _extract_date(self, text: str, field_name: str) -> str:
        """Extract date value from text."""
        # Try to find date near field-specific keywords
        if field_name == "starting_date":
            # Look for date after "Starting Date" or "Start Date"
            match = re.search(r'(?:Starting\s+Date|Start\s+Date)[^\d]*(\d{1,2}\s+\w+\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        elif field_name == "completion_date":
            # Look for date after "Completion Date" or "Completion of the whole of the works"
            match = re.search(r'(?:Completion\s+Date|Completion\s+of\s+the\s+whole)[^\d]*(\d{1,2}\s+\w+\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        elif field_name == "access_date":
            # Look for date after "Access Date" or "Access to the Site"
            match = re.search(r'(?:Access\s+Date|Access\s+to\s+the\s+Site)[^\d]*(\d{1,2}\s+\w+\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        elif field_name == "defects_date":
            # Look for date or duration after "Defects Date"
            match = re.search(r'Defects\s+Date[^\d]*(\d{1,2}\s+\w+\s+\d{4}|\d+\s+weeks?\s+after)', text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # Fallback: find first date pattern in text
        for pattern in self.compiled_date_patterns:
            match = pattern.search(text)
            if match:
                date_value = match.group(0).strip()
                # Validate it's not a clause number
                if not re.match(r'^\d+\.\d+$', date_value):
                    return date_value
        
        return ""
    
    def _extract_duration(self, text: str, field_name: str) -> str:
        """Extract duration value (weeks, days, months)."""
        # Try to find duration near field-specific keywords
        if field_name in ["defect_correction_period", "defects_period"]:
            # Look for duration after "defect correction period" or "defects period"
            match = re.search(r'(?:defect\s+correction\s+period|defects\s+period)[^\d]*(\d+\s+weeks?|\d+\s+days?|\d+\s+months?)', text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # Fallback: find first duration pattern
        for pattern in self.compiled_duration_patterns:
            match = pattern.search(text)
            if match:
                return match.group(0).strip()
        
        return ""
    
    def _extract_time_interval(self, text: str, field_name: str) -> str:
        """Extract time interval (within X weeks, every X weeks)."""
        # Try field-specific patterns
        if field_name == "first_programme_submission":
            # Look for "within X weeks" after "first programme" or "submit"
            match = re.search(r'(?:first\s+programme|submit)[^\d]*(within\s+\d+\s+weeks?|\d+\s+weeks?)', text, re.IGNORECASE)
            if match:
                interval = match.group(1).strip()
                if not interval.startswith("within"):
                    interval = f"within {interval}"
                return interval
        
        elif field_name == "revised_programme_interval":
            # Look for "every X weeks" or "at intervals no longer than X weeks"
            match = re.search(r'(?:revised\s+programme|interval)[^\d]*(every\s+\d+\s+weeks?|at\s+intervals\s+no\s+longer\s+than\s+\d+\s+weeks?|\d+\s+weeks?)', text, re.IGNORECASE)
            if match:
                interval = match.group(1).strip()
                if not any(interval.startswith(prefix) for prefix in ["every", "at intervals"]):
                    interval = f"every {interval}"
                return interval
        
        elif field_name in ["assessment_interval", "payment_period"]:
            # Look for duration after field name
            match = re.search(rf'{field_name.replace("_", " ")}[^\d]*(\d+\s+weeks?|\d+\s+days?)', text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # Fallback: find first time interval pattern
        for pattern in self.compiled_time_interval_patterns:
            match = pattern.search(text)
            if match:
                return match.group(0).strip()
        
        return ""
    
    def _extract_currency_amount(self, text: str, field_name: str) -> str:
        """Extract currency amount (with or without per time unit)."""
        # Try field-specific patterns
        if field_name in ["delay_damages", "delay_damages_amount"]:
            # Look for currency amount with "per day/week/month"
            match = re.search(r'([£$€]\s*\d[\d,\.]*)\s*(per|a)\s*(day|week|month)', text, re.IGNORECASE)
            if match:
                return f"{match.group(1).strip()} per {match.group(3).strip()}"
            
            # Fallback: just currency amount
            match = re.search(r'([£$€]\s*\d[\d,\.]*)', text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        elif field_name in ["bond_amount", "bond"]:
            # Look for currency amount after "bond" or "performance bond"
            match = re.search(r'(?:bond|performance\s+bond)[^\d£$€]*([£$€]\s*\d[\d,\.]*)', text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # Fallback: find first currency pattern
        for pattern in self.compiled_currency_patterns:
            match = pattern.search(text)
            if match:
                return match.group(0).strip()
        
        return ""
    
    def _extract_percentage(self, text: str, field_name: str) -> str:
        """Extract percentage value."""
        # Look for percentage after "retention"
        if field_name in ["retention_percentage", "retention"]:
            match = re.search(r'retention[^\d]*(\d+%)', text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # Fallback: find first percentage pattern
        for pattern in self.compiled_percentage_patterns:
            match = pattern.search(text)
            if match:
                return match.group(0).strip()
        
        return ""
    
    def _extract_weather_location(self, text: str) -> str:
        """Extract weather measurement location."""
        # Look for location after "place where weather" or "recorded at"
        match = re.search(r'(?:place\s+where\s+weather|recorded\s+at|taken\s+at)[^\n]*?([A-Z][A-Za-z\s]+(?:Station|Office|Agency|Site))', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        # Look for "Met Office" or similar
        match = re.search(r'(Met\s+Office|Environment\s+Agency|Weather\s+Station)', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        return ""
    
    def _extract_weather_measurement_type(self, text: str) -> str:
        """Extract weather measurement type."""
        # Look for measurement types
        measurement_types = ["rainfall", "temperature", "snow", "wind speed", "wind", "precipitation"]
        
        for mtype in measurement_types:
            if re.search(rf'\b{mtype}\b', text, re.IGNORECASE):
                return mtype.capitalize()
        
        # Look for "weather measurements are"
        match = re.search(r'weather\s+measurements\s+are\s+([^\n\.]+)', text, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            # Extract first meaningful word
            words = value.split()
            if words:
                return words[0].capitalize()
        
        return ""
    
    def _extract_weather_source(self, text: str) -> str:
        """Extract historical weather records source."""
        # Look for "Met Office" or "historical records"
        match = re.search(r'(Met\s+Office|Environment\s+Agency|historical\s+records\s+from\s+([A-Z][A-Za-z\s]+))', text, re.IGNORECASE)
        if match:
            return match.group(1).strip() if match.group(1) else match.group(2).strip()
        
        # Look for "weather data are the records of"
        match = re.search(r'weather\s+data\s+are\s+the\s+records\s+of\s+the\s+([A-Z][A-Za-z\s]+)', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        return ""
    
    def extract_key_dates(self, text_block: str) -> List[Dict[str, Any]]:
        """
        Extract Key Dates from text block.
        
        Args:
            text_block: Text containing Key Dates section
            
        Returns:
            List of key date dictionaries: [{"key_date": "KD-01", "description": "...", "date": "..."}, ...]
        """
        key_dates = []
        
        # Split into lines
        lines = text_block.split('\n')
        
        for i, line in enumerate(lines):
            # Look for Key Date identifier
            kd_match = re.search(r'KD[-–]?\s*(\d+)', line, re.IGNORECASE)
            if kd_match:
                kd_id = kd_match.group(1)
                kd_key = f"KD-{kd_id}"
                
                # Get description from current or next line
                description = ""
                date = ""
                
                # Check current line for description
                if len(line) > len(kd_match.group(0)):
                    remaining = line[kd_match.end():].strip()
                    if remaining:
                        description = remaining
                
                # Check next line if description is empty
                if not description and i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line and not re.search(r'KD[-–]?\s*\d+', next_line, re.IGNORECASE):
                        description = next_line
                
                # Extract date from description
                if description:
                    # Try to find date in description
                    for date_pattern in self.compiled_date_patterns:
                        date_match = date_pattern.search(description)
                        if date_match:
                            date = date_match.group(0).strip()
                            description = description.replace(date, "").strip()
                            break
                    
                    # Clean description
                    description = self._clean_text_block(description)
                    
                    if description:
                        key_date = {
                            "key_date": kd_key,
                            "description": description,
                            "date": date
                        }
                        key_dates.append(key_date)
                        self.log(f"Extracted key_date: {kd_key} - {description}")
        
        return key_dates
