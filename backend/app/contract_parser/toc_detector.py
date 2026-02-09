"""
Minimal TOC Detector stub for backward compatibility.
"""

from typing import List, Dict, Any, Optional


class TOCDetector:
    """Minimal TOC detector stub."""
    
    def __init__(self):
        """Initialize TOC detector."""
        pass
    
    def detect_toc_page(self, pages: List[Dict[str, Any]]) -> Optional[int]:
        """
        Detect TOC page (stub - returns None).
        
        Args:
            pages: List of page dictionaries
            
        Returns:
            None (TOC detection disabled)
        """
        return None
    
    def extract_toc_entries(self, pages: List[Dict[str, Any]], toc_page_idx: int) -> List[Dict[str, Any]]:
        """
        Extract TOC entries (stub - returns empty list).
        
        Args:
            pages: List of page dictionaries
            toc_page_idx: Index of TOC page
            
        Returns:
            Empty list
        """
        return []
