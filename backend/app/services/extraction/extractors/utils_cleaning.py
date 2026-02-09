"""
Text cleaning and normalization utilities for contract extraction.

Handles OCR noise, whitespace normalization, header/footer removal,
and other text cleaning tasks.
"""

import re
from typing import List, Tuple, Optional


def clean_ocr_noise(text: str) -> str:
    """
    Clean common OCR errors and noise.
    
    Args:
        text: Raw text with potential OCR errors
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    # Remove common OCR artifacts
    text = re.sub(r'cid:\d+', '', text)  # Remove cid:1, cid:2, etc.
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)  # Remove non-ASCII except common ones
    text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
    
    # Fix common OCR mistakes
    replacements = {
        r'\bl\s*([A-Z])': r'I\1',  # Fix "l" -> "I" at start of words
        r'([a-z])\s+([a-z])': r'\1\2',  # Fix broken words
    }
    
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text)
    
    return text.strip()


def remove_headers_footers(text: str, page_number_pattern: bool = True) -> str:
    """
    Remove headers and footers from text.
    
    Args:
        text: Text with potential headers/footers
        page_number_pattern: Whether to remove page numbers
        
    Returns:
        Text with headers/footers removed
    """
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        line = line.strip()
        
        # Skip common header/footer patterns
        if page_number_pattern and re.match(r'^\d+$', line):
            continue
        if re.match(r'^(Page|page)\s+\d+', line, re.IGNORECASE):
            continue
        if len(line) < 3:  # Very short lines (likely page numbers)
            continue
        
        cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)


def fix_hyphenated_line_breaks(text: str) -> str:
    """
    Fix words broken across lines with hyphens.
    
    Args:
        text: Text with potential hyphenated line breaks
        
    Returns:
        Text with fixed line breaks
    """
    # Pattern: word ending with hyphen, followed by newline, followed by continuation
    pattern = r'([a-zA-Z])-\s*\n\s*([a-zA-Z])'
    text = re.sub(pattern, r'\1\2', text)
    
    # Remove standalone hyphens at line ends
    text = re.sub(r'-\s*\n', ' ', text)
    
    return text


def normalize_whitespace(text: str) -> str:
    """
    Normalize all whitespace to single spaces.
    
    Args:
        text: Text with irregular whitespace
        
    Returns:
        Text with normalized whitespace
    """
    # Replace all whitespace (spaces, tabs, newlines) with single space
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def clean_unicode_issues(text: str) -> str:
    """
    Clean Unicode encoding issues.
    
    Args:
        text: Text with potential Unicode issues
        
    Returns:
        Cleaned text
    """
    # Remove zero-width characters
    text = re.sub(r'[\u200B-\u200D\uFEFF]', '', text)
    
    # Fix common Unicode issues
    text = text.replace('\u2019', "'")  # Right single quotation mark
    text = text.replace('\u2018', "'")  # Left single quotation mark
    text = text.replace('\u201C', '"')  # Left double quotation mark
    text = text.replace('\u201D', '"')  # Right double quotation mark
    text = text.replace('\u2013', '-')  # En dash
    text = text.replace('\u2014', '--')  # Em dash
    
    return text


def clean_text(text: str) -> str:
    """
    Apply all cleaning functions in sequence.
    
    Args:
        text: Raw text to clean
        
    Returns:
        Fully cleaned text
    """
    if not text:
        return ""
    
    text = clean_unicode_issues(text)
    text = fix_hyphenated_line_breaks(text)
    text = clean_ocr_noise(text)
    text = remove_headers_footers(text)
    text = normalize_whitespace(text)
    
    return text


def extract_section_number(text: str) -> Optional[Tuple[int, int, Optional[int]]]:
    """
    Extract section number from text (e.g., "1.2" -> (1, 2, None), "1.2.3" -> (1, 2, 3)).
    
    Args:
        text: Text that may contain section numbers
        
    Returns:
        Tuple of (major, minor, subminor) or None if not found
    """
    # Pattern for section numbers: 1.2, 1.2.3, etc.
    pattern = r'^(\d+)\.(\d+)(?:\.(\d+))?'
    match = re.match(pattern, text.strip())
    
    if match:
        major = int(match.group(1))
        minor = int(match.group(2))
        subminor = int(match.group(3)) if match.group(3) else None
        return (major, minor, subminor)
    
    return None


def is_clause_heading(text: str) -> bool:
    """
    Check if text is a clause heading (e.g., "1. General", "2.3 Payment").
    
    Args:
        text: Text to check
        
    Returns:
        True if it appears to be a clause heading
    """
    # Pattern for clause headings
    clause_pattern = r'^\d+(\.\d+)*\s+[A-Z][a-zA-Z\s]+'
    return bool(re.match(clause_pattern, text.strip()))


def extract_table_of_contents_indicators(text: str) -> bool:
    """
    Check if text is part of a table of contents.
    
    Args:
        text: Text to check
        
    Returns:
        True if appears to be TOC content
    """
    toc_keywords = ['content', 'table of contents', 'index', 'page']
    text_lower = text.lower()
    
    # Check for TOC patterns
    if any(keyword in text_lower for keyword in toc_keywords):
        # Check for page number patterns
        if re.search(r'\b(page|p\.)\s*\d+\b', text_lower):
            return True
    
    return False

