"""
NEC Contract Extraction Modules.

Provides structured contract ingestion, table extraction, clause parsing,
and contract data models.
"""

from app.services.extraction.extractors.contract_ingestion_engine import ContractIngestionEngine
from app.services.extraction.extractors.table_extractor import TableExtractor
from app.services.extraction.extractors.clause_parser import ClauseParser
from app.services.extraction.extractors.nec_contract_model import (
    NECContract,
    ContractDataPart1,
    ContractDataPart2,
    DrawingReference,
    ContractorData
)

__all__ = [
    "ContractIngestionEngine",
    "TableExtractor",
    "ClauseParser",
    "NECContract",
    "ContractDataPart1",
    "ContractDataPart2",
    "DrawingReference",
    "ContractorData"
]
