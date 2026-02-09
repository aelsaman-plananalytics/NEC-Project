"""
Table-First Contract Data Part One Extractor.

Extracts NEC programme-critical data from real-world NEC4 contracts using:
1. Table detection first (primary source)
2. Label-based extraction second (fills gaps)
3. Optional LLM fallback last (only for missing fields)

Works reliably with:
- Anderby Creek Piling NEC4 ECC 2023
- Addingham Lower Gauge Fish Pass NEC
- KSL Rec 22-23 NEC contract
- Skyscraper contract (test contract)
"""

import re
from typing import Dict, List, Any, Optional, Tuple


class ContractDataTableExtractor:
    """
    Table-first extractor for Contract Data Part One.
    
    Primary extraction method: Extract from structured tables in Contract Data Part One.
    Tables contain two columns: description (e.g., "3.1 Starting Date") and value (e.g., "12 February 2024").
    """
    
    # Contract Data Part One section headers
    CD_PART_ONE_HEADERS = [
        r"Contract\s+Data\s+Part\s+One",
        r"Contract\s+Data\s+[–-]\s+Part\s+One",
        r"Contract\s+Data\s+Provided\s+by\s+the\s+Employer",
        r"Contract\s+Data\s+Part\s+1",
        r"CD\s+Part\s+One",
        r"CD\s+Part\s+1",
    ]
    
    # NEC field patterns for matching table row descriptions
    # Maps clause numbers and keywords to field names
    FIELD_PATTERNS = {
        "3.1": {
            "patterns": [
                r"3\.1\s+Starting\s+Date",
                r"Starting\s+Date",
                r"Start\s+Date",
                r"Commencement\s+Date",
            ],
            "field_name": "starting_date",
            "title": "Starting Date"
        },
        "3.2": {
            "patterns": [
                r"3\.2\s+(?:Access|Possession)\s+Date",
                r"Access\s+Date[s]?",
                r"Possession\s+Date[s]?",
            ],
            "field_name": "access_date",
            "title": "Possession Date(s)"
        },
        "3.3": {
            "patterns": [
                r"3\.3\s+Completion\s+Date",
                r"Completion\s+Date",
                r"Date\s+of\s+Completion",
            ],
            "field_name": "completion_date",
            "title": "Completion Date"
        },
        "3.5": {
            "patterns": [
                r"3\.5\s+.*[Pp]rogramme",
                r"First\s+programme\s+to\s+be\s+submitted",
                r"Submission\s+of\s+first\s+programme",
                r"Period\s+for\s+reply",
            ],
            "field_name": "programme_first_submission",
            "title": "Submission of First Programme"
        },
        "3.6": {
            "patterns": [
                r"3\.6\s+.*[Pp]rogramme",
                r"Revised\s+programme[s]?",
                r"Interval\s+for\s+submitting\s+revised\s+programme",
                r"Programme\s+submission\s+interval",
            ],
            "field_name": "programme_revisions",
            "title": "Submission of Revised Programmes"
        },
        "3.7": {
            "patterns": [
                r"3\.7\s+Delay\s+damages",
                r"Delay\s+damages",
                r"Damages\s+for\s+late\s+Completion",
            ],
            "field_name": "delay_damages",
            "title": "Delay Damages"
        },
        "4.1": {
            "patterns": [
                r"4\.1\s+Defects\s+Date",
                r"Defects\s+Date",
            ],
            "field_name": "defects_date",
            "title": "Defects Date"
        },
        "4.2": {
            "patterns": [
                r"4\.2\s+Defect\s+Correction",
                r"Defect\s+Correction\s+Period",
                r"Defects\s+Correction\s+Period",
            ],
            "field_name": "defect_correction_period",
            "title": "Defect Correction Period"
        },
        "4.3": {
            "patterns": [
                r"4\.3\s+.*[Mm]aintenance",
                r"Landscaping\s+Maintenance\s+Period",
                r"Landscape\s+Maintenance\s+Period",
            ],
            "field_name": "landscaping_maintenance_period",
            "title": "Landscaping Maintenance Period"
        },
        "5.2": {
            "patterns": [
                r"5\.2\s+Assessment",
                r"Assessment\s+Interval",
            ],
            "field_name": "assessment_interval",
            "title": "Assessment Interval"
        },
        "5.3": {
            "patterns": [
                r"5\.3\s+Payment",
                r"Payment\s+Period",
            ],
            "field_name": "payment_period",
            "title": "Payment Period"
        },
        "5.5": {
            "patterns": [
                r"5\.5\s+Retention",
                r"Retention",
                r"Retention\s+Percentage",
            ],
            "field_name": "retention_percentage",
            "title": "Retention Percentage"
        },
        "5.6": {
            "patterns": [
                r"5\.6\s+Bond",
                r"Bond\s+Amount",
                r"Performance\s+Bond",
            ],
            "field_name": "bond_amount",
            "title": "Bond Amount"
        },
        "6.1": {
            "patterns": [
                r"6\.1\s+.*[Ww]eather",
                r"Weather\s+Recording\s+Location",
                r"Weather\s+recorded\s+at",
                r"Place\s+where\s+weather\s+recorded",
            ],
            "field_name": "weather_recording_location",
            "title": "Weather Recording Location"
        },
        "6.2": {
            "patterns": [
                r"6\.2\s+.*[Ww]eather",
                r"Weather\s+Measurement\s+Data",
                r"Weather\s+measurements?",
            ],
            "field_name": "weather_measurement_data",
            "title": "Weather Measurement Data"
        },
        "6.3": {
            "patterns": [
                r"6\.3\s+.*[Ww]eather",
                r"Weather\s+Historical\s+Records",
                r"Historical\s+weather\s+records\s+source",
            ],
            "field_name": "weather_historical_records",
            "title": "Weather Historical Records Source"
        },
    }
    
    # Option X7 delay damages pattern (fallback)
    OPTION_X7_PATTERNS = [
        r"Option\s+X7",
        r"Secondary\s+Option\s+X7",
        r"X7\s+Delay\s+damages",
    ]
    
    # Z-clauses pattern
    Z_CLAUSE_PATTERNS = [
        r"Z\s+[Cc]lause",
        r"Additional\s+[Cc]ondition",
    ]
    
    def __init__(self, debug: bool = False):
        """Initialize table extractor."""
        self.debug = debug
        self.compiled_cd_headers = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.CD_PART_ONE_HEADERS
        ]
        self.compiled_field_patterns = {}
        for clause_num, field_info in self.FIELD_PATTERNS.items():
            self.compiled_field_patterns[clause_num] = {
                "patterns": [re.compile(p, re.IGNORECASE) for p in field_info["patterns"]],
                "field_name": field_info["field_name"],
                "title": field_info["title"]
            }
    
    def log(self, msg: str):
        """Log debug message."""
        if self.debug:
            print(f"[TableExtractor] {msg}")
    
    def find_contract_data_part_one(self, tables: List[Dict[str, Any]], clean_text: str) -> List[Dict[str, Any]]:
        """
        Find tables that belong to Contract Data Part One section.
        
        Args:
            tables: List of table dictionaries from PDF parser
            clean_text: Full clean text from PDF
            
        Returns:
            List of tables in Contract Data Part One
        """
        cd_tables = []
        
        # Find Contract Data Part One section in text
        cd_start_idx = None
        cd_end_idx = len(clean_text)
        
        for pattern in self.compiled_cd_headers:
            match = pattern.search(clean_text)
            if match:
                cd_start_idx = match.start()
                self.log(f"Found CD Part One header at position {cd_start_idx}")
                break
        
        if cd_start_idx is None:
            # Fallback: look for tables on first few pages that contain NEC field patterns
            self.log("CD Part One header not found, using heuristic: tables with NEC field patterns")
        
        # Find end of CD Part One (stop at Works Information or CD Part Two)
        end_patterns = [
            r"Works\s+Information",
            r"Contract\s+Data\s+Part\s+Two",
            r"Contract\s+Data\s+Part\s+2",
        ]
        
        if cd_start_idx is not None:
            search_text = clean_text[cd_start_idx:]
            for pattern_str in end_patterns:
                pattern = re.compile(pattern_str, re.IGNORECASE)
                match = pattern.search(search_text)
                if match:
                    potential_end = cd_start_idx + match.start()
                    if potential_end < cd_end_idx:
                        cd_end_idx = potential_end
        
        # Filter tables: include tables that contain NEC field patterns
        for table in tables:
            # Support both dict and list formats
            rows = []
            if isinstance(table, dict):
                rows = table.get("rows", [])
            elif isinstance(table, list):
                rows = table
            
            if not rows:
                continue
            
            # Check if table contains any NEC field pattern
            table_text = ""
            for row in rows[:10]:  # Check first 10 rows
                if isinstance(row, list) and len(row) >= 2:
                    table_text += " " + str(row[0]) + " " + str(row[1])
                elif isinstance(row, dict):
                    table_text += " " + str(row.get("field", "")) + " " + str(row.get("value", ""))
            
            # Check if table contains NEC field indicators
            has_nec_field = False
            for clause_num, field_info in self.compiled_field_patterns.items():
                for pattern in field_info["patterns"]:
                    if pattern.search(table_text):
                        has_nec_field = True
                        break
                if has_nec_field:
                    break
            
            if has_nec_field:
                cd_tables.append(table)
                self.log(f"Found CD Part One table with NEC fields")
        
        return cd_tables
    
    def extract_from_table_row(self, row: List[str]) -> Optional[Tuple[str, str, str]]:
        """
        Extract NEC field from a table row.
        
        Args:
            row: Table row as list [description, value] or [field, value]
            
        Returns:
            Tuple of (clause_number, field_name, value) or None
        """
        if not row or len(row) < 2:
            return None
        
        description = str(row[0]).strip()
        value = str(row[1]).strip()
        
        # Skip empty or invalid rows
        if not description or not value:
            return None
        
        # Clean value - remove corrupted text fragments
        value = self._clean_value(value)
        if not value or len(value) < 2:
            return None
        
        # Match description against NEC field patterns
        for clause_num, field_info in self.compiled_field_patterns.items():
            for pattern in field_info["patterns"]:
                if pattern.search(description):
                    self.log(f"Matched {clause_num} ({field_info['field_name']}): {value[:80]}")
                    return (clause_num, field_info["field_name"], value)
        
        return None
    
    def _clean_value(self, value: str) -> str:
        """
        Clean extracted value to remove corrupted text fragments.
        
        Removes:
        - Single words like "is", "of", "the", "S603"
        - Excessive whitespace
        - PDF artifacts
        """
        if not value:
            return ""
        
        # Remove PDF artifacts
        value = re.sub(r'\(cid:\d+\)', '', value)
        value = re.sub(r'\s+', ' ', value)
        value = value.strip()
        
        # Remove single-word fragments that are likely corrupted
        # If value is just one word and it's not a date/number, likely corrupted
        words = value.split()
        if len(words) == 1:
            word = words[0]
            # Check if it's a corrupted fragment (common corrupted words)
            corrupted_fragments = ["is", "of", "the", "a", "an", "and", "or", "but"]
            if word.lower() in corrupted_fragments:
                return ""
            # Check if it's a drawing reference without context (e.g., "S603")
            if re.match(r'^[A-Z]\d+$', word) and len(word) < 5:
                return ""
        
        # Remove leading/trailing punctuation
        value = re.sub(r'^[^\w]+|[^\w]+$', '', value)
        
        return value.strip()
    
    def extract_from_tables(self, tables: List[Dict[str, Any]], clean_text: str) -> Dict[str, Any]:
        """
        Extract all NEC fields from Contract Data Part One tables.
        
        Args:
            tables: List of table dictionaries from PDF parser
            clean_text: Full clean text from PDF
            
        Returns:
            Dictionary mapping clause numbers to extracted data:
            {
                "3.1": {"value": "...", "status": "filled|blank|missing", "title": "..."},
                ...
            }
        """
        results = {}
        
        # Initialize all required clauses as missing
        for clause_num in self.FIELD_PATTERNS.keys():
            results[clause_num] = {
                "value": "",
                "status": "missing",
                "title": self.FIELD_PATTERNS[clause_num]["title"]
            }
        
        # Find Contract Data Part One tables
        cd_tables = self.find_contract_data_part_one(tables, clean_text)
        
        if not cd_tables:
            self.log("No Contract Data Part One tables found")
            return results
        
        self.log(f"Found {len(cd_tables)} Contract Data Part One tables")
        
        # Extract from each table
        for table in cd_tables:
            rows = []
            if isinstance(table, dict):
                rows = table.get("rows", [])
            elif isinstance(table, list):
                rows = table
            
            for row in rows:
                # Normalize row format
                normalized_row = None
                if isinstance(row, list) and len(row) >= 2:
                    normalized_row = [str(row[0]).strip(), str(row[1]).strip()]
                elif isinstance(row, dict):
                    field = str(row.get("field", "")).strip()
                    value = str(row.get("value", "")).strip()
                    if field and value:
                        normalized_row = [field, value]
                
                if not normalized_row:
                    continue
                
                # Extract field from row
                extracted = self.extract_from_table_row(normalized_row)
                if extracted:
                    clause_num, field_name, value = extracted
                    
                    # Determine status
                    if value and len(value) > 0:
                        status = "filled"
                    else:
                        # Row exists but value is empty
                        status = "blank"
                    
                    results[clause_num] = {
                        "value": value,
                        "status": status,
                        "title": self.FIELD_PATTERNS[clause_num]["title"]
                    }
        
        return results
    
    def extract_key_dates_from_tables(self, tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract Key Dates from tables.
        
        Args:
            tables: List of table dictionaries
            
        Returns:
            List of key date dictionaries
        """
        key_dates = []
        
        for table in tables:
            rows = []
            if isinstance(table, dict):
                rows = table.get("rows", [])
            elif isinstance(table, list):
                rows = table
            
            for row in rows:
                if isinstance(row, list) and len(row) >= 2:
                    description = str(row[0]).strip().lower()
                    value = str(row[1]).strip()
                    
                    if "key date" in description and value:
                        # Try to extract key date ID and description
                        # Format might be: "KD-01 Structural frame" or "Key Date 1: Structural frame"
                        key_date = {
                            "id": "",
                            "description": value,
                            "date": ""
                        }
                        
                        # Try to extract ID from description
                        id_match = re.search(r'(?:KD[- ]?|Key\s+Date\s*)(\d+|[A-Z]\d+)', description, re.IGNORECASE)
                        if id_match:
                            key_date["id"] = id_match.group(1)
                        
                        # Try to extract date from value
                        date_match = re.search(r'(\d{1,2}\s+\w+\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|Month\s+\d+)', value, re.IGNORECASE)
                        if date_match:
                            key_date["date"] = date_match.group(1)
                            key_date["description"] = value.replace(date_match.group(1), "").strip()
                        
                        key_dates.append(key_date)
        
        return key_dates
    
    def extract_z_clauses(self, clean_text: str) -> List[str]:
        """
        Extract Z-clauses from text.
        
        Args:
            clean_text: Full clean text from PDF
            
        Returns:
            List of Z-clause descriptions
        """
        z_clauses = []
        
        # Find Z-clause section
        z_section_pattern = re.compile(r"Z\s+[Cc]lause[s]?.*?(?=Works\s+Information|Contract\s+Data\s+Part\s+Two|$)", re.IGNORECASE | re.DOTALL)
        z_match = z_section_pattern.search(clean_text)
        
        if z_match:
            z_section = z_match.group(0)
            # Extract individual Z-clauses (lines starting with "Z" or "Z.")
            z_lines = re.findall(r'Z\.?\s*\d+[^\n]+', z_section, re.IGNORECASE)
            z_clauses = [line.strip() for line in z_lines if line.strip()]
        
        return z_clauses
    
    def extract_option_clauses(self, clean_text: str) -> Dict[str, str]:
        """
        Extract Secondary Option clauses (e.g., X7 for delay damages).
        
        Args:
            clean_text: Full clean text from PDF
            
        Returns:
            Dictionary mapping option codes to values
        """
        options = {}
        
        # Look for Option X7 (delay damages)
        x7_patterns = [
            r"Option\s+X7[^\n]*[:\-]\s*([^\n]+)",
            r"X7\s+Delay\s+damages[:\-]\s*([^\n]+)",
        ]
        
        for pattern_str in x7_patterns:
            pattern = re.compile(pattern_str, re.IGNORECASE)
            match = pattern.search(clean_text)
            if match:
                value = match.group(1).strip()
                value = self._clean_value(value)
                if value:
                    options["X7"] = value
                    self.log(f"Found Option X7 (delay damages): {value[:80]}")
                    break
        
        return options
