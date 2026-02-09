"""
Main NEC Contract Parser.

Extracts programme-critical information from NEC contract PDFs:
- Scope items
- Constraints
- Milestones
- Contract dates

Uses TOC detection and fuzzy matching for accurate clause location.
"""

import os
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from app.services.parsing.parsers.pdf_parser import DocumentParser
from app.contract_parser.toc_detector import TOCDetector
from app.contract_parser.clause_locator import ClauseLocator
from app.contract_parser.section_extractor import SectionExtractor
from app.contract_parser.cleaner import TextCleaner


class NECParser:
    """Main parser for NEC contract documents."""
    
    def __init__(self):
        """Initialize NEC parser."""
        self.toc_detector = TOCDetector()
        self.clause_locator = ClauseLocator()
        self.section_extractor = SectionExtractor()
        self.cleaner = TextCleaner()
        
        # Check AI_MODE
        self.ai_mode = os.getenv("AI_MODE", "mock").lower().strip()
        print(f"[NEC_PARSER] Initialized in {self.ai_mode.upper()} mode")
    
    def parse_contract(self, pdf_path: str) -> Dict[str, Any]:
        """
        Parse NEC contract PDF and extract programme-critical information.
        
        Uses hybrid extraction (PDFPlumber + OCR + Table Capture).
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Dictionary with structure:
            {
                "contract_text": "...",
                "sections": {...},
                "tables": [...],
                "key_dates": {...},
                "constraints": {...},
                "scope_items": [...],
                "drawings": [...],
                "metadata": {...}
            }
        """
        print(f"[NEC_PARSER] Parsing contract with hybrid extraction: {pdf_path}")
        
        # Step 1: Extract hybrid PDF data (4 layers)
        hybrid_data = DocumentParser.extract_hybrid(pdf_path)
        pages = hybrid_data.get("pages", [])
        
        if not pages:
            return self._empty_result(pdf_path, "No pages extracted from PDF")
        
        print(f"[NEC_PARSER] Extracted {len(pages)} pages")
        
        # Step 2: Detect TOC
        toc_page_idx = self.toc_detector.detect_toc_page(pages)
        toc_entries = []
        toc_detected = False
        
        if toc_page_idx is not None:
            print(f"[NEC_PARSER] TOC detected on page {toc_page_idx + 1}")
            toc_entries = self.toc_detector.extract_toc_entries(pages, toc_page_idx)
            toc_detected = len(toc_entries) > 0
            print(f"[NEC_PARSER] Extracted {len(toc_entries)} TOC entries")
        else:
            print(f"[NEC_PARSER] No TOC detected, using fallback search")
        
        # Step 3: Find target clauses
        if toc_detected:
            clause_pages = self.clause_locator.find_clauses_from_toc(toc_entries)
        else:
            clause_pages = self.clause_locator.find_clauses_fallback(pages)
        
        print(f"[NEC_PARSER] Found clauses: {clause_pages}")
        
        # Step 4: Extract sections - ONLY from TOC-matched pages
        # NOTE: This contract does NOT contain Volume 3 Works Information
        # Extract ONLY: Clause 1.2 Works Description, Drawing Schedule, Section 3 Programme Requirements
        scope_items = []
        constraints = []
        milestones = []
        contract_dates = {}
        missing_sections = []
        
        # 1. EXTRACT WORKS DESCRIPTION FROM CLAUSE 1.2 ONLY (FROM TABLE - NO FALLBACK)
        if clause_pages.get("works_description"):
            page_num = clause_pages["works_description"]
            print(f"[NEC_PARSER] Extracting Works Description from Clause 1.2 table (page {page_num})")
            
            # MUST extract from table cells - NO text block fallback
            works_desc_text = self.clause_locator.find_clause_1_2_in_table(pages, page_num)
            
            if works_desc_text:
                # Split into atomic items using specified separators
                atomic_items = self.section_extractor.split_works_description(works_desc_text)
                for item_text in atomic_items:
                    scope_item = self.section_extractor.create_scope_item(
                        item_text, source="works_description"
                    )
                    # Only add if it has features (not admin content)
                    if scope_item and self._has_valid_features(scope_item):
                        scope_items.append(scope_item)
            else:
                print(f"[NEC_PARSER] WARNING: Clause 1.2 not found in table cells on page {page_num}")
                missing_sections.append("works_description")
        else:
            missing_sections.append("works_description")
        
        # 2. EXTRACT SCHEDULE OF DRAWINGS (FROM TABLES ONLY)
        if clause_pages.get("drawings"):
            page_num = clause_pages["drawings"]
            print(f"[NEC_PARSER] Extracting Schedule of Drawings from tables (page {page_num})")
            
            # Extract from hybrid data tables (already extracted by PDF parser)
            all_draw_tables = []
            for table in hybrid_data.get("tables", []):
                # Support both dict-style tables and stream-mode list tables
                if isinstance(table, dict):
                    table_name = table.get("table_name", "").lower()
                elif isinstance(table, list):
                    # Stream mode: infer name from first row
                    if table and len(table) > 0:
                        first_row_text = " ".join(str(cell).lower() for cell in table[0] if cell)
                        table_name = first_row_text
                    else:
                        table_name = ""
                else:
                    continue
                
                if "drawing" in table_name or "schedule" in table_name:
                    all_draw_tables.append(table)
            
            # Also check pages for drawing schedule tables
            drawing_pages = self.clause_locator.get_section_pages(pages, page_num, "drawings")
            for draw_page_num in drawing_pages:
                page_idx = draw_page_num - 1
                if page_idx < len(pages):
                    page = pages[page_idx]
                    page_tables = page.get("tables", [])
                    for table in page_tables:
                        # Support both dict-style tables and stream-mode list tables
                        if isinstance(table, dict):
                            rows = table.get("rows", [])
                        elif isinstance(table, list):
                            # Stream mode: table IS the list of rows
                            rows = table
                        else:
                            rows = []
                        
                        # Normalize rows into list-of-lists
                        normalized_rows = []
                        for row in rows:
                            if isinstance(row, list):
                                normalized_rows.append([str(cell).strip() for cell in row])
                            elif isinstance(row, str):
                                normalized_rows.append([row.strip()])
                            else:
                                continue
                        
                        rows = normalized_rows
                        
                        if rows:
                            # Check first row for drawing-related keywords
                            first_row = rows[0] if rows else []
                            if isinstance(first_row, list):
                                row_text = " ".join(str(cell).lower() for cell in first_row if cell)
                            else:
                                row_text = str(first_row).lower()
                            
                            if any(keyword in row_text for keyword in ["drawing", "code", "title", "sheet", "number"]):
                                all_draw_tables.append(table)
            
            # Extract scope items from drawing schedule tables
            for table in all_draw_tables:
                drawing_items = self.section_extractor.extract_scope_from_drawing_table(
                    table, source="drawing_schedule"
                )
                # Only add items with valid features
                for item in drawing_items:
                    if self._has_valid_features(item):
                        scope_items.append(item)
        else:
            print(f"[NEC_PARSER] Drawing schedule not found in TOC")
        
        # 3. EXTRACT PROGRAMME REQUIREMENTS FROM SECTION 3 (Time) - FROM TABLE ONLY
        if clause_pages.get("time_section"):
            page_num = clause_pages["time_section"]
            print(f"[NEC_PARSER] Extracting Programme Requirements from Section 3 table (page {page_num})")
            
            # Extract from table - NO text fallback
            time_data = self.clause_locator.find_section_3_in_table(pages, page_num)
            
            # Also check hybrid data tables for time section data
            for table in hybrid_data.get("tables", []):
                # Support both dict-style tables and stream-mode list tables
                if isinstance(table, dict):
                    table_name = table.get("table_name", "").lower()
                    rows = table.get("rows", [])
                elif isinstance(table, list):
                    # Stream mode: table is list of rows, infer name from first row
                    rows = table
                    if rows and len(rows) > 0:
                        first_row_text = " ".join(str(cell).lower() for cell in rows[0] if cell)
                        table_name = first_row_text
                    else:
                        table_name = ""
                else:
                    continue
                
                if "time" in table_name or "section 3" in table_name or "key date" in table_name:
                    # Normalize rows into list-of-lists
                    normalized_rows = []
                    for row in rows:
                        if isinstance(row, list):
                            normalized_rows.append([str(cell).strip() for cell in row])
                        elif isinstance(row, dict):
                            # Convert dict row to list format
                            if "field" in row and "value" in row:
                                normalized_rows.append([row["field"], row["value"]])
                            else:
                                normalized_rows.append(list(row.values()))
                        elif isinstance(row, str):
                            normalized_rows.append([row.strip()])
                        else:
                            continue
                    
                    # Extract from table rows
                    for row in normalized_rows:
                        if isinstance(row, list) and len(row) >= 2:
                            field = str(row[0]).strip().lower()
                            value = str(row[1]).strip()
                        elif isinstance(row, dict):
                            field = str(row.get("field", "")).strip().lower()
                            value = str(row.get("value", "")).strip()
                        else:
                            continue
                        
                        if not field or not value:
                            continue
                        
                        if "starting" in field and "date" in field:
                            if not time_data:
                                time_data = {}
                            time_data["starting_date"] = value
                        elif "completion" in field and "date" in field:
                            if not time_data:
                                time_data = {}
                            time_data["completion_date"] = value
                        elif "possession" in field or "access" in field:
                            if not time_data:
                                time_data = {"access_dates": []}
                            if "access_dates" not in time_data:
                                time_data["access_dates"] = []
                            time_data["access_dates"].append(value)
                        elif "programme" in field and "submission" in field:
                            if not time_data:
                                time_data = {}
                            time_data["programme_submission_rules"] = value
                        elif "programme" in field and "revision" in field:
                            if not time_data:
                                time_data = {}
                            time_data["programme_revision_rules"] = value
            
            # Populate contract_dates
            if time_data:
                contract_dates = {
                    "starting_date": time_data.get("starting_date", ""),
                    "completion_date": time_data.get("completion_date", ""),
                    "access_dates": time_data.get("access_dates", []),
                    "key_dates": time_data.get("key_dates", []),
                    "programme_submission_rules": time_data.get("programme_submission_rules", ""),
                    "programme_revision_rules": time_data.get("programme_revision_rules", "")
                }
                
                # Extract constraints from programme rules
                if time_data.get("programme_submission_rules"):
                    constraints.append({
                        "type": "programme",
                        "description": time_data["programme_submission_rules"],
                        "related_assets": [],
                        "locations": []
                    })
                
                if time_data.get("programme_revision_rules"):
                    constraints.append({
                        "type": "programme",
                        "description": time_data["programme_revision_rules"],
                        "related_assets": [],
                        "locations": []
                    })
                
                # Extract milestones from time section
                if time_data.get("programme_submission_rules"):
                    milestones.append({
                        "name": "Programme Submission",
                        "description": time_data["programme_submission_rules"],
                        "category": "programme"
                    })
            else:
                print(f"[NEC_PARSER] WARNING: Section 3 data not found in tables on page {page_num}")
                missing_sections.append("time_section")
        else:
            missing_sections.append("time_section")
        
        # Ensure contract_dates has correct structure
        if not contract_dates or not isinstance(contract_dates, dict):
            contract_dates = {
                "starting_date": "",
                "completion_date": "",
                "access_dates": [],
                "key_dates": [],
                "programme_submission_rules": "",
                "programme_revision_rules": ""
            }
        else:
            # Ensure all required fields exist
            if "access_dates" not in contract_dates:
                contract_dates["access_dates"] = contract_dates.get("possession_dates", [])
            if "programme_revision_rules" not in contract_dates:
                contract_dates["programme_revision_rules"] = ""
        
        # 4. Filter out invalid items (zero features, admin content, TOC fragments, etc.)
        # ONLY allow scope items from Clause 1.2 and Drawing Schedule
        scope_items = self._filter_scope_sources(scope_items)
        scope_items = self._filter_scope_items(scope_items)
        scope_items = self._filter_invalid_items(scope_items)
        
        # Remove duplicates
        scope_items = self._deduplicate_scope_items(scope_items)
        
        print(f"[NEC_PARSER] Extraction complete:")
        print(f"  - Scope items: {len(scope_items)}")
        print(f"  - Constraints: {len(constraints)}")
        print(f"  - Milestones: {len(milestones)}")
        print(f"  - Contract dates: {len(contract_dates)}")
        
        # Build result with new structure
        result = {
            "contract_text": hybrid_data.get("contract_text", ""),
            "sections": hybrid_data.get("sections", {}),
            "tables": hybrid_data.get("tables", []),
            "key_dates": hybrid_data.get("key_dates", {}),
            "constraints": constraints,  # List of constraint dicts
            "scope_items": scope_items,
            "drawings": hybrid_data.get("drawings", []),
            "milestones": milestones,
            "contract_dates": contract_dates,
            "metadata": {
                **hybrid_data.get("metadata", {}),
                "file_name": os.path.basename(pdf_path),
                "extraction_timestamp": datetime.now().isoformat(),
                "toc_detected": toc_detected,
                "missing_sections": missing_sections
            }
        }
        
        return result
    
    def _has_valid_features(self, item: Dict[str, Any]) -> bool:
        """
        Check if scope item has valid features (not admin content).
        
        Returns False if:
        - No discipline, assets, or actions
        - Text is clearly admin content
        """
        # Must have at least one feature
        discipline = item.get("discipline", "")
        assets = item.get("assets", [])
        actions = item.get("actions", [])
        
        if not discipline and not assets and not actions:
            return False
        
        # Check text for admin keywords
        text = item.get("text", "").lower()
        admin_keywords = [
            "payment", "insurance", "bond", "guarantee", "adjudicator",
            "supervisor", "project manager", "employer", "contractor",
            "cdm coordinator", "quantity surveyor", "health and safety",
            "quality statement", "questionnaire", "form", "notice",
            "currency", "interest rate", "retention", "dispute", "arbitration"
        ]
        
        if any(keyword in text for keyword in admin_keywords):
            return False
        
        return True
    
    def _filter_scope_sources(self, scope_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter scope items to ONLY allow sources from Clause 1.2 and Drawing Schedule.
        
        Removes all items with source="inferred_list" or any other invalid source.
        """
        allowed_sources = ["works_description", "drawing_schedule"]
        filtered = []
        
        for item in scope_items:
            source = item.get("source", "")
            if source in allowed_sources:
                filtered.append(item)
            else:
                # Log removed item for debugging
                print(f"[NEC_PARSER] Removed item with invalid source '{source}': {item.get('text', '')[:50]}")
        
        return filtered
    
    def _filter_invalid_items(self, scope_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove invalid items: zero features, admin content, document metadata, TOC fragments.
        """
        filtered = []
        
        for item in scope_items:
            # Must have valid features
            if not self._has_valid_features(item):
                continue
            
            text = item.get("text", "").strip()
            if not text or len(text) < 10:
                continue
            
            # Check for document metadata
            if re.match(r'^(page|sheet|volume|part|section)\s+\d+$', text, re.IGNORECASE):
                continue
            
            # Check for TOC fragments
            if re.search(r'\.{3,}', text):  # Dots/leaders from TOC
                continue
            
            # Check for section headings only
            if re.match(r'^\d+(\.\d+)*\s+[A-Z][a-z]+(\s+[A-Z][a-z]+)*$', text):
                continue
            
            filtered.append(item)
        
        return filtered
    
    def _filter_scope_items(self, scope_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter out unwanted scope items based on source and text patterns.
        
        Removes:
        - Items with source="inferred_list" (should never happen, but double-check)
        - Items matching exclusion patterns
        - Payment, insurance, H&S, adjudicator, supervisor names
        - Contractor Data Part Two
        - Quality Statement
        - H&S questionnaire
        - TOC entries
        - Page headers/footers
        - Engineering series headings (unless table row provides scope)
        - Arbitrary fragments like "Cunard Building"
        """
        filtered = []
        
        # Exclusion patterns (case-insensitive)
        exclusion_patterns = [
            r'issued for (tender|eci|construction)',
            r'volume \d+',
            r'^series \d+',  # Series XXX unless it includes physical work
            r'^table of contents',
            r'^contents',
            r'^index',
            r'^schedule a',
            r'^schedule b',
            r'^annex [a-z]',
            r'^appendix \d+',
            r'^part [ivx]+',  # Part I, Part II, etc.
            r'^section \d+$',  # Just section numbers
            r'^page \d+$',
            r'^drawing \d+$',  # Just drawing numbers without description
            r'contractor data part two',
            r'quality statement',
            r'health and safety questionnaire',
            r'questionnaire on health',
            r'payment',
            r'insurance',
            r'adjudicator',
            r'supervisor',
            r'project manager',
            r'cdm coordinator',
            r'cunard building',  # Arbitrary fragment
            r'mercury court',  # Arbitrary fragment
            r'water street',  # Arbitrary fragment
        ]
        
        for item in scope_items:
            # STRICT: Skip inferred_list items (should never exist)
            source = item.get("source", "")
            if source == "inferred_list":
                print(f"[NEC_PARSER] REJECTED: Item with source='inferred_list': {item.get('text', '')[:50]}")
                continue
            
            # Check text against exclusion patterns
            text = item.get("text", "").strip()
            if not text:
                continue
            
            # Check if text matches exclusion patterns
            excluded = False
            for pattern in exclusion_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    # Special case: "Series XXX" is allowed if it includes physical work
                    if pattern == r'^series \d+':
                        # Check if it contains work verbs
                        work_verbs = ["construct", "install", "demolish", "build", "erect"]
                        if not any(verb in text.lower() for verb in work_verbs):
                            excluded = True
                            break
                    else:
                        excluded = True
                        break
            
            if not excluded:
                filtered.append(item)
            else:
                print(f"[NEC_PARSER] REJECTED: Item matches exclusion pattern: {text[:50]}")
        
        return filtered
    
    def _deduplicate_scope_items(self, scope_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate scope items based on normalized text."""
        seen = set()
        unique_items = []
        
        for item in scope_items:
            # Normalize text for comparison
            text = item.get("text", "").lower().strip()
            normalized = re.sub(r'[^\w\s]', '', text)
            normalized = re.sub(r'\s+', ' ', normalized)
            
            if normalized and normalized not in seen:
                seen.add(normalized)
                unique_items.append(item)
        
        return unique_items
    
    def _empty_result(self, pdf_path: str, reason: str = "") -> Dict[str, Any]:
        """Return empty result structure matching new format."""
        return {
            "contract_text": "",
            "sections": {},
            "tables": [],
            "key_dates": {},
            "constraints": {},
            "scope_items": [],
            "drawings": [],
            "milestones": [],
            "contract_dates": {
                "starting_date": "",
                "completion_date": "",
                "access_dates": [],
                "key_dates": [],
                "programme_submission_rules": "",
                "programme_revision_rules": ""
            },
            "metadata": {
                "file_name": os.path.basename(pdf_path) if pdf_path else "",
                "extraction_timestamp": datetime.now().isoformat(),
                "toc_detected": False,
                "missing_sections": ["all"],
                "error": reason,
                "total_pages": 0,
                "ocr_used": False,
                "tables_found": 0
            }
        }

