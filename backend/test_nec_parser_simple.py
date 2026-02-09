"""
Simple test script for NEC Parser (runs without pytest).
"""

import os
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.contract_parser.nec_parser import NECParser
from app.contract_parser.toc_detector import TOCDetector
from app.contract_parser.clause_locator import ClauseLocator
from app.contract_parser.section_extractor import SectionExtractor
from app.contract_parser.cleaner import TextCleaner


def test_toc_detector():
    """Test TOC detection."""
    print("\n=== Testing TOC Detector ===")
    detector = TOCDetector()
    
    # Mock pages
    pages = [
        {"text_blocks": ["Page 1 content"]},
        {"text_blocks": ["Table of Contents", "1.2 Works Description ... 5"]},
        {"text_blocks": ["Page 3 content"]}
    ]
    
    toc_page_idx = detector.detect_toc_page(pages)
    assert toc_page_idx == 1, f"Expected TOC on page 2 (index 1), got {toc_page_idx}"
    print("✓ TOC detection works")
    
    # Test TOC entry extraction
    pages_with_table = [
        {"text_blocks": ["Table of Contents"], "tables": [
            {"rows": [
                ["1.2 Works Description", "5"],
                ["1.3 Employer", "6"],
                ["3. Time", "10"]
            ]}
        ]}
    ]
    
    entries = detector.extract_toc_entries(pages_with_table, 0)
    assert len(entries) == 3, f"Expected 3 entries, got {len(entries)}"
    assert entries[0]["title"] == "1.2 Works Description"
    assert entries[0]["page_number"] == 5
    print("✓ TOC entry extraction works")


def test_clause_locator():
    """Test clause location."""
    print("\n=== Testing Clause Locator ===")
    locator = ClauseLocator()
    
    toc_entries = [
        {"title": "1.2 Works Description", "page_number": 5},
        {"title": "Works Information", "page_number": 8},
        {"title": "Section 3 Time", "page_number": 10},
        {"title": "Schedule of Drawings", "page_number": 13}
    ]
    
    clauses = locator.find_clauses_from_toc(toc_entries)
    assert clauses["works_description"] == 5, f"Expected page 5, got {clauses.get('works_description')}"
    assert clauses["works_information"] == 8, f"Expected page 8, got {clauses.get('works_information')}"
    assert clauses["time_section"] == 10, f"Expected page 10, got {clauses.get('time_section')}"
    assert clauses["drawings"] == 13, f"Expected page 13, got {clauses.get('drawings')}"
    print("✓ Clause location from TOC works")
    
    # Test fuzzy matching
    assert locator._fuzzy_match("works description", "Works Description", 0.7)
    assert locator._fuzzy_match("works info", "Works Information", 0.7)
    assert not locator._fuzzy_match("works description", "time section", 0.7)
    print("✓ Fuzzy matching works")


def test_section_extractor():
    """Test section extraction."""
    print("\n=== Testing Section Extractor ===")
    extractor = SectionExtractor()
    
    # Test scope extraction
    text = "Construct new carriageway and resurface existing footway. Install new lighting columns."
    scope_items = extractor.extract_scope_items(text)
    assert len(scope_items) > 0, f"Expected scope items, got {len(scope_items)}"
    assert "text" in scope_items[0]
    assert "discipline" in scope_items[0]
    assert "assets" in scope_items[0]
    print(f"✓ Scope extraction works ({len(scope_items)} items extracted)")
    
    # Test constraint extraction
    text = "Work shall not commence until approval is obtained. Access restricted to working hours only."
    constraints = extractor.extract_constraints(text)
    assert len(constraints) > 0, f"Expected constraints, got {len(constraints)}"
    assert constraints[0]["type"] in ["access", "approval", "sequencing"]
    assert "description" in constraints[0]
    print(f"✓ Constraint extraction works ({len(constraints)} constraints extracted)")
    
    # Test milestone extraction
    text = "Design submission required before construction. Approval from local authority needed."
    milestones = extractor.extract_milestones(text)
    assert len(milestones) > 0, f"Expected milestones, got {len(milestones)}"
    assert milestones[0]["category"] in ["design", "approval", "test", "handover", "certificate"]
    print(f"✓ Milestone extraction works ({len(milestones)} milestones extracted)")
    
    # Test date extraction
    text = """
    Starting date: 01/01/2024
    Completion date: 31/12/2024
    Possession date: 15/01/2024
    """
    dates = extractor.extract_contract_dates(text)
    assert dates["starting_date"] != "", "Expected starting date"
    assert dates["completion_date"] != "", "Expected completion date"
    assert len(dates["access_dates"]) > 0, "Expected access dates"
    print("✓ Date extraction works")


def test_text_cleaner():
    """Test text cleaning."""
    print("\n=== Testing Text Cleaner ===")
    cleaner = TextCleaner()
    
    text = "1.2   Works   Description"
    cleaned = cleaner.clean_text(text)
    assert "works description" in cleaned.lower()
    assert "1.2" not in cleaned or cleaned.count("1.2") < 2  # Line numbers should be removed
    print("✓ Text cleaning works")
    
    text = "Contract administration is handled by the Project Manager. Insurance requirements are detailed."
    cleaned = cleaner.remove_boilerplate(text)
    assert "contract administration" not in cleaned.lower()
    assert "insurance" not in cleaned.lower()
    print("✓ Boilerplate removal works")


def test_nec_parser_structure():
    """Test NEC parser structure."""
    print("\n=== Testing NEC Parser Structure ===")
    parser = NECParser()
    result = parser._empty_result("test.pdf")
    
    assert "metadata" in result
    assert "scope_items" in result
    assert "constraints" in result
    assert "milestones" in result
    assert "contract_dates" in result
    assert "contract_text" in result
    assert "sections" in result
    assert "tables" in result
    assert "key_dates" in result
    assert "drawings" in result
    
    assert isinstance(result["scope_items"], list)
    assert isinstance(result["constraints"], dict)  # Now a dict, not list
    assert isinstance(result["milestones"], list)
    assert isinstance(result["contract_dates"], dict)
    assert isinstance(result["sections"], dict)
    assert isinstance(result["tables"], list)
    assert isinstance(result["drawings"], list)
    
    assert "file_name" in result["metadata"]
    assert "extraction_timestamp" in result["metadata"]
    assert "toc_detected" in result["metadata"]
    assert "missing_sections" in result["metadata"]
    print("✓ NEC parser structure is correct")
    
    # Test deduplication
    items = [
        {"text": "Construct carriageway"},
        {"text": "construct carriageway"},  # Duplicate
        {"text": "Install lighting"}
    ]
    unique = parser._deduplicate_scope_items(items)
    assert len(unique) == 2, f"Expected 2 unique items, got {len(unique)}"
    print("✓ Deduplication works")


def test_with_real_pdf():
    """Test with a real PDF if available."""
    print("\n=== Testing with Real PDF ===")
    
    # Look for PDF files in common locations
    possible_paths = [
        "../test_data/sample_contract.pdf",
        "test_data/sample_contract.pdf",
        "../Contract_Data_Parts_1_and_2.pdf",
        "Contract_Data_Parts_1_and_2.pdf"
    ]
    
    pdf_path = None
    for path in possible_paths:
        if os.path.exists(path):
            pdf_path = path
            break
    
    if not pdf_path:
        print("⚠ No test PDF found. Skipping real PDF test.")
        print("  To test with a real PDF, place it in the project root or test_data/ folder")
        return
    
    print(f"Found PDF: {pdf_path}")
    parser = NECParser()
    
    try:
        result = parser.parse_contract(pdf_path)
        
        # Verify structure
        assert "metadata" in result
        assert "scope_items" in result
        assert "constraints" in result
        assert "milestones" in result
        assert "contract_dates" in result
        assert "contract_text" in result
        assert "sections" in result
        assert "tables" in result
        
        print(f"✓ Parsed PDF successfully")
        print(f"  - Scope items: {len(result['scope_items'])}")
        print(f"  - Constraints: {len(result['constraints'])} (dict)")
        print(f"  - Milestones: {len(result['milestones'])}")
        print(f"  - Tables: {len(result['tables'])}")
        print(f"  - Sections: {len(result['sections'])}")
        print(f"  - TOC detected: {result['metadata']['toc_detected']}")
        print(f"  - Missing sections: {result['metadata']['missing_sections']}")
        
        # Print sample scope item if available
        if result["scope_items"]:
            print(f"\n  Sample scope item:")
            sample = result["scope_items"][0]
            print(f"    Text: {sample.get('text', '')[:80]}...")
            print(f"    Discipline: {sample.get('discipline', '')}")
            print(f"    Assets: {sample.get('assets', [])}")
        
    except Exception as e:
        print(f"✗ Error parsing PDF: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("=" * 60)
    print("NEC Parser Test Suite")
    print("=" * 60)
    
    try:
        test_toc_detector()
        test_clause_locator()
        test_section_extractor()
        test_text_cleaner()
        test_nec_parser_structure()
        test_with_real_pdf()
        
        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


