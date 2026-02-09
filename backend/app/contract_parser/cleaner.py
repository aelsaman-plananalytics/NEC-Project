"""
Text cleaning and normalization utilities for contract parsing.
"""

import re


class TextCleaner:
    """Cleans and normalizes contract text."""
    
    # Common abbreviations in NEC contracts
    ABBREVIATIONS = {
        "CD": "Contract Data",
        "WI": "Works Information",
        "SI": "Site Information",
        "PM": "Project Manager",
        "QS": "Quantity Surveyor",
        "CDM": "Construction Design and Management",
        "NEC": "New Engineering Contract",
        "ECC": "Engineering and Construction Contract",
        "TBC": "To Be Confirmed",
        "TBD": "To Be Determined",
        "ELW": "Edge Lane West",
        "ch": "chainage",
        "km": "kilometre",
        "m": "metre",
        "mm": "millimetre"
    }
    
    @staticmethod
    def clean_text(text: str) -> str:
        """
        Clean and normalize text.
        
        - Expand abbreviations
        - Lowercase
        - Remove line numbers
        - Unify chainage formats
        - Collapse whitespace
        """
        if not text:
            return ""
        
        # Expand abbreviations
        text = TextCleaner._expand_abbreviations(text)
        
        # Lowercase
        text = text.lower()
        
        # Remove line numbers (e.g., "1.2.3" at start of line)
        text = re.sub(r'^\d+(\.\d+)*\s+', '', text, flags=re.MULTILINE)
        
        # Unify chainage formats (ch 100, chainage 100, 100+00, etc.)
        text = TextCleaner._normalize_chainages(text)
        
        # Collapse whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text
    
    @staticmethod
    def _expand_abbreviations(text: str) -> str:
        """Expand common abbreviations."""
        result = text
        for abbrev, expansion in TextCleaner.ABBREVIATIONS.items():
            # Match whole word only
            pattern = r'\b' + re.escape(abbrev) + r'\b'
            result = re.sub(pattern, expansion, result, flags=re.IGNORECASE)
        return result
    
    @staticmethod
    def _normalize_chainages(text: str) -> str:
        """
        Normalize chainage formats to standard format: ch 100+00.
        
        Handles:
        - ch 100
        - chainage 100
        - 100+00
        - 100.00
        """
        # Pattern: ch/chainage followed by number
        text = re.sub(
            r'\b(?:ch|chainage)\s*(\d+(?:\.\d+)?)',
            r'ch \1+00',
            text,
            flags=re.IGNORECASE
        )
        
        # Pattern: number with + separator (100+00)
        text = re.sub(
            r'\b(\d+)\s*\+\s*(\d+)\b',
            r'ch \1+\2',
            text
        )
        
        return text
    
    @staticmethod
    def remove_boilerplate(text: str) -> str:
        """
        Remove common boilerplate text that doesn't affect programming.
        
        Filters out:
        - Contract administration
        - Lists of employees
        - Insurance clauses
        - Dispute resolution
        - Legal boilerplate
        - Pricing data
        - Health & safety questionnaires
        """
        if not text:
            return ""
        
        # Patterns to remove
        boilerplate_patterns = [
            r'contract administration[^.]*\.',
            r'list of employees[^.]*\.',
            r'insurance[^.]*\.',
            r'dispute resolution[^.]*\.',
            r'arbitration[^.]*\.',
            r'legal[^.]*\.',
            r'pricing data[^.]*\.',
            r'health and safety questionnaire[^.]*\.',
            r'questionnaire[^.]*\.',
            r'form[^.]*\.',
            r'notice[^.]*\.',
        ]
        
        result = text
        for pattern in boilerplate_patterns:
            result = re.sub(pattern, '', result, flags=re.IGNORECASE | re.DOTALL)
        
        return result.strip()

