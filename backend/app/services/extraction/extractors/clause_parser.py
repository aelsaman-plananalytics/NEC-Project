"""
Clause parser for NEC contract documents.

Detects and extracts structured clauses, subclauses, and sections
from Contract Data Part 1 and Part 2.
"""

import re
from typing import List, Dict, Optional, Tuple, Any
from app.services.extraction.extractors.utils_cleaning import clean_text, extract_section_number, is_clause_heading


class ClauseParser:
    """Parse NEC contract clauses and subclauses."""
    
    # Patterns for detecting different clause types
    MAIN_SECTION_PATTERN = re.compile(r'^(\d+)\s+([A-Z][^\.]+?)(?:\.|$)')
    SUBCLAUSE_PATTERN = re.compile(r'^(\d+)\.(\d+)(?:\.(\d+))?\s+([^\.]+?)(?:\.|$)')
    WORKS_DESC_PATTERN = re.compile(r'1\.2\s+[Ww]orks\s+[Dd]escription', re.IGNORECASE)
    SCHEDULE_PATTERN = re.compile(r'(?:Schedule|Schedule A|Schedule of Drawings)', re.IGNORECASE)
    SERIES_PATTERN = re.compile(r'Series\s+(\d+)(?:[/\-](\d+))?', re.IGNORECASE)
    
    def __init__(self):
        """Initialize clause parser."""
        self.clauses = {}
        self.current_section = None
        self.current_subsection = None
    
    def detect_clause_structure(self, text: str) -> Dict[str, Any]:
        """
        Detect clause structure in contract text.
        
        Args:
            text: Full contract text
            
        Returns:
            Dictionary with detected clause structure
        """
        lines = text.split('\n')
        structure = {
            "main_sections": [],
            "subclauses": [],
            "works_description": None,
            "schedule_of_drawings": None
        }
        
        current_section = None
        current_subsection = None
        
        for line in lines:
            line = line.strip()
            if not line or len(line) < 3:
                continue
            
            # Check for main section (e.g., "1. General")
            main_match = self.MAIN_SECTION_PATTERN.match(line)
            if main_match:
                section_num = int(main_match.group(1))
                section_title = main_match.group(2).strip()
                current_section = {
                    "number": section_num,
                    "title": section_title,
                    "text": line
                }
                structure["main_sections"].append(current_section)
                current_subsection = None
                continue
            
            # Check for subclause (e.g., "1.1 Conditions of Contract")
            subclause_match = self.SUBCLAUSE_PATTERN.match(line)
            if subclause_match:
                major = int(subclause_match.group(1))
                minor = int(subclause_match.group(2))
                subminor = subclause_match.group(3)
                title = subclause_match.group(4).strip()
                
                clause_key = f"{major}.{minor}"
                if subminor:
                    clause_key += f".{subminor}"
                
                subclause = {
                    "key": clause_key,
                    "major": major,
                    "minor": minor,
                    "subminor": int(subminor) if subminor else None,
                    "title": title,
                    "text": line,
                    "section": current_section["number"] if current_section else None
                }
                structure["subclauses"].append(subclause)
                current_subsection = subclause
                continue
            
            # Check for Works Description
            if self.WORKS_DESC_PATTERN.search(line):
                structure["works_description"] = {
                    "found": True,
                    "line": line
                }
            
            # Check for Schedule of Drawings
            if self.SCHEDULE_PATTERN.search(line):
                structure["schedule_of_drawings"] = {
                    "found": True,
                    "line": line
                }
        
        return structure
    
    def extract_part1_section(self, text: str, section_key: str) -> Dict[str, Any]:
        """
        Extract a specific Part 1 section.
        
        Args:
            text: Contract text
            section_key: Section key (e.g., "1_general", "2_contractor_responsibilities")
            
        Returns:
            Dictionary with extracted section data
        """
        section_num = section_key.split('_')[0]
        section_data = {}
        
        # Pattern to find section
        section_pattern = re.compile(
            rf'^{re.escape(section_num)}\.\s+([^\n]+)',
            re.MULTILINE | re.IGNORECASE
        )
        
        match = section_pattern.search(text)
        if not match:
            return section_data
        
        # Extract subclauses within this section
        subclause_pattern = re.compile(
            rf'^{re.escape(section_num)}\.(\d+)(?:\.(\d+))?\s+([^\n]+)',
            re.MULTILINE
        )
        
        for match in subclause_pattern.finditer(text):
            minor = match.group(1)
            subminor = match.group(2)
            content = match.group(3).strip()
            
            if subminor:
                key = f"{section_num}.{minor}.{subminor}"
            else:
                key = f"{section_num}.{minor}"
            
            # Clean key for dictionary (replace dots with underscores)
            dict_key = key.replace('.', '_')
            section_data[dict_key] = content
        
        return section_data
    
    def extract_works_description(self, text: str) -> str:
        """
        Extract Works Description (1.2) section.
        
        Args:
            text: Contract text
            
        Returns:
            Works description text
        """
        # Find 1.2 Works description section
        pattern = re.compile(
            r'1\.2\s+[Ww]orks\s+[Dd]escription[:\s]*(.*?)(?=\d+\.\d+|$)',
            re.DOTALL | re.IGNORECASE
        )
        
        match = pattern.search(text)
        if match:
            works_desc = match.group(1).strip()
            # Clean up the text
            works_desc = clean_text(works_desc)
            return works_desc
        
        return ""
    
    def extract_employer_info(self, text: str) -> Dict[str, str]:
        """
        Extract Employer information (1.3).
        
        Args:
            text: Contract text
            
        Returns:
            Dictionary with employer name, address, representative
        """
        employer = {"name": "", "address": "", "representative": ""}
        
        # Pattern for 1.3 Employer
        pattern = re.compile(
            r'1\.3\s+[Tt]he\s+[Ee]mployer\s+is\s+(.+?)(?:and\s+is\s+represented\s+by\s+(.+?))?(?=\d+\.\d+|$)',
            re.DOTALL | re.IGNORECASE
        )
        
        match = pattern.search(text)
        if match:
            employer_text = match.group(1).strip()
            if match.group(2):
                employer["representative"] = match.group(2).strip()
            
            # Try to extract name and address
            lines = employer_text.split('\n')
            if lines:
                employer["name"] = lines[0].strip()
                if len(lines) > 1:
                    employer["address"] = ' '.join(lines[1:]).strip()
        
        return employer
    
    def extract_project_manager(self, text: str) -> Dict[str, str]:
        """
        Extract Project Manager information (1.4).
        
        Args:
            text: Contract text
            
        Returns:
            Dictionary with project manager details
        """
        pm = {"name": "", "address": "", "representative": ""}
        
        pattern = re.compile(
            r'1\.4\s+[Tt]he\s+[Pp]roject\s+[Mm]anager\s+is\s+(.+?)(?:and\s+is\s+represented\s+by\s+(.+?))?(?=\d+\.\d+|$)',
            re.DOTALL | re.IGNORECASE
        )
        
        match = pattern.search(text)
        if match:
            pm_text = match.group(1).strip()
            if match.group(2):
                pm["representative"] = match.group(2).strip()
            
            lines = pm_text.split('\n')
            if lines:
                pm["name"] = lines[0].strip()
                if len(lines) > 1:
                    pm["address"] = ' '.join(lines[1:]).strip()
        
        return pm
    
    def extract_payment_terms(self, text: str) -> Dict[str, str]:
        """
        Extract Payment section (5) details.
        
        Args:
            text: Contract text
            
        Returns:
            Dictionary with payment terms
        """
        payment = {
            "currency": "",
            "assessment_interval": "",
            "payment_period": "",
            "interest_rate": "",
            "retention_amount": "",
            "contract_bond_amount": "",
            "exchange_rates": "",
            "assessment_dates_schedule": ""
        }
        
        # Extract each payment subclause
        patterns = {
            "currency": r'5\.1\s+[Tt]he\s+currency\s+of\s+this\s+contract\s+is\s+(.+?)(?=\d+\.\d+|$)',
            "assessment_interval": r'5\.2\s+[Tt]he\s+assessment\s+interval\s+is\s+(.+?)(?=\d+\.\d+|$)',
            "payment_period": r'5\.3\s+[Tt]he\s+period\s+within\s+which\s+payments\s+are\s+to\s+be\s+made\s+is\s+(.+?)(?=\d+\.\d+|$)',
            "interest_rate": r'5\.4\s+[Tt]he\s+interest\s+rate\s+is\s+(.+?)(?=\d+\.\d+|$)',
            "retention_amount": r'5\.5\s+[Tt]he\s+retention\s+(?:free\s+amount|percentage\s+amount)\s+is\s+(.+?)(?=\d+\.\d+|$)',
            "contract_bond_amount": r'5\.6\s+[Tt]he\s+amount\s+of\s+the\s+guarantee\s+bond\s+is\s+(.+?)(?=\d+\.\d+|$)',
            "exchange_rates": r'5\.7\s+[Ee]xchange\s+rates\s+are\s+(.+?)(?=\d+\.\d+|$)',
            "assessment_dates_schedule": r'5\.8\s+[Aa]\s+schedule\s+of\s+Assessment\s+Dates\s+is\s+(.+?)(?=\d+\.\d+|$)'
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                payment[key] = clean_text(match.group(1).strip())
        
        return payment
    
    def extract_time_section(self, text: str) -> Dict[str, Any]:
        """
        Extract Time section (3) details.
        
        Args:
            text: Contract text
            
        Returns:
            Dictionary with time-related data
        """
        time_data = {
            "starting_date": "",
            "possession_dates": {},
            "completion_date": "",
            "taking_over": "",
            "first_programme_submission": "",
            "revised_programme_interval": "",
            "delay_damages": ""
        }
        
        patterns = {
            "starting_date": r'3\.1\s+[Tt]he\s+starting\s+date\s+of\s+the\s+Contract\s+Period\s+is\s+(.+?)(?=\d+\.\d+|$)',
            "completion_date": r'3\.3\s+[Tt]he\s+Completion\s+Date\s+for\s+the\s+whole\s+of\s+the\s+works\s+is\s+(.+?)(?=\d+\.\d+|$)',
            "taking_over": r'3\.4\s+[Tt]he\s+Employer\s+is\s+(.+?)(?=\d+\.\d+|$)',
            "first_programme_submission": r'3\.5\s+[Tt]he\s+Contractor\s+is\s+to\s+submit\s+a\s+first\s+programme\s+for\s+acceptance\s+within\s+(.+?)(?=\d+\.\d+|$)',
            "revised_programme_interval": r'3\.6\s+[Tt]he\s+Contractor\s+submits\s+a\s+revised\s+Programme\s+at\s+intervals\s+no\s+longer\s+than\s+(.+?)(?=\d+\.\d+|$)',
            "delay_damages": r'3\.7\s+[Dd]elay\s+damages\s+for\s+Completion\s+of\s+the\s+whole\s+of\s+the\s+works\s+are\s+(.+?)(?=\d+\.\d+|$)'
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                time_data[key] = clean_text(match.group(1).strip())
        
        return time_data
    
    def extract_contractor_data_part2(self, text: str) -> Dict[str, Any]:
        """
        Extract Contract Data Part 2 (Contractor data).
        
        Args:
            text: Contract text
            
        Returns:
            Dictionary with contractor data
        """
        contractor_data = {
            "contractor_name": "",
            "contractor_address": "",
            "contractor_representative": "",
            "direct_fee_percentage": "",
            "subcontracted_fee_percentage": "",
            "working_areas": "",
            "key_persons": [],
            "works_information_design": "",
            "programme_identified": "",
            "adjudicator_acceptable": "",
            "subcontractors": [],
            "insurance_details": {},
            "quality_statement_location": "",
            "parent_company_guarantee": ""
        }
        
        # Find Part 2 section
        part2_pattern = re.compile(
            r'CONTRACT\s+DATA\s+PART\s+TWO[^\n]*(.*?)(?=PRICING\s+DATA|CONTRACTORS\s+QUALITY|$)',
            re.DOTALL | re.IGNORECASE
        )
        
        match = part2_pattern.search(text)
        if not match:
            return contractor_data
        
        part2_text = match.group(1)
        
        # Extract contractor name (1.1)
        name_pattern = r'1\.1\s+[Tt]he\s+Contractor\s+is\s+Name[^\n]*\n\s*([^\n]+)'
        name_match = re.search(name_pattern, part2_text, re.IGNORECASE)
        if name_match:
            contractor_data["contractor_name"] = clean_text(name_match.group(1).strip())
        
        # Extract fee percentages
        fee_pattern = r'1\.2\s+[Tt]he\s+Direct\s+fee\s+percentage\s+is\s+([^\n]+)'
        fee_match = re.search(fee_pattern, part2_text, re.IGNORECASE)
        if fee_match:
            contractor_data["direct_fee_percentage"] = clean_text(fee_match.group(1).strip())
        
        sub_fee_pattern = r'1\.3\s+[Tt]he\s+subcontracted\s+fee\s+percentage\s+is\s+([^\n]+)'
        sub_fee_match = re.search(sub_fee_pattern, part2_text, re.IGNORECASE)
        if sub_fee_match:
            contractor_data["subcontracted_fee_percentage"] = clean_text(sub_fee_match.group(1).strip())
        
        # Extract working areas
        areas_pattern = r'1\.4\s+[Tt]he\s+working\s+areas\s+are\s+the\s+Site\s+and\s+([^\n]+)'
        areas_match = re.search(areas_pattern, part2_text, re.IGNORECASE)
        if areas_match:
            contractor_data["working_areas"] = clean_text(areas_match.group(1).strip())
        
        return contractor_data



