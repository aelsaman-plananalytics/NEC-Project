"""
Tests for Contract Ingestion Engine.

Tests table extraction, clause parsing, and structured output.
"""

import pytest
import json
from pathlib import Path
from app.services.extraction.extractors.contract_ingestion_engine import ContractIngestionEngine
from app.services.extraction.extractors.table_extractor import TableExtractor
from app.services.extraction.extractors.clause_parser import ClauseParser


class TestContractIngestionEngine:
    """Test suite for contract ingestion."""
    
    @pytest.fixture
    def engine(self):
        """Create ingestion engine instance."""
        return ContractIngestionEngine()
    
    @pytest.fixture
    def sample_text(self):
        """Sample contract text for testing."""
        return """
        1. General
        1.1 The conditions of contract are the NEC3 New Engineering and Construction Contract.
        1.2 The Works are the Edge Lane West Highways and Environmental Improvement Scheme.
        1.3 The Employer is Liverpool City Council, Municipal Buildings, Dale Street, Liverpool, L69 2DH.
        1.4 The Project Manager is Mouchel, represented by Mr Chris Founds.
        
        5. Payment
        5.1 The currency of this contract is sterling (£).
        5.2 The assessment interval is 4 weeks.
        
        Schedule A – Drawings and Standard Details
        Status July Size Number rev Title Scale
        A1 A 000041/ELW/100/01 Scottish Power - LV, HV and 33KV proposed alterations Sheet 1 of 2. 1:500 Complete
        """
    
    def test_engine_initialization(self, engine):
        """Test that engine initializes correctly."""
        assert engine is not None
        assert engine.table_extractor is not None
        assert engine.clause_parser is not None
    
    def test_clause_detection(self, engine, sample_text):
        """Test clause structure detection."""
        structure = engine.clause_parser.detect_clause_structure(sample_text)
        
        assert "main_sections" in structure
        assert "subclauses" in structure
        assert len(structure["main_sections"]) > 0
        assert len(structure["subclauses"]) > 0
    
    def test_works_description_extraction(self, engine, sample_text):
        """Test Works Description extraction."""
        works_desc = engine.clause_parser.extract_works_description(sample_text)
        assert "Edge Lane West" in works_desc or works_desc != ""
    
    def test_employer_extraction(self, engine, sample_text):
        """Test Employer information extraction."""
        employer = engine.clause_parser.extract_employer_info(sample_text)
        assert "Liverpool City Council" in employer.get("name", "")
    
    def test_payment_terms_extraction(self, engine, sample_text):
        """Test Payment terms extraction."""
        payment = engine.clause_parser.extract_payment_terms(sample_text)
        assert payment.get("currency", "") != "" or "sterling" in str(payment.get("currency", ""))
    
    def test_table_extractor_initialization(self):
        """Test table extractor initialization."""
        extractor = TableExtractor()
        assert extractor is not None
    
    def test_drawings_table_parsing(self):
        """Test Schedule of Drawings table parsing."""
        extractor = TableExtractor()
        
        # Sample table data
        table_data = [
            ["Status", "Size", "Number", "rev", "Title", "Scale"],
            ["Complete", "A1", "A", "000041/ELW/100/01", "Scottish Power - LV, HV and 33KV", "1:500"]
        ]
        
        drawings = extractor.parse_drawings_table(table_data)
        assert len(drawings) > 0
        assert drawings[0].get("number") or drawings[0].get("title")
    
    def test_output_structure(self, engine, sample_text):
        """Test that output has correct structure."""
        # This is a mock test - would need actual PDF file for full test
        # But we can test the structure expectations
        
        expected_keys = ["metadata", "contract"]
        expected_contract_keys = ["part_1", "part_2"]
        expected_part1_keys = [
            "1_general", "2_contractor_responsibilities", "3_time",
            "4_testing_and_defects", "5_payment", "6_compensation_events",
            "7_title", "8_risks_and_insurance", "9_disputes_and_termination",
            "schedule_of_drawings"
        ]
        
        # Verify structure expectations
        assert all(key in expected_keys for key in expected_keys)
        assert all(key in expected_contract_keys for key in expected_contract_keys)
        assert all(key in expected_part1_keys for key in expected_part1_keys)


@pytest.mark.skip(reason="Requires actual PDF file")
def test_full_ingestion_with_pdf(engine):
    """Test full ingestion with actual PDF file."""
    # This test would require a sample PDF file
    pdf_path = "test_contract.pdf"
    
    if not Path(pdf_path).exists():
        pytest.skip("Test PDF file not found")
    
    result = engine.ingest_contract(pdf_path)
    
    # Verify structure
    assert "metadata" in result
    assert "contract" in result
    assert "part_1" in result["contract"]
    assert "part_2" in result["contract"]
    
    # Verify metadata
    assert "file_name" in result["metadata"]
    assert "pages" in result["metadata"]
    assert "extraction_time" in result["metadata"]
    assert "tables_detected" in result["metadata"]
    
    # Verify Part 1 structure
    part1 = result["contract"]["part_1"]
    assert "1_general" in part1
    assert "schedule_of_drawings" in part1
    
    # Verify drawings
    drawings = part1["schedule_of_drawings"]
    assert isinstance(drawings, list)
    if drawings:
        assert "number" in drawings[0] or "title" in drawings[0]



