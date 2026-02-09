"""
Utility functions for NEC contract parsing.
"""

import re
from typing import Optional, Dict


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


def detect_nec_sections(clean_text: str) -> Dict[str, str]:
    """
    Detect NEC sections in clean_text using regex and heuristic anchors.
    
    Sections detected:
    - Section 3: Time
    - Section 4: Quality Management
    - Section 5: Payment
    - Section 6: Compensation Events (weather)
    - Option X7: Delay Damages
    
    Args:
        clean_text: Full clean text from PDF
        
    Returns:
        Dictionary mapping section IDs to section text:
        {
            "3": section_3_text,
            "4": section_4_text,
            "5": section_5_text,
            "6": section_6_text,
            "X7": section_x7_text
        }
        If a section is not found, set it to "".
    """
    sections = {
        "3": "",
        "4": "",
        "5": "",
        "6": "",
        "X7": ""
    }
    
    # Section 3: Time
    # Look for "Section 3", "3 Time", "3. Time", "3 TIME", etc.
    section_3_patterns = [
        r'Section\s+3[:\s]+Time',
        r'3[.\s]+Time',
        r'SECTION\s+3[:\s]+TIME',
        r'^3\s+Time',
        r'\b3\s+Time\b',
        r'Section\s+3\b',
    ]
    
    section_3_start = None
    for pattern in section_3_patterns:
        match = re.search(pattern, clean_text, re.IGNORECASE | re.MULTILINE)
        if match:
            section_3_start = match.start()
            break
    
    # Section 4: Quality Management
    section_4_patterns = [
        r'Section\s+4[:\s]+Quality',
        r'4[.\s]+Quality',
        r'SECTION\s+4[:\s]+QUALITY',
        r'^4\s+Quality',
        r'\b4\s+Quality\b',
        r'Section\s+4\b',
    ]
    
    section_4_start = None
    for pattern in section_4_patterns:
        match = re.search(pattern, clean_text, re.IGNORECASE | re.MULTILINE)
        if match:
            section_4_start = match.start()
            break
    
    # Section 5: Payment
    section_5_patterns = [
        r'Section\s+5[:\s]+Payment',
        r'5[.\s]+Payment',
        r'SECTION\s+5[:\s]+PAYMENT',
        r'^5\s+Payment',
        r'\b5\s+Payment\b',
        r'Section\s+5\b',
    ]
    
    section_5_start = None
    for pattern in section_5_patterns:
        match = re.search(pattern, clean_text, re.IGNORECASE | re.MULTILINE)
        if match:
            section_5_start = match.start()
            break
    
    # Section 6: Compensation Events
    section_6_patterns = [
        r'Section\s+6[:\s]+Compensation',
        r'6[.\s]+Compensation',
        r'SECTION\s+6[:\s]+COMPENSATION',
        r'^6\s+Compensation',
        r'\b6\s+Compensation\b',
        r'Section\s+6\b',
    ]
    
    section_6_start = None
    for pattern in section_6_patterns:
        match = re.search(pattern, clean_text, re.IGNORECASE | re.MULTILINE)
        if match:
            section_6_start = match.start()
            break
    
    # Option X7: Delay Damages
    x7_patterns = [
        r'Option\s+X7',
        r'OPTION\s+X7',
        r'X7[:\s]+Delay',
        r'\bX7\b.*?Delay\s+damages',
        r'Option\s+X7[:\s]+Delay',
    ]
    
    x7_start = None
    for pattern in x7_patterns:
        match = re.search(pattern, clean_text, re.IGNORECASE)
        if match:
            x7_start = match.start()
            break
    
    # Extract section text by finding boundaries
    # Section boundaries are typically the next section header or end of document
    
    # Find all section starts
    section_starts = []
    if section_3_start is not None:
        section_starts.append(("3", section_3_start))
    if section_4_start is not None:
        section_starts.append(("4", section_4_start))
    if section_5_start is not None:
        section_starts.append(("5", section_5_start))
    if section_6_start is not None:
        section_starts.append(("6", section_6_start))
    if x7_start is not None:
        section_starts.append(("X7", x7_start))
    
    # Sort by position
    section_starts.sort(key=lambda x: x[1])
    
    # Helper function to expand section start upward to include preamble
    def expand_section_start(section_id: str, header_pos: int, all_section_starts: list) -> int:
        """
        Expand section start position upward by up to 40 lines to include preamble.
        
        Stops expanding if:
        - Another numbered section header is encountered
        - Start of document is reached
        """
        # Sections that need preamble: 3, 5, 6, X7
        if section_id not in ["3", "5", "6", "X7"]:
            return header_pos
        
        # Get text before header
        text_before = clean_text[:header_pos]
        lines_before = text_before.split('\n')
        
        # Find the closest section header before this one
        closest_prev_section_pos = 0
        for other_id, other_pos in all_section_starts:
            if other_pos < header_pos and other_pos > closest_prev_section_pos:
                closest_prev_section_pos = other_pos
        
        # Count lines from header backward (up to 40 lines)
        lines_to_include = 0
        max_lines = 40
        
        # Work backward from header position
        for i in range(len(lines_before) - 1, -1, -1):
            if lines_to_include >= max_lines:
                break
            
            # Check if we've hit another section header
            line = lines_before[i]
            # Look for section headers (e.g., "Section 2", "2.", "Option X6")
            if re.search(r'Section\s+\d+|^\d+[.\s]+[A-Z]|Option\s+[A-Z]\d+', line, re.IGNORECASE):
                # Found another section header - stop here
                break
            
            lines_to_include += 1
        
        # Calculate new start position by counting characters
        if lines_to_include > 0:
            # Count characters backward from header_pos
            char_count = 0
            line_count = 0
            for i in range(len(lines_before) - 1, -1, -1):
                if line_count >= lines_to_include:
                    break
                # Add length of line plus newline character
                char_count += len(lines_before[i]) + 1  # +1 for newline
                line_count += 1
            
            # Calculate new start position
            new_start_pos = header_pos - char_count
            # Ensure we don't go before the closest previous section
            if new_start_pos < closest_prev_section_pos:
                new_start_pos = closest_prev_section_pos
            
            # Ensure we don't go negative
            if new_start_pos < 0:
                new_start_pos = 0
            
            return new_start_pos
        
        return header_pos
    
    # Expand section starts for sections that need preamble
    expanded_starts = []
    for section_id, start_pos in section_starts:
        expanded_start = expand_section_start(section_id, start_pos, section_starts)
        expanded_starts.append((section_id, expanded_start))
    
    # Sort by position again (in case expansion changed order)
    expanded_starts.sort(key=lambda x: x[1])
    
    # Extract each section text (from expanded start to next section or end)
    for i, (section_id, start_pos) in enumerate(expanded_starts):
        if i < len(expanded_starts) - 1:
            # Extract until next section
            end_pos = expanded_starts[i + 1][1]
            sections[section_id] = clean_text[start_pos:end_pos]
        else:
            # Last section - extract until end
            sections[section_id] = clean_text[start_pos:]
    
    return sections
