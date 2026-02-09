"""
NEC Contract Schema Definitions.

Defines the structure for extracted NEC contract data.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ClauseData:
    """Data structure for a single NEC clause."""
    clause_number: str
    title: str
    value: str
    status: str  # "filled", "blank", or "missing"
    confidence: float  # 0.0 to 1.0
    page: Optional[int] = None
    source: Optional[str] = None  # "toc", "table", "text", "llm"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "clause_number": self.clause_number,
            "title": self.title,
            "value": self.value,
            "status": self.status,
            "confidence": self.confidence,
            "page": self.page,
            "source": self.source,
        }


@dataclass
class ContractCompleteness:
    """Contract completeness assessment."""
    document_type: str  # "template", "partial", "complete"
    is_template: bool
    filled_percentage: float
    blank_percentage: float
    mandatory_missing: int
    total_mandatory: int
    mandatory_filled: int
    mandatory_blank: int
    missing_fields: List[str] = field(default_factory=list)
    blank_fields: List[str] = field(default_factory=list)
    filled_fields: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "document_type": self.document_type,
            "is_template": self.is_template,
            "filled_percentage": self.filled_percentage,
            "blank_percentage": self.blank_percentage,
            "mandatory_missing": self.mandatory_missing,
            "total_mandatory": self.total_mandatory,
            "mandatory_filled": self.mandatory_filled,
            "mandatory_blank": self.mandatory_blank,
            "missing_fields": self.missing_fields,
            "blank_fields": self.blank_fields,
            "filled_fields": self.filled_fields,
        }


@dataclass
class ExtractionMetadata:
    """Metadata for extraction process."""
    filename: str
    total_pages: int
    extraction_timestamp: str
    toc_detected: bool
    extraction_confidence: float
    file_size_bytes: int
    output_filename: Optional[str] = None
    output_file: Optional[str] = None
    missing_sections: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "filename": self.filename,
            "total_pages": self.total_pages,
            "extraction_timestamp": self.extraction_timestamp,
            "toc_detected": self.toc_detected,
            "extraction_confidence": self.extraction_confidence,
            "file_size_bytes": self.file_size_bytes,
            "output_filename": self.output_filename,
            "output_file": self.output_file,
            "missing_sections": self.missing_sections,
        }


class NECSchema:
    """
    Schema for complete NEC contract extraction output.
    """
    
    # Programme-critical clauses (NEC3)
    PROGRAMME_CRITICAL_CLAUSES = [
        "3.1",  # Starting Date
        "3.2",  # Possession Date(s)
        "3.3",  # Completion Date
        "3.5",  # First Programme Submission
        "3.6",  # Revised Programme Interval
        "3.7",  # Delay Damages
        "4.1",  # Defects Date
        "4.2",  # Defect Correction Period
        "4.3",  # Landscaping Maintenance Period
        "5.2",  # Assessment Interval
        "5.3",  # Payment Period
        "5.5",  # Retention Percentage
        "5.6",  # Bond Amount
        "6.1",  # Weather Recording Location
        "6.2",  # Weather Measurement Data
        "6.3",  # Historical Weather Records Source
    ]
    
    @staticmethod
    def create_extraction_output(
        project: str,
        clauses: List[ClauseData],
        completeness: ContractCompleteness,
        metadata: ExtractionMetadata,
        contract_dates: Optional[Dict[str, Any]] = None,
        programme_requirements: Optional[Dict[str, Any]] = None,
        defects: Optional[Dict[str, Any]] = None,
        payment_terms: Optional[Dict[str, Any]] = None,
        weather_data: Optional[Dict[str, Any]] = None,
        scope_items: Optional[List[str]] = None,
        constraints: Optional[List[str]] = None,
        milestones: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Create complete extraction output dictionary.
        
        Args:
            project: Project name
            clauses: List of extracted clauses
            completeness: Completeness assessment
            metadata: Extraction metadata
            contract_dates: Contract dates dictionary
            programme_requirements: Programme requirements
            defects: Defects information
            payment_terms: Payment terms
            weather_data: Weather data
            scope_items: Scope items list
            constraints: Constraints list
            milestones: Milestones list
            
        Returns:
            Complete extraction output dictionary
        """
        # Convert clauses to dictionary
        extracted_clauses = {}
        for clause in clauses:
            extracted_clauses[clause.clause_number] = clause.to_dict()
        
        output = {
            "project": project,
            "extracted_clauses": extracted_clauses,
            "contract_completeness": completeness.to_dict(),
            "metadata": metadata.to_dict(),
            "contract_dates": contract_dates or {},
            "programme_requirements": programme_requirements or {},
            "defects": defects or {},
            "payment_terms": payment_terms or {},
            "weather_data": weather_data or {},
            "scope_items": scope_items or [],
            "constraints": constraints or [],
            "milestones": milestones or [],
        }
        
        return output
