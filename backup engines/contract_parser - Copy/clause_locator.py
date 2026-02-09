"""
Minimal Clause Locator stub for backward compatibility.
"""

from typing import List, Dict, Any, Optional


class ClauseLocator:
    """Minimal clause locator stub."""
    
    def __init__(self):
        """Initialize clause locator."""
        pass
    
    def find_clauses_from_toc(self, toc_entries: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Find clauses from TOC (stub - returns empty dict).
        
        Args:
            toc_entries: List of TOC entries
            
        Returns:
            Empty dictionary
        """
        return {}
    
    def find_clauses_fallback(self, pages: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Find clauses using fallback method (stub - returns empty dict).
        
        Args:
            pages: List of page dictionaries
            
        Returns:
            Empty dictionary
        """
        return {}
    
    def find_clause_1_2_in_table(self, pages: List[Dict[str, Any]], page_num: int) -> Optional[str]:
        """
        Find Clause 1.2 in table (stub - returns None).
        
        Args:
            pages: List of page dictionaries
            page_num: Page number
            
        Returns:
            None
        """
        return None
    
    def get_section_pages(self, pages: List[Dict[str, Any]], start_page: int, section_type: str) -> List[int]:
        """
        Get section pages (stub - returns empty list).
        
        Args:
            pages: List of page dictionaries
            start_page: Starting page number
            section_type: Type of section
            
        Returns:
            Empty list
        """
        return []
    
    def find_section_3_in_table(self, pages: List[Dict[str, Any]], page_num: int) -> Optional[Dict[str, Any]]:
        """
        Find Section 3 in table (stub - returns None).
        
        Args:
            pages: List of page dictionaries
            page_num: Page number
            
        Returns:
            None
        """
        return None
