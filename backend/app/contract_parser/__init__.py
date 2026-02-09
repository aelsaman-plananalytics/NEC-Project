"""
NEC Contract Parser Module.

NEW Real NEC4 ECC Extraction Engine (2026):
- RealNECExtractor: Comprehensive extraction for real-world NEC4 ECC contracts
- NECValueExtractor: Extracts literal values (dates, numbers, durations) from text blocks
- Works with EA-standard NEC4 formatting (Anderby Creek, Addingham, KSL Rec)
- Extracts Time Section, Key Dates, Delay Damages, Defects, Weather
- Does NOT use clause numbers - uses section-based label matching
- Option B: Regex finds lines, LLM trims to literal values only
"""

from app.contract_parser.hybrid_ai_extractor import HybridAIExtractor
from app.contract_parser.real_nec_extractor import RealNECExtractor
from app.contract_parser.nec_value_extractor import NECValueExtractor
from app.contract_parser.contract_data_extractor import ContractDataExtractor
from app.contract_parser.nec_parser import NECParser
from app.contract_parser.toc_detector import TOCDetector
from app.contract_parser.clause_locator import ClauseLocator

# Legacy extractors (kept for backward compatibility, but not recommended for real NEC4 contracts)
from app.contract_parser.nec4_cd_part_one_extractor import NEC4CDPartOneExtractor
from app.contract_parser.unified_extractor import UnifiedExtractor
from app.contract_parser.contract_data_table_extractor import ContractDataTableExtractor
from app.contract_parser.label_fallback_extractor import LabelFallbackExtractor
from app.contract_parser.extractor_hybrid import HybridNECExtractor

__all__ = [
    "HybridAIExtractor",  # Primary extractor: Engine finds windows, AI extracts values (final authority)
    "ContractDataExtractor",  # Label-based extractor for Contract Data Part One
    "RealNECExtractor",  # Fallback extractor for Key Dates and additional fields
    "NECValueExtractor",  # Value extraction layer (Option B)
    "NECParser",
    "TOCDetector",
    "ClauseLocator",
    # Legacy extractors
    "NEC4CDPartOneExtractor",
    "UnifiedExtractor",
    "ContractDataTableExtractor",
    "LabelFallbackExtractor",
    "HybridNECExtractor",
]
