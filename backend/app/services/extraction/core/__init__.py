"""
Core extraction components.

Contains:
- EngineeringOntology: Engineering knowledge base
- FeatureExtractor: Three-tier feature extraction engine
"""

from app.services.extraction.core.ontology import EngineeringOntology
from app.services.extraction.core.feature_extractor import FeatureExtractor

__all__ = ["EngineeringOntology", "FeatureExtractor"]

