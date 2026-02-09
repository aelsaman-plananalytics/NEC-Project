"""
Utility functions for NEC contract parsing.
"""

import re
from typing import Optional


def normalize_clause_number(clause_ref: str) -> Optional[str]:
    """
    Normalize clause number references.
    
    Handles variations like:
    - "3.1" -> "3.1"
    - "3. 1" -> "3.1"
    - "3-1" -> "3.1"
    - "3 1" -> "3.1"
    
    Args:
        clause_ref: Raw clause reference string
        
    Returns:
        Normalized clause number (e.g., "3.1") or None if invalid
    """
    if not clause_ref:
        return None
    
    # Remove whitespace
    clause_ref = clause_ref.strip()
    
    # Replace common separators with dot
    clause_ref = re.sub(r'[\s\-]+', '.', clause_ref)
    
    # Normalize multiple dots
    clause_ref = re.sub(r'\.+', '.', clause_ref)
    
    # Remove trailing dots
    clause_ref = clause_ref.rstrip('.')
    
    # Validate format: should be like "3.1" or "3.1.2"
    if re.match(r'^\d+(\.\d+)+$', clause_ref):
        return clause_ref
    
    return None


def extract_clause_from_text(text: str, clause_number: str) -> Optional[str]:
    """
    Extract clause text from surrounding text.
    
    Args:
        text: Full text to search
        clause_number: Clause number to find (e.g., "3.1")
        
    Returns:
        Extracted clause text or None
    """
    # Pattern to find clause
    pattern = rf'\b{re.escape(clause_number)}\b'
    
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None
    
    # Extract text after clause number (next 500 chars or until next clause)
    start_pos = match.end()
    end_pos = min(start_pos + 500, len(text))
    
    # Stop at next clause number
    next_clause = re.search(r'\b\d+\.\d+\b', text[start_pos:end_pos])
    if next_clause:
        end_pos = start_pos + next_clause.start()
    
    return text[start_pos:end_pos].strip()


def is_placeholder_value(value: str) -> bool:
    """
    Check if a value is a placeholder.
    
    Args:
        value: Value to check
        
    Returns:
        True if placeholder, False otherwise
    """
    if not value:
        return True
    
    value = value.strip().lower()
    
    placeholders = [
        "", "-", "n/a", "na", ".", "..", "...", "tbc", "tbd",
        "to be confirmed", "to be determined", "blank", "empty"
    ]
    
    return value in placeholders or value.count(".") > 6
