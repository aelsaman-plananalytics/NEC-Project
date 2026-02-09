"""
Core matching engines.

Contains:
- RuleBasedMatcher: Deterministic rule-based matching
- EnsembleMatcher: Weighted ensemble combining multiple matchers
- ScopeMatchingEngine: Full scope-to-activity matching orchestration
"""

from app.services.matching.engines.rule_engine import RuleBasedMatcher
# Note: EnsembleMatcher and ScopeMatchingEngine not imported here to avoid circular imports
# Import them directly when needed

__all__ = ["RuleBasedMatcher"]

