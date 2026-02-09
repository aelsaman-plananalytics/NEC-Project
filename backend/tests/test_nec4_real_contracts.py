"""
Tests for NEC4 Contract Data Part One extraction on real EA contracts.

Tests extraction from:
- Anderby Creek Piling NEC4 ECC
- Addingham Lower Gauge Fish Pass NEC4 ECC
- KSL Rec Package NEC4 ECC

Validates that at least 12 key fields are extracted correctly.
"""

import os
import sys
import unittest
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from app.contract_parser.nec4_cd_part_one_extractor import NEC4CDPartOneExtractor
from app.services.parsing.parsers.pdf_parser import DocumentParser


class TestNEC4RealContracts(unittest.TestCase):
    """Test NEC4 extraction on real EA contracts."""
    
    # Required fields that must be extracted
    REQUIRED_FIELDS = [
        "starting_date",
        "access_date",
        "completion_date",
        "submit_first_programme_within",
        "revised_programme_interval",
        "assessment_interval",
        "payment_period",
        "defects_date",
        "defect_correction_period",
        "weather_recording_location",
        "weather_measurement_data",
        "weather_historical_records_source",
    ]
    
    def setUp(self):
        """Set up test fixtures."""
        self.extractor = NEC4CDPartOneExtractor(debug=True)
        
        # Paths to test contracts (adjust as needed)
        self.test_contracts_dir = Path(__file__).parent.parent.parent / "test_contracts"
        
        # Contract file names (adjust based on actual file names)
        self.contracts = {
            "anderby_creek": self.test_contracts_dir / "Anderby_Creek_Piling_NEC4_ECC.pdf",
            "addingham": self.test_contracts_dir / "Addingham_Lower_Gauge_Fish_Pass_NEC4_ECC.pdf",
            "ksl_rec": self.test_contracts_dir / "KSL_Rec_Package_NEC4_ECC.pdf",
        }
    
    def _extract_from_pdf(self, pdf_path: Path) -> dict:
        """Extract Contract Data Part One from PDF."""
        if not pdf_path.exists():
            self.skipTest(f"Contract file not found: {pdf_path}")
        
        # Extract clean text
        clean_text = DocumentParser.extract_clean_text(str(pdf_path))
        self.assertGreater(len(clean_text), 0, "Failed to extract text from PDF")
        
        # Extract Contract Data Part One
        result = self.extractor.extract(clean_text)
        return result
    
    def _validate_extraction(self, result: dict, contract_name: str):
        """Validate that extraction contains required fields."""
        extracted_fields = result.get("extracted_fields", {})
        
        # Check that at least 12 key fields are present
        found_fields = []
        for field_name in self.REQUIRED_FIELDS:
            if field_name in extracted_fields:
                field_data = extracted_fields[field_name]
                status = field_data.get("status", "missing")
                value = field_data.get("value", "")
                
                if status == "filled":
                    found_fields.append(field_name)
                    self.assertGreater(
                        len(value), 0,
                        f"{contract_name}: Field {field_name} marked as filled but value is empty"
                    )
                elif status == "blank":
                    found_fields.append(field_name)
                    # Blank is acceptable (label found but no value)
        
        # Assert that at least 12 fields were found (filled or blank)
        self.assertGreaterEqual(
            len(found_fields), 12,
            f"{contract_name}: Expected at least 12 fields, found {len(found_fields)}. "
            f"Found: {found_fields}"
        )
        
        # Validate completeness
        completeness = result.get("completeness", {})
        self.assertIn("document_type", completeness)
        self.assertIn("filled_percentage", completeness)
        self.assertIn("is_template", completeness)
        
        # For real contracts, should not be marked as template
        if len(found_fields) >= 12:
            self.assertFalse(
                completeness.get("is_template", True),
                f"{contract_name}: Real contract should not be marked as template"
            )
    
    def test_anderby_creek_extraction(self):
        """Test extraction from Anderby Creek Piling NEC4 ECC."""
        pdf_path = self.contracts["anderby_creek"]
        result = self._extract_from_pdf(pdf_path)
        self._validate_extraction(result, "Anderby Creek")
        
        # Validate specific fields
        contract_dates = result.get("contract_dates", {})
        self.assertIn("starting_date", contract_dates)
        self.assertIn("completion_date", contract_dates)
        
        programme_requirements = result.get("programme_requirements", {})
        self.assertIn("submit_first_programme_within", programme_requirements)
    
    def test_addingham_extraction(self):
        """Test extraction from Addingham Lower Gauge Fish Pass NEC4 ECC."""
        pdf_path = self.contracts["addingham"]
        result = self._extract_from_pdf(pdf_path)
        self._validate_extraction(result, "Addingham")
        
        # Validate specific fields
        contract_dates = result.get("contract_dates", {})
        self.assertIn("starting_date", contract_dates)
        self.assertIn("completion_date", contract_dates)
        
        payment_terms = result.get("payment_terms", {})
        self.assertIn("assessment_interval", payment_terms)
    
    def test_ksl_rec_extraction(self):
        """Test extraction from KSL Rec Package NEC4 ECC."""
        pdf_path = self.contracts["ksl_rec"]
        result = self._extract_from_pdf(pdf_path)
        self._validate_extraction(result, "KSL Rec")
        
        # Validate specific fields
        weather_data = result.get("weather_data", {})
        self.assertIn("recording_location", weather_data)
        self.assertIn("measurement_data", weather_data)
    
    def test_no_clause_numbers_in_extraction(self):
        """Test that extraction does not use clause numbers (3.1, 3.2, etc.)."""
        # Test with sample text containing NEC4 labels
        sample_text = """
        The starting date is 28 March 2023.
        The access date is 1 April 2023.
        The Completion Date for the whole of the works is 31 December 2024.
        The period after the Contract Date within which the Contractor is to submit a first programme is 2 weeks.
        """
        
        result = self.extractor.extract(sample_text)
        extracted_fields = result.get("extracted_fields", {})
        
        # Should extract fields by label, not clause number
        self.assertIn("starting_date", extracted_fields)
        self.assertIn("access_date", extracted_fields)
        self.assertIn("completion_date", extracted_fields)
        self.assertIn("submit_first_programme_within", extracted_fields)
        
        # Should NOT have clause numbers as keys
        self.assertNotIn("3.1", extracted_fields)
        self.assertNotIn("3.2", extracted_fields)
        self.assertNotIn("3.3", extracted_fields)


if __name__ == "__main__":
    unittest.main()
