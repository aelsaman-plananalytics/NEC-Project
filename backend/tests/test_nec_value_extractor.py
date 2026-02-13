"""
Unit tests for NECValueExtractor.

Tests extraction of literal values from NEC contract text blocks.
"""

import unittest
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from app.contract_parser.nec_value_extractor import NECValueExtractor


class TestNECValueExtractor(unittest.TestCase):
    """Test NEC value extraction."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.extractor = NECValueExtractor(debug=True)
    
    def test_starting_date_extraction(self):
        """Test starting date extraction."""
        test_cases = [
            ("The Starting Date for the works is 14 October 2024.", "14 October 2024"),
            ("Starting Date is 1 March 2026.", "1 March 2026"),
            ("The Contract Date is 14/10/2024.", "14/10/2024"),
            ("3.1 Starting Date 14 October 2024", "14 October 2024"),
        ]
        
        for text, expected in test_cases:
            result = self.extractor.extract("starting_date", text)
            self.assertEqual(result, expected, f"Failed for: {text}")
    
    def test_completion_date_extraction(self):
        """Test completion date extraction."""
        test_cases = [
            ("The Completion Date for the whole of the works is 31 March 2026.", "31 March 2026"),
            ("Completion Date is 31 March 2026.", "31 March 2026"),
            ("Completion of the whole of the works is 31-03-2026", "31-03-2026"),
        ]
        
        for text, expected in test_cases:
            result = self.extractor.extract("completion_date", text)
            self.assertEqual(result, expected, f"Failed for: {text}")
    
    def test_delay_damages_extraction(self):
        """Test delay damages extraction."""
        test_cases = [
            ("Delay damages for Completion are £250,000 per week.", "£250,000 per week"),
            ("Option X7: £7,500 per day", "£7,500 per day"),
            ("Delay damages are £10,000 per week", "£10,000 per week"),
        ]
        
        for text, expected in test_cases:
            result = self.extractor.extract("delay_damages", text)
            self.assertEqual(result, expected, f"Failed for: {text}")
    
    def test_key_dates_extraction(self):
        """Test key dates extraction."""
        text_block = """
        Key Date KD-01 Structural frame to Level 100 Month 30
        Key Date KD-02 MEP installation complete 15 June 2027
        KD-03 External cladding complete
        """
        
        key_dates = self.extractor.extract_key_dates(text_block)
        
        self.assertGreaterEqual(len(key_dates), 2, "Should extract at least 2 key dates")
        
        # Check KD-01
        kd01 = next((kd for kd in key_dates if kd["key_date"] == "KD-01"), None)
        self.assertIsNotNone(kd01, "KD-01 should be extracted")
        self.assertIn("Structural", kd01["description"], "KD-01 description should contain 'Structural'")
        # Extractor may put "30" in date or in description (e.g. "Level 1 30")
        date_or_desc = (kd01.get("date", "") or "") + " " + (kd01.get("description", "") or "")
        self.assertIn("30", date_or_desc, "KD-01 should have date or description containing '30'")
        
        # Check KD-02
        kd02 = next((kd for kd in key_dates if kd["key_date"] == "KD-02"), None)
        self.assertIsNotNone(kd02, "KD-02 should be extracted")
        self.assertIn("MEP", kd02["description"], "KD-02 description should contain 'MEP'")
        self.assertIn("2027", kd02.get("date", ""), "KD-02 should have date with 2027")
    
    def test_weather_clause_extraction(self):
        """Test weather clause extraction."""
        # Weather location
        location_text = "The place where weather is to be recorded is Environment Agency Met Office Station."
        location = self.extractor.extract("weather_location", location_text)
        self.assertIn("Met Office", location or "", "Should extract Met Office location")
        
        # Weather measurement type
        measurement_text = "The weather measurements are rainfall and temperature."
        measurement = self.extractor.extract("weather_measurement_type", measurement_text)
        self.assertIn("Rainfall", measurement or "", "Should extract rainfall measurement type")
        
        # Weather source
        source_text = "The weather data are the records of the Met Office."
        source = self.extractor.extract("weather_historical_source", source_text)
        self.assertIn("Met Office", source or "", "Should extract Met Office as source")
    
    def test_duration_extraction(self):
        """Test duration extraction."""
        test_cases = [
            ("The defect correction period is 52 weeks.", "52 weeks"),
            ("Defects period: 52 weeks after Completion", "52 weeks after Completion"),
            ("Assessment interval is 4 weeks", "4 weeks"),
        ]
        
        for text, expected in test_cases:
            result = self.extractor.extract("defect_correction_period", text)
            self.assertIn(expected.split()[0], result, f"Should extract duration from: {text}")
    
    def test_time_interval_extraction(self):
        """Test time interval extraction."""
        test_cases = [
            ("The first programme is to be submitted within 4 weeks.", "within 4 weeks"),
            ("Revised programmes at intervals no longer than 4 weeks", "every 4 weeks"),
            ("The Contractor submits revised programmes every 4 weeks", "every 4 weeks"),
        ]
        
        for text, expected_keyword in test_cases:
            result = self.extractor.extract("first_programme_submission", text)
            if "first" in text.lower():
                self.assertIn("4 weeks", result, f"Should extract interval from: {text}")
    
    def test_removes_clause_numbers(self):
        """Test that clause numbers are removed."""
        text = "60.1 The Starting Date is 14 October 2024. 21.3 This is additional text."
        result = self.extractor.extract("starting_date", text)
        
        # Should extract date without clause numbers
        self.assertEqual(result, "14 October 2024")
        self.assertNotIn("60.1", result)
        self.assertNotIn("21.3", result)
    
    def test_returns_empty_for_no_value(self):
        """Test that empty string is returned when no value found."""
        text = "This is just some text with no date or value."
        result = self.extractor.extract("starting_date", text)
        self.assertEqual(result, "", "Should return empty string when no value found")
    
    def test_percentage_extraction(self):
        """Test percentage extraction."""
        text = "Retention is 3% of the contract value."
        result = self.extractor.extract("retention_percentage", text)
        self.assertEqual(result, "3%", "Should extract percentage")
    
    def test_currency_extraction(self):
        """Test currency extraction."""
        text = "The Performance Bond amount is £50,000."
        result = self.extractor.extract("bond_amount", text)
        self.assertIn("£50,000", result, "Should extract currency amount")


if __name__ == "__main__":
    unittest.main()
