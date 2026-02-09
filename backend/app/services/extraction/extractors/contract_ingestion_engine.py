"""
Main Contract Ingestion Engine for NEC contracts.

Orchestrates table extraction, text extraction, clause parsing,
and builds the final structured JSON contract model.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

from app.services.parsing.parsers.pdf_parser import DocumentParser
from app.services.extraction.extractors.table_extractor import TableExtractor
from app.services.extraction.extractors.clause_parser import ClauseParser
from app.services.extraction.extractors.nec_contract_model import (
    NECContract, ContractDataPart1, ContractDataPart2,
    Employer, ProjectManager, TimeSection, TestingDefects,
    PaymentSection, CompensationEvents, RisksInsurance,
    DisputesTermination, DrawingReference, ContractorData,
    ScheduleOfCostComponents
)
from app.services.extraction.extractors.utils_cleaning import clean_text
from app.services.extraction.extractors.utils_pdf import get_pdf_info, extract_all_text


class ContractIngestionEngine:
    """
    Main engine for ingesting and structuring NEC contracts.
    
    Processes PDFs to extract:
    - Tables (Schedule of Drawings, Series tables)
    - Structured clauses (Part 1, Part 2)
    - Contract data fields
    """
    
    def __init__(self):
        """Initialize the ingestion engine."""
        self.table_extractor = TableExtractor()
        self.clause_parser = ClauseParser()
        self.document_parser = DocumentParser()
    
    def ingest_contract(self, pdf_path: str) -> Dict[str, Any]:
        """
        Main entry point: ingest contract and return structured JSON.
        
        Args:
            pdf_path: Path to PDF contract file
            
        Returns:
            Structured contract dictionary ready for JSON serialization
        """
        start_time = datetime.now()
        
        print(f"[INGESTION_ENGINE] Starting contract ingestion: {pdf_path}")
        
        # Step 1: Extract all text
        print(f"[INGESTION_ENGINE] Extracting text from PDF...")
        contract_text = extract_all_text(pdf_path)
        if not contract_text:
            # Fallback to DocumentParser
            contract_text = self.document_parser.extract_text(pdf_path)
        
        contract_text = clean_text(contract_text)
        print(f"[INGESTION_ENGINE] Extracted {len(contract_text)} characters of text")
        
        # Step 2: Extract tables
        print(f"[INGESTION_ENGINE] Extracting tables...")
        all_tables = self.table_extractor.extract_tables_hybrid(pdf_path)
        print(f"[INGESTION_ENGINE] Found {len(all_tables)} tables")
        
        # Step 3: Parse clause structure
        print(f"[INGESTION_ENGINE] Parsing clause structure...")
        clause_structure = self.clause_parser.detect_clause_structure(contract_text)
        
        # Step 4: Extract Part 1 data
        print(f"[INGESTION_ENGINE] Extracting Contract Data Part 1...")
        part1_data = self._extract_part1(contract_text, all_tables)
        
        # Step 5: Extract Part 2 data
        print(f"[INGESTION_ENGINE] Extracting Contract Data Part 2...")
        part2_data = self._extract_part2(contract_text, all_tables)
        
        # Step 6: Extract Schedule of Drawings
        print(f"[INGESTION_ENGINE] Extracting Schedule of Drawings...")
        drawings = self._extract_schedule_of_drawings(contract_text, all_tables)
        part1_data["schedule_of_drawings"] = drawings
        
        # Step 7: Build final structure
        end_time = datetime.now()
        extraction_time = (end_time - start_time).total_seconds()
        
        pdf_info = get_pdf_info(pdf_path)
        
        result = {
            "metadata": {
                "file_name": Path(pdf_path).name,
                "pages": pdf_info.get("total_pages", 0),
                "extraction_time": f"{extraction_time:.2f}s",
                "tables_detected": len(all_tables)
            },
            "contract": {
                "part_1": part1_data,
                "part_2": part2_data
            }
        }
        
        print(f"[INGESTION_ENGINE] Ingestion complete in {extraction_time:.2f}s")
        return result
    
    def _extract_part1(self, text: str, tables: List[Dict]) -> Dict[str, Any]:
        """Extract Contract Data Part 1."""
        part1 = {}
        
        # 1. General
        part1["1_general"] = {}
        part1["1_general"]["1.1_conditions_of_contract"] = self._extract_subclause(text, "1.1")
        part1["1_general"]["1.2_works_description"] = self.clause_parser.extract_works_description(text)
        
        employer = self.clause_parser.extract_employer_info(text)
        part1["1_general"]["1.3_employer"] = employer
        
        pm = self.clause_parser.extract_project_manager(text)
        part1["1_general"]["1.4_project_manager"] = pm.get("name", "")
        if pm.get("address"):
            part1["1_general"]["1.4_project_manager"] += f", {pm['address']}"
        if pm.get("representative"):
            part1["1_general"]["1.4_project_manager"] += f", represented by {pm['representative']}"
        
        part1["1_general"]["1.5_quantity_surveyor"] = self._extract_subclause(text, "1.5")
        part1["1_general"]["1.6_supervisor"] = self._extract_subclause(text, "1.6")
        part1["1_general"]["1.7_cdm_coordinator"] = self._extract_subclause(text, "1.7")
        part1["1_general"]["1.8_adjudicator_nomination_body"] = self._extract_subclause(text, "1.8")
        part1["1_general"]["1.9_works_information"] = self._extract_subclause(text, "1.9")
        part1["1_general"]["1.10_site_information"] = self._extract_subclause(text, "1.10")
        part1["1_general"]["1.11_boundaries_of_site"] = self._extract_subclause(text, "1.11")
        part1["1_general"]["1.12_language"] = self._extract_subclause(text, "1.12")
        part1["1_general"]["1.13_law"] = self._extract_subclause(text, "1.13")
        part1["1_general"]["1.14_period_for_reply"] = self._extract_subclause(text, "1.14")
        part1["1_general"]["1.15_pre_construction_info"] = self._extract_subclause(text, "1.15")
        part1["1_general"]["1.16_amendments"] = self._extract_subclause(text, "1.16")
        part1["1_general"]["1.17_additions"] = self._extract_subclause(text, "1.17")
        part1["1_general"]["1.18_project_risk_register"] = self._extract_subclause(text, "1.18")
        
        # 2. Contractor's Main Responsibilities
        part1["2_contractor_responsibilities"] = {}
        part1["2_contractor_responsibilities"]["2.1_liability_for_defects"] = self._extract_subclause(text, "2.1")
        part1["2_contractor_responsibilities"]["2.2_considerate_constructors"] = self._extract_subclause(text, "2.2")
        part1["2_contractor_responsibilities"]["2.3_forecasts"] = self._extract_subclause(text, "2.3")
        part1["2_contractor_responsibilities"]["2.4_early_warnings"] = self._extract_subclause(text, "2.4")
        
        # 3. Time
        time_data = self.clause_parser.extract_time_section(text)
        part1["3_time"] = time_data
        
        # 4. Testing and Defects
        part1["4_testing_and_defects"] = {}
        part1["4_testing_and_defects"]["4.1_defects_date"] = self._extract_subclause(text, "4.1")
        part1["4_testing_and_defects"]["4.2_defect_correction_period"] = self._extract_subclause(text, "4.2")
        part1["4_testing_and_defects"]["4.3_landscape_maintenance"] = self._extract_subclause(text, "4.3")
        
        # 5. Payment
        payment_data = self.clause_parser.extract_payment_terms(text)
        part1["5_payment"] = payment_data
        
        # 6. Compensation Events
        part1["6_compensation_events"] = {}
        part1["6_compensation_events"]["6.1_weather_location"] = self._extract_subclause(text, "6.1")
        part1["6_compensation_events"]["6.2_weather_measurements"] = self._extract_subclause(text, "6.2")
        part1["6_compensation_events"]["6.3_weather_data"] = self._extract_subclause(text, "6.3")
        
        # 7. Title
        part1["7_title"] = self._extract_subclause(text, "7.1")
        
        # 8. Risks and Insurance
        part1["8_risks_and_insurance"] = {}
        for i in range(1, 10):
            clause_key = f"8.{i}"
            dict_key = f"8.{i}".replace('.', '_')
            part1["8_risks_and_insurance"][dict_key] = self._extract_subclause(text, clause_key)
        
        # 9. Disputes and Termination
        part1["9_disputes_and_termination"] = {}
        part1["9_disputes_and_termination"]["9.1_disagreement_over_adjudicator"] = self._extract_subclause(text, "9.1")
        part1["9_disputes_and_termination"]["9.2_adjudication_procedure"] = self._extract_subclause(text, "9.2")
        
        return part1
    
    def _extract_part2(self, text: str, tables: List[Dict]) -> Dict[str, Any]:
        """Extract Contract Data Part 2."""
        contractor_data = self.clause_parser.extract_contractor_data_part2(text)
        
        part2 = {
            "contractor_data": contractor_data,
            "schedule_of_cost_components": {}
        }
        
        return part2
    
    def _extract_subclause(self, text: str, clause_key: str) -> str:
        """
        Extract content of a specific subclause.
        
        Args:
            text: Contract text
            clause_key: Clause key (e.g., "1.1", "2.3")
            
        Returns:
            Extracted clause content
        """
        # Escape dots for regex
        escaped_key = clause_key.replace('.', r'\.')
        
        # Pattern to find clause and extract content until next clause
        pattern = re.compile(
            rf'^{escaped_key}\s+([^\n]+(?:\n(?!\d+\.\d+)[^\n]+)*)',
            re.MULTILINE | re.DOTALL
        )
        
        match = pattern.search(text)
        if match:
            content = match.group(1).strip()
            # Clean up
            content = clean_text(content)
            # Remove trailing dots if they're just formatting
            content = re.sub(r'\.{3,}', '...', content)
            return content
        
        return ""
    
    def _extract_schedule_of_drawings(self, text: str, tables: List[Dict]) -> List[Dict[str, str]]:
        """
        Extract Schedule of Drawings from tables and text.
        
        Args:
            text: Contract text
            tables: List of extracted tables
            
        Returns:
            List of drawing reference dictionaries
        """
        drawings = []
        
        # First, try to find drawings table
        for table in tables:
            table_data = table.get("data", [])
            if not table_data:
                continue
            
            # Check if this looks like a drawings table
            # Look for keywords in first few rows
            header_text = ' '.join(str(cell) for row in table_data[:3] for cell in row if cell).lower()
            
            if any(keyword in header_text for keyword in ['number', 'title', 'scale', 'status', 'rev', 'drawing']):
                # Try to parse as drawings table
                parsed = self.table_extractor.parse_drawings_table(table_data)
                if parsed:
                    drawings.extend(parsed)
        
        # If no table found, try text extraction
        if not drawings:
            # Look for Schedule A or Schedule of Drawings section
            schedule_pattern = re.compile(
                r'Schedule\s+(?:A\s*[–-]?\s*)?Drawings.*?(?=\d+\.\s+[A-Z]|$)',
                re.DOTALL | re.IGNORECASE
            )
            
            match = schedule_pattern.search(text)
            if match:
                schedule_text = match.group(0)
                # Try to extract drawing references from text
                drawing_refs = self._extract_drawings_from_text(schedule_text)
                drawings.extend(drawing_refs)
        
        return drawings
    
    def _extract_drawings_from_text(self, text: str) -> List[Dict[str, str]]:
        """
        Extract drawing references from text (fallback if table extraction fails).
        
        Args:
            text: Text containing drawing references
            
        Returns:
            List of drawing dictionaries
        """
        drawings = []
        
        # Pattern for drawing numbers (e.g., 000041/ELW/100/01)
        drawing_num_pattern = re.compile(r'\b(\d{6}/[A-Z]+/\d+/\d+)\b')
        
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Look for drawing number
            match = drawing_num_pattern.search(line)
            if match:
                drawing_num = match.group(1)
                
                # Try to extract other fields from the line
                drawing = {
                    "number": drawing_num,
                    "title": line,
                    "size": "",
                    "revision": "",
                    "scale": "",
                    "status": ""
                }
                
                # Extract revision (single letter after number)
                rev_match = re.search(rf'{re.escape(drawing_num)}\s*([A-Z])\s+', line)
                if rev_match:
                    drawing["revision"] = rev_match.group(1)
                
                # Extract scale (e.g., 1:500)
                scale_match = re.search(r'(\d+:\d+)', line)
                if scale_match:
                    drawing["scale"] = scale_match.group(1)
                
                # Extract status
                if re.search(r'\b(Complete|Not Finalised|Not Started)\b', line, re.IGNORECASE):
                    status_match = re.search(r'\b(Complete|Not Finalised|Not Started)\b', line, re.IGNORECASE)
                    if status_match:
                        drawing["status"] = status_match.group(1)
                
                drawings.append(drawing)
        
        return drawings



