"""
Unit tests for label-based ContractDataExtractor.

Tests extraction from modern NEC4 formatted CD Part One where labels exist
but clause numbers may not.
"""

import unittest
from app.contract_parser.contract_clause_extractor import ContractDataExtractor


class TestContractDataExtractorLabelBased(unittest.TestCase):
    """Test label-based extraction from modern NEC4 format."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.extractor = ContractDataExtractor(debug=True)
    
    def test_extract_access_date(self):
        """Test extraction of Access Date."""
        text = """
Access Date
1 March 2026

Starting Date
1 April 2026
"""
        results = self.extractor.extract(text)
        
        self.assertEqual(results["dates"]["access_date"], "1 March 2026")
        self.assertEqual(results["dates"]["starting_date"], "1 April 2026")
    
    def test_extract_completion_date(self):
        """Test extraction of Completion Date."""
        text = """
Completion Date
31 March 2031

Defects Date
52 weeks after Completion
"""
        results = self.extractor.extract(text)
        
        self.assertEqual(results["dates"]["completion_date"], "31 March 2031")
        self.assertEqual(results["dates"]["defects_date"], "52 weeks after Completion")
    
    def test_extract_programme_submission_interval(self):
        """Test extraction of Programme submission interval."""
        text = """
Programme submission interval
Every 4 weeks

Period for reply to a programme submission
2 weeks
"""
        results = self.extractor.extract(text)
        
        self.assertEqual(results["programme"]["submission_interval"], "Every 4 weeks")
        self.assertEqual(results["programme"]["reply_period"], "2 weeks")
    
    def test_extract_key_dates(self):
        """Test extraction of Key Dates (multi-line text block)."""
        text = """
Key Dates
KD-01 Structural frame to Level 100 Month 30
KD-02 MEP installation complete Month 45
KD-03 Building envelope complete Month 50

Information Modelling
BIM Level 2 compliance required
"""
        results = self.extractor.extract(text)
        
        self.assertIn("KD-01", results["programme"]["key_dates"])
        self.assertIn("Structural frame", results["programme"]["key_dates"])
        self.assertIn("Month 30", results["programme"]["key_dates"])
        self.assertIn("BIM Level 2", results["programme"]["information_modelling"])
    
    def test_extract_full_contract_sample(self):
        """Test extraction from full contract sample (skyscraper contract)."""
        text = """
Access Date
1 March 2026

Starting Date
1 April 2026

Completion Date
31 March 2031

Defects Date
52 weeks after Completion

Programme submission interval
Every 4 weeks

Period for reply to a programme submission
2 weeks

Key Dates
KD-01 Structural frame to Level 100 Month 30
KD-02 MEP installation complete Month 45

Information Modelling
BIM Level 2 compliance required. All models must be submitted in IFC format.
"""
        results = self.extractor.extract(text)
        
        # Verify all expected values
        self.assertEqual(results["dates"]["access_date"], "1 March 2026")
        self.assertEqual(results["dates"]["starting_date"], "1 April 2026")
        self.assertEqual(results["dates"]["completion_date"], "31 March 2031")
        self.assertEqual(results["dates"]["defects_date"], "52 weeks after Completion")
        self.assertEqual(results["programme"]["submission_interval"], "Every 4 weeks")
        self.assertEqual(results["programme"]["reply_period"], "2 weeks")
        self.assertIn("KD-01", results["programme"]["key_dates"])
        self.assertIn("BIM Level 2", results["programme"]["information_modelling"])
    
    def test_detect_modern_format(self):
        """Test detection of modern NEC4 format."""
        # Modern format: labels exist but clause numbers are sparse
        text = """
Access Date
1 March 2026

Starting Date
1 April 2026

Completion Date
31 March 2031

Programme submission interval
Every 4 weeks
"""
        is_modern = self.extractor.has_modern_format(text)
        self.assertTrue(is_modern, "Should detect modern format when labels exist but clause numbers don't")
    
    def test_detect_legacy_format(self):
        """Test detection of legacy format (clause numbers present)."""
        # Legacy format: clause numbers present
        text = """
3.1 Starting Date
1 April 2026

3.2 Access Date
1 March 2026

3.3 Completion Date
31 March 2031
"""
        is_modern = self.extractor.has_modern_format(text)
        self.assertFalse(is_modern, "Should NOT detect modern format when clause numbers are present")
    
    def test_extract_value_stops_at_blank_line(self):
        """Test that value extraction stops at blank line."""
        text = """
Access Date
1 March 2026

Starting Date
1 April 2026
"""
        results = self.extractor.extract(text)
        
        # Access Date should only contain "1 March 2026", not "1 March 2026 Starting Date 1 April 2026"
        self.assertEqual(results["dates"]["access_date"], "1 March 2026")
        self.assertEqual(results["dates"]["starting_date"], "1 April 2026")
    
    def test_extract_multi_line_value(self):
        """Test extraction of multi-line values (e.g., Key Dates)."""
        text = """
Key Dates
KD-01 Structural frame to Level 100 Month 30
KD-02 MEP installation complete Month 45
KD-03 Building envelope complete Month 50
"""
        results = self.extractor.extract(text)
        
        key_dates = results["programme"]["key_dates"]
        self.assertIn("KD-01", key_dates)
        self.assertIn("KD-02", key_dates)
        self.assertIn("KD-03", key_dates)
        self.assertIn("Month 30", key_dates)
    
    def test_empty_text_returns_empty_results(self):
        """Test that empty text returns empty results."""
        results = self.extractor.extract("")
        
        self.assertEqual(results["dates"]["access_date"], "")
        self.assertEqual(results["dates"]["starting_date"], "")
        self.assertEqual(results["programme"]["submission_interval"], "")


if __name__ == "__main__":
    unittest.main()
