"""
Test suite for NEC Contract Parser.

Tests TOC detection, clause matching, scope extraction, constraint extraction,
date parsing, milestone detection, and output structure correctness.
"""

import pytest
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.contract_parser.nec_parser import NECParser
from app.contract_parser.toc_detector import TOCDetector
from app.contract_parser.clause_locator import ClauseLocator
from app.contract_parser.section_extractor import SectionExtractor
from app.contract_parser.cleaner import TextCleaner


class TestTOCDetector:
    """Test TOC detection functionality."""
    
    def test_detect_toc_page(self):
        """Test TOC page detection."""
        detector = TOCDetector()
        
        # Mock pages
        pages = [
            {"text_blocks": ["Page 1 content"]},
            {"text_blocks": ["Table of Contents", "1.2 Works Description ... 5"]},
            {"text_blocks": ["Page 3 content"]}
        ]
        
        toc_page_idx = detector.detect_toc_page(pages)
        assert toc_page_idx == 1, "Should detect TOC on page 2 (index 1)"
    
    def test_extract_toc_entries(self):
        """Test TOC entry extraction."""
        detector = TOCDetector()
        
        pages = [
            {"text_blocks": ["Table of Contents"], "tables": [
                {"rows": [
                    ["1.2 Works Description", "5"],
                    ["1.3 Employer", "6"],
                    ["3. Time", "10"]
                ]}
            ]}
        ]
        
        entries = detector.extract_toc_entries(pages, 0)
        assert len(entries) == 3, "Should extract 3 TOC entries"
        assert entries[0]["title"] == "1.2 Works Description"
        assert entries[0]["page_number"] == 5


class TestClauseLocator:
    """Test clause location functionality."""
    
    def test_find_clauses_from_toc(self):
        """Test clause finding from TOC."""
        locator = ClauseLocator()
        
        toc_entries = [
            {"title": "1.2 Works Description", "page_number": 5},
            {"title": "Works Information", "page_number": 8},
            {"title": "Section 3 Time", "page_number": 10},
            {"title": "Schedule of Drawings", "page_number": 13}
        ]
        
        clauses = locator.find_clauses_from_toc(toc_entries)
        assert clauses["works_description"] == 5
        assert clauses["works_information"] == 8
        assert clauses["time_section"] == 10
        assert clauses["drawings"] == 13
    
    def test_fuzzy_match(self):
        """Test fuzzy string matching."""
        locator = ClauseLocator()
        
        assert locator._fuzzy_match("works description", "Works Description", 0.7)
        assert locator._fuzzy_match("works info", "Works Information", 0.7)
        assert not locator._fuzzy_match("works description", "time section", 0.7)


class TestSectionExtractor:
    """Test section extraction functionality."""
    
    def test_extract_scope_items(self):
        """Test scope item extraction."""
        extractor = SectionExtractor()
        
        text = "Construct new carriageway and resurface existing footway. Install new lighting columns."
        scope_items = extractor.extract_scope_items(text)
        
        assert len(scope_items) > 0, "Should extract scope items"
        assert "text" in scope_items[0]
        assert "discipline" in scope_items[0]
        assert "assets" in scope_items[0]
    
    def test_extract_constraints(self):
        """Test constraint extraction."""
        extractor = SectionExtractor()
        
        text = "Work shall not commence until approval is obtained. Access restricted to working hours only."
        constraints = extractor.extract_constraints(text)
        
        assert len(constraints) > 0, "Should extract constraints"
        assert constraints[0]["type"] in ["access", "approval", "sequencing"]
        assert "description" in constraints[0]
    
    def test_extract_milestones(self):
        """Test milestone extraction."""
        extractor = SectionExtractor()
        
        text = "Design submission required before construction. Approval from local authority needed."
        milestones = extractor.extract_milestones(text)
        
        assert len(milestones) > 0, "Should extract milestones"
        assert milestones[0]["category"] in ["design", "approval", "test", "handover", "certificate"]
    
    def test_extract_contract_dates(self):
        """Test contract date extraction."""
        extractor = SectionExtractor()
        
        text = """
        Starting date: 01/01/2024
        Completion date: 31/12/2024
        Possession date: 15/01/2024
        """
        dates = extractor.extract_contract_dates(text)
        
        assert dates["starting_date"] != ""
        assert dates["completion_date"] != ""
        assert len(dates["possession_dates"]) > 0


class TestTextCleaner:
    """Test text cleaning functionality."""
    
    def test_clean_text(self):
        """Test text cleaning."""
        cleaner = TextCleaner()
        
        text = "1.2   Works   Description"
        cleaned = cleaner.clean_text(text)
        
        assert "works description" in cleaned.lower()
        assert "1.2" not in cleaned  # Line numbers removed
    
    def test_remove_boilerplate(self):
        """Test boilerplate removal."""
        cleaner = TextCleaner()
        
        text = "Contract administration is handled by the Project Manager. Insurance requirements are detailed."
        cleaned = cleaner.remove_boilerplate(text)
        
        assert "contract administration" not in cleaned.lower()
        assert "insurance" not in cleaned.lower()


class TestNECParser:
    """Test main NEC parser."""
    
    def test_empty_result_structure(self):
        """Test that empty result has correct structure."""
        parser = NECParser()
        result = parser._empty_result("test.pdf")
        
        assert "metadata" in result
        assert "scope_items" in result
        assert "constraints" in result
        assert "milestones" in result
        assert "contract_dates" in result
        
        assert isinstance(result["scope_items"], list)
        assert isinstance(result["constraints"], list)
        assert isinstance(result["milestones"], list)
        assert isinstance(result["contract_dates"], dict)
        
        assert "file_name" in result["metadata"]
        assert "extraction_timestamp" in result["metadata"]
        assert "toc_detected" in result["metadata"]
        assert "missing_sections" in result["metadata"]
    
    def test_deduplicate_scope_items(self):
        """Test scope item deduplication."""
        parser = NECParser()
        
        items = [
            {"text": "Construct carriageway"},
            {"text": "construct carriageway"},  # Duplicate (case-insensitive)
            {"text": "Install lighting"}
        ]
        
        unique = parser._deduplicate_scope_items(items)
        assert len(unique) == 2, "Should remove duplicate"


@pytest.mark.skipif(
    not os.path.exists("test_data/sample_contract.pdf"),
    reason="Test PDF file not found"
)
class TestNECParserIntegration:
    """Integration tests with real PDF (if available)."""
    
    def test_parse_real_contract(self):
        """Test parsing a real contract PDF."""
        pdf_path = "test_data/sample_contract.pdf"
        
        if not os.path.exists(pdf_path):
            pytest.skip("Test PDF not available")
        
        parser = NECParser()
        result = parser.parse_contract(pdf_path)
        
        # Verify structure
        assert "metadata" in result
        assert "scope_items" in result
        assert "constraints" in result
        assert "milestones" in result
        assert "contract_dates" in result
        
        # Verify metadata
        assert result["metadata"]["file_name"] == os.path.basename(pdf_path)
        assert "extraction_timestamp" in result["metadata"]
        assert isinstance(result["metadata"]["toc_detected"], bool)
        assert isinstance(result["metadata"]["missing_sections"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


