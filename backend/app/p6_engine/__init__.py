"""
P6 Engine Module.

Primavera P6 programme validation and NEC alignment.
Uses ComprehensiveValidator, XERLoader, LogicChecker, obligation_entities, etc.
"""

from app.p6_engine.xer_loader import XERLoader
from app.p6_engine.logic_checks import LogicChecker

__all__ = [
    "XERLoader",
    "LogicChecker",
]
