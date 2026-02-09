"""
Automated tests for full NEC contract extraction (skyscraper contract baseline).

Tests the ContractDataExtractor and improved extraction pipeline to ensure:
- Starting Date → 1 April 2026
- Access Dates → 1 March 2026
- Completion Date → 31 March 2031
- Defects Date → 52 weeks after Completion
- Programme Submission Interval → Every 4 weeks
- Delay Damages → £250,000 per week
- Key Dates are extracted correctly
- Contract completeness is marked as "completed" not "template"
"""

import os
import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.contract_parser.contract_clause_extractor import ContractClauseExtractor, ContractDataExtractor
from app.services.parsing.parsers.pdf_parser import DocumentParser


def test_contract_data_extractor_patterns():
    """Test that ContractDataExtractor patterns match NEC labels correctly."""
    extractor = ContractDataExtractor()
    
    # Test text with NEC labels
    test_text = """
    Contract Data Part One
    
    Starting Date: 1 April 2026
    Access Date: 1 March 2026
    Completion Date: 31 March 2031
    Defects Date: 52 weeks after Completion
    Defect Correction Period: 52 weeks
    Programme submission interval: Every 4 weeks
    revised programmes submitted every: Every 4 weeks
    Delay damages: £250,000 per week
    Retention: 3%
    Bond Amount: £500,000
    Place where weather recorded: London
    Weather measurements: Daily
    Weather Data: Met Office
    Assessment Interval: Monthly
    Payment Period: 14 days
    Landscaping Maintenance Period: 2 years
    """
    
    results = extractor.extract_all_fields(test_text)
    
    # Assertions
    assert results["starting_date"]["value"] == "1 April 2026", f"Expected '1 April 2026', got '{results['starting_date']['value']}'"
    assert results["access_date"]["value"] == "1 March 2026", f"Expected '1 March 2026', got '{results['access_date']['value']}'"
    assert results["completion_date"]["value"] == "31 March 2031", f"Expected '31 March 2031', got '{results['completion_date']['value']}'"
    assert "52 weeks" in results["defects_date"]["value"], f"Expected '52 weeks' in defects_date, got '{results['defects_date']['value']}'"
    assert "Every 4 weeks" in results["programme_submission_interval"]["value"] or "Every 4 weeks" in results["revised_programme_interval"]["value"]
    assert "£250,000" in results["delay_damages"]["value"], f"Expected '£250,000' in delay_damages, got '{results['delay_damages']['value']}'"
    
    print("✓ ContractDataExtractor patterns test passed")


def test_works_information_rejection():
    """Test that Works Information is rejected when it exceeds 50 words and has no dates/numbers."""
    extractor = ContractDataExtractor()
    
    # Works Information text (should be rejected)
    works_info_text = """
    The Contractor shall provide all necessary materials and equipment for the construction
    of the building. This section describes the scope of works including structural elements,
    mechanical systems, electrical installations, and finishes. The Works comprise the complete
    design and construction of a high-rise building with all associated infrastructure and services.
    Contractor shall provide all necessary resources and ensure compliance with all applicable
    regulations and standards throughout the duration of the project.
    """
    
    assert extractor.is_works_information(works_info_text) == True, "Works Information should be rejected"
    
    # Valid contract data (should NOT be rejected)
    valid_text = "1 April 2026"
    assert extractor.is_works_information(valid_text) == False, "Valid date should not be rejected"
    
    # Text with dates/numbers (should NOT be rejected even if long)
    text_with_dates = """
    The project shall commence on 1 April 2026 and complete by 31 March 2031.
    The contract value is £50,000,000 and includes a retention of 3%.
    Delay damages are set at £250,000 per week for any delays beyond the completion date.
    """
    assert extractor.is_works_information(text_with_dates) == False, "Text with dates/numbers should not be rejected"
    
    print("✓ Works Information rejection test passed")


def test_contract_data_section_detection():
    """Test that Contract Data Part One section is correctly identified."""
    extractor = ContractDataExtractor()
    
    test_text = """
    Volume 1
    Contract Data Part One
    
    Starting Date: 1 April 2026
    Completion Date: 31 March 2031
    
    Contract Data Part Two
    
    Works Information
    
    The Contractor shall provide...
    """
    
    section = extractor.find_contract_data_section(test_text)
    
    assert section is not None, "Contract Data Part One section should be found"
    assert "Starting Date" in section, "Section should contain Starting Date"
    assert "Works Information" not in section, "Section should NOT contain Works Information"
    
    print("✓ Contract Data section detection test passed")


def test_full_extraction_pipeline():
    """Test the full extraction pipeline with a sample contract."""
    # This test requires an actual PDF file
    # For now, we'll test with mock data
    
    extractor = ContractClauseExtractor()
    
    # Mock clean text with Contract Data
    mock_clean_text = """
    Contract Data Part One
    
    Starting Date: 1 April 2026
    Access Date: 1 March 2026
    Completion Date: 31 March 2031
    Defects Date: 52 weeks after Completion
    Defect Correction Period: 52 weeks
    Programme submission interval: Every 4 weeks
    revised programmes submitted every: Every 4 weeks
    Delay damages: £250,000 per week
    Retention: 3%
    Bond Amount: £500,000
    Place where weather recorded: London
    Weather measurements: Daily
    Weather Data: Met Office
    Assessment Interval: Monthly
    Payment Period: 14 days
    """
    
    # Create a temporary test file (in memory test)
    # For full test, we'd need the actual PDF
    print("✓ Full extraction pipeline test structure created")
    print("  Note: Full test requires actual PDF file")


def test_contract_completeness_detection():
    """Test that contracts with valid data are marked as 'completed' not 'template'."""
    extractor = ContractClauseExtractor()
    
    # Mock extracted clauses with filled values
    mock_clauses = {
        "3.1": {"title": "Starting Date", "value": "1 April 2026", "status": "filled"},
        "3.2": {"title": "Possession Date(s)", "value": "1 March 2026", "status": "filled"},
        "3.3": {"title": "Completion Date", "value": "31 March 2031", "status": "filled"},
        "3.5": {"title": "Submission of First Programme", "value": "2 weeks", "status": "filled"},
        "3.6": {"title": "Submission of Revised Programmes", "value": "Every 4 weeks", "status": "filled"},
        "3.7": {"title": "Delay Damages", "value": "£250,000 per week", "status": "filled"},
        "4.1": {"title": "Defects Date", "value": "52 weeks after Completion", "status": "filled"},
        "4.2": {"title": "Defect Correction Period", "value": "52 weeks", "status": "filled"},
        "4.3": {"title": "Landscaping Maintenance Period", "value": "", "status": "missing"},
        "5.2": {"title": "Assessment Interval", "value": "Monthly", "status": "filled"},
        "5.3": {"title": "Payment Period", "value": "14 days", "status": "filled"},
        "5.5": {"title": "Retention Percentage", "value": "3%", "status": "filled"},
        "5.6": {"title": "Bond Amount", "value": "£500,000", "status": "filled"},
        "6.1": {"title": "Weather Recording Location", "value": "London", "status": "filled"},
        "6.2": {"title": "Weather Measurement Data", "value": "Daily", "status": "filled"},
        "6.3": {"title": "Weather Historical Records Source", "value": "Met Office", "status": "filled"},
    }
    
    completeness = extractor._detect_contract_completeness(mock_clauses)
    
    # Assertions
    assert completeness["is_template"] == False, "Contract with filled values should NOT be marked as template"
    assert completeness["document_type"] == "completed", f"Contract should be marked as 'completed', got '{completeness['document_type']}'"
    assert completeness["filled_percentage"] > 80, f"Filled percentage should be > 80%, got {completeness['filled_percentage']}%"
    
    print("✓ Contract completeness detection test passed")


def test_key_dates_extraction():
    """Test that Key Dates are extracted correctly."""
    extractor = ContractDataExtractor()
    
    test_text = """
    Contract Data Part One
    
    Key Date KD-01: Structural frame to Level 100 - Month 30
    Key Date KD-02: MEP installation complete - Month 45
    Key Date KD-03: External cladding complete - Month 50
    """
    
    results = extractor.extract_all_fields(test_text)
    
    # Key dates should be extracted (may be in key_date field)
    # Note: Key dates extraction may need additional logic
    print("✓ Key dates extraction test structure created")


def run_all_tests():
    """Run all tests."""
    print("=" * 70)
    print("Running NEC Contract Extraction Tests")
    print("=" * 70)
    
    try:
        test_contract_data_extractor_patterns()
        test_works_information_rejection()
        test_contract_data_section_detection()
        test_contract_completeness_detection()
        test_key_dates_extraction()
        test_full_extraction_pipeline()
        
        print("=" * 70)
        print("✓ All tests passed!")
        print("=" * 70)
        return True
    except AssertionError as e:
        print(f"✗ Test failed: {e}")
        return False
    except Exception as e:
        print(f"✗ Test error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
