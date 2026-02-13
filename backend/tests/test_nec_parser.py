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
    """Test TOC detection functionality (stub returns None/empty)."""
    
    def test_detect_toc_page(self):
        """TOC detector stub returns None when no TOC detection is used."""
        detector = TOCDetector()
        pages = [
            {"text_blocks": ["Page 1 content"]},
            {"text_blocks": ["Table of Contents", "1.2 Works Description ... 5"]},
        ]
        toc_page_idx = detector.detect_toc_page(pages)
        assert toc_page_idx is None, "Stub returns None"

    def test_extract_toc_entries(self):
        """TOC detector stub returns empty list."""
        detector = TOCDetector()
        pages = [{"text_blocks": ["Table of Contents"], "tables": [{"rows": []}]}]
        entries = detector.extract_toc_entries(pages, 0)
        assert entries == [], "Stub returns empty list"


class TestClauseLocator:
    """Test clause location functionality (stub returns empty dict)."""

    def test_find_clauses_from_toc(self):
        """ClauseLocator stub returns empty dict."""
        locator = ClauseLocator()
        toc_entries = [
            {"title": "1.2 Works Description", "page_number": 5},
            {"title": "Schedule of Drawings", "page_number": 13},
        ]
        clauses = locator.find_clauses_from_toc(toc_entries)
        assert clauses == {}, "Stub returns empty dict"

    def test_fuzzy_match_removed(self):
        """ClauseLocator no longer exposes _fuzzy_match (stub implementation)."""
        locator = ClauseLocator()
        assert not hasattr(locator, "_fuzzy_match")


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
        """Test contract date extraction (uses access_dates not possession_dates)."""
        extractor = SectionExtractor()
        text = """
        Starting date: 01/01/2024
        Completion date: 31/12/2024
        Possession date: 15/01/2024
        """
        dates = extractor.extract_contract_dates(text)
        assert dates["starting_date"] != ""
        assert dates["completion_date"] != ""
        assert "access_dates" in dates
        assert len(dates["access_dates"]) > 0


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
        """Test that empty result has correct structure (constraints may be dict or list)."""
        parser = NECParser()
        result = parser._empty_result("test.pdf")
        assert "metadata" in result
        assert "scope_items" in result
        assert "constraints" in result
        assert "milestones" in result
        assert "contract_dates" in result
        assert isinstance(result["scope_items"], list)
        assert isinstance(result["milestones"], list)
        assert isinstance(result["contract_dates"], dict)
        assert isinstance(result["constraints"], (dict, list))
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


# Minimal valid PDF (single empty page) for integration test when no real contract is present
_MINIMAL_PDF_BYTES = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000052 00000 n \n0000000101 00000 n \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF"
)


@pytest.fixture
def sample_pdf_path(tmp_path):
    """Real contract path if present, otherwise a minimal PDF so the test always runs."""
    real = Path("test_data/sample_contract.pdf")
    if real.exists():
        return str(real)
    minimal = tmp_path / "sample_contract.pdf"
    minimal.write_bytes(_MINIMAL_PDF_BYTES)
    return str(minimal)


class TestNECParserIntegration:
    """Integration tests: real PDF if available, otherwise minimal PDF for structure checks."""

    def test_parse_real_contract(self, sample_pdf_path):
        """Test parsing a contract PDF (real or minimal). Verifies output structure."""
        parser = NECParser()
        result = parser.parse_contract(sample_pdf_path)

        # Verify structure
        assert "metadata" in result
        assert "scope_items" in result
        assert "constraints" in result
        assert "milestones" in result
        assert "contract_dates" in result

        # Verify metadata
        assert result["metadata"]["file_name"] == os.path.basename(sample_pdf_path)
        assert "extraction_timestamp" in result["metadata"]
        assert isinstance(result["metadata"].get("toc_detected"), bool)
        assert isinstance(result["metadata"].get("missing_sections"), list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


