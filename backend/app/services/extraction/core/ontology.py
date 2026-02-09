"""
Engineering Ontology for NEC Engineering Analysis System.

Seed ontology providing core engineering knowledge for text normalization,
discipline detection, asset identification, and pattern recognition.
"""

import re
from typing import List, Dict, Set, Optional, Tuple


class EngineeringOntology:
    """
    Seed engineering ontology for grounding and consistency in NEC analysis.
    
    Provides deterministic mappings and patterns for:
    - Abbreviation expansion
    - Action verb normalization
    - Discipline classification
    - Asset type detection
    - Material identification
    - Pattern matching (chainage, drawings, activity codes)
    """
    
    # 1. Core Abbreviation Expansion Map
    ABBREVIATIONS: Dict[str, str] = {
        # Civil/Structural
        "RC": "reinforced concrete",
        "PC": "precast concrete",
        "RCC": "reinforced cement concrete",
        "WRC": "water retaining concrete",
        "HDPE": "high density polyethylene",
        "GRP": "glass reinforced plastic",
        "GI": "galvanized iron",
        "MS": "mild steel",
        "SS": "stainless steel",
        "RSJ": "rolled steel joist",
        "UB": "universal beam",
        "UC": "universal column",
        # Highway/Drainage
        "WBM": "water bound macadam",
        "DBM": "dense bituminous macadam",
        "AC": "asphalt concrete",
        "PCC": "plain cement concrete",
        "MH": "manhole",
        "CB": "catch basin",
        "SW": "storm water",
        "FW": "foul water",
        # General
        "NTS": "not to scale",
        "TBC": "to be confirmed",
        "TBD": "to be determined",
    }
    
    # 2. Core Engineering Action Normalization
    ACTION_MAP: Dict[str, str] = {
        # Installation actions
        "install": "install",
        "place": "install",
        "fit": "install",
        "mount": "install",
        "fix": "install",
        "erect": "install",
        # Earthworks
        "excavate": "earthworks",
        "dig": "earthworks",
        "cut": "earthworks",
        "fill": "earthworks",
        "backfill": "earthworks",
        "compact": "earthworks",
        # Construction
        "construct": "construct",
        "build": "construct",
        "form": "construct",
        "pour": "construct",
        "cast": "construct",
        # Removal
        "remove": "remove",
        "demolish": "remove",
        "strip": "remove",
        "clear": "remove",
        # Testing
        "test": "test",
        "inspect": "test",
        "verify": "test",
    }
    
    # 3. Core Discipline Classifier Keywords
    DISCIPLINE_KEYWORDS: Dict[str, List[str]] = {
        "structures": [
            "bridge", "culvert", "retaining wall", "abutment", "pier",
            "beam", "column", "slab", "foundation", "piling", "reinforcement",
            "concrete", "steel", "structural"
        ],
        "highways": [
            "pavement", "road", "carriageway", "footway", "kerb", "verge",
            "asphalt", "macadam", "bitumen", "highway", "roadway"
        ],
        "drainage": [
            "drain", "drainage", "manhole", "catch basin", "gully", "pipe",
            "culvert", "storm water", "foul water", "sewer", "outfall"
        ],
        "earthworks": [
            "excavation", "cut", "fill", "embankment", "earthworks", "soil",
            "backfill", "compaction", "grading", "earth moving"
        ],
        "m&e": [
            "electrical", "mechanical", "lighting", "power", "cable", "conduit",
            "switchgear", "transformer", "M&E", "M and E"
        ],
        "utilities": [
            "utility", "service", "water main", "gas", "telecom", "fiber",
            "underground", "service duct"
        ],
        "temporary_works": [
            "temporary", "shoring", "scaffold", "falsework", "temporary works",
            "site establishment", "hoarding"
        ],
    }
    
    # 4. Core Asset Type Keywords (grouped by category)
    ASSET_KEYWORDS: Dict[str, List[str]] = {
        "culverts": [
            "culvert", "box culvert", "pipe culvert", "arch culvert",
            "multi-cell culvert"
        ],
        "bridges": [
            "bridge", "footbridge", "overbridge", "underbridge", "viaduct"
        ],
        "retaining_walls": [
            "retaining wall", "gabion wall", "reinforced earth wall",
            "concrete wall", "masonry wall"
        ],
        "drainage_manholes": [
            "manhole", "catch basin", "gully", "inspection chamber",
            "drainage chamber"
        ],
        "pavement_highways": [
            "pavement", "carriageway", "footway", "cycleway", "kerb",
            "verge", "shoulder"
        ],
        "earthworks": [
            "embankment", "cut slope", "fill slope", "batter", "berm"
        ],
        "utilities": [
            "water main", "gas main", "telecom duct", "service duct",
            "utility corridor"
        ],
    }
    
    # Asset to Discipline mapping
    ASSET_DISCIPLINE_MAP: Dict[str, str] = {
        "culverts": "structures",
        "bridges": "structures",
        "retaining_walls": "structures",
        "drainage_manholes": "drainage",
        "pavement_highways": "highways",
        "earthworks": "earthworks",
        "utilities": "utilities",
    }
    
    # 5. Material Keywords
    MATERIAL_KEYWORDS: List[str] = [
        "concrete", "reinforced concrete", "steel", "mild steel",
        "stainless steel", "asphalt", "bitumen", "aggregate", "soil",
        "HDPE", "PVC", "clay", "brick", "stone", "timber", "dbm", "grp"
    ]
    
    # 6. Regex Patterns
    CHAINAGE_PATTERN = re.compile(
        r'\b(?:Ch\.?|Chainage|CH)\s*(\d+)[\+\-](\d+)\b',
        re.IGNORECASE
    )
    
    DRAWING_PATTERN = re.compile(
        r'\b(?:DRG|DWG|DRAWING|SHT|SHEET|GA|GEN|DET)[\s\-]?(\d+[A-Z]?\d*)\b',
        re.IGNORECASE
    )
    
    # Activity code patterns (enhanced with P6-like patterns)
    ACTIVITY_CODE_PATTERNS = [
        re.compile(r'\b([A-Z]\d{4,5})\b'),  # Original: A10234
        re.compile(r'\b([A-Z]{2,3}[\-]?\d{3,5}[\-]?[A-Z]{0,3}[\-]?\d{0,5})\b'),  # Original: 0100-STR-CH124
        re.compile(r'\b([A-Z]-\d{4})\b'),  # New: A-1234
        re.compile(r'\b(\d{3}-[A-Z]{3,5}-\d{3})\b'),  # New: 010-STR-124
        re.compile(r'\b([A-Z]{2}-\d{4})\b'),  # New: AB-1234
    ]
    
    # Discipline weights
    DISCIPLINE_WEIGHTS: Dict[str, int] = {
        "structures": 5,
        "drainage": 5,
        "highways": 4,
        "earthworks": 3,
        "utilities": 3,
        "m&e": 2,
        "temporary_works": 1,
    }
    
    # Material equivalence map
    MATERIAL_EQUIVALENCE: Dict[str, str] = {
        "bituminous": "bitumen",
        "bituminous material": "bitumen",
        "rc concrete": "reinforced concrete",
        "asphalt concrete": "ac",
        "high density polyethylene": "hdpe",
        "polyvinyl chloride": "pvc",
        "dbm": "bitumen",
        "grp": "grp",
    }
    
    # Canonical material formats
    CANONICAL_MATERIALS: Dict[str, str] = {
        "reinforced concrete": "rc",
        "stainless steel": "ss",
        "mild steel": "ms",
        "asphalt concrete": "ac",
        "high density polyethylene": "hdpe",
        "polyvinyl chloride": "pvc",
    }
    
    # Asset canonicalization map
    ASSET_CANONICAL: Dict[str, str] = {
        "culvert": "culvert",
        "bridge": "bridge",
        "drainage_manhole": "drainage",
        "utility": "utility",
        "pavement_highway": "pavement",
    }
    
    @staticmethod
    def _canonicalize_list(items: List[str]) -> List[str]:
        """
        Canonicalize a list of items: lowercase, singularize, dedupe, sort.
        
        Improved singularization:
        - "ies" → "y" (utilities → utility)
        - "es" → remove but avoid incorrect cases
        - "s" → remove if not in ignore list
        
        Args:
            items: List of items to canonicalize
            
        Returns:
            List[str]: Canonicalized, deduplicated, sorted list
        """
        if not items:
            return []
        
        canonical = []
        seen = set()
        ignore_suffixes = ["gas", "mass", "glass", "as", "ss", "us", "is"]
        original_lower = [i.lower() for i in items]
        
        for item in items:
            # Lowercase
            item_lower = item.lower().strip()
            if not item_lower:
                continue
            
            # Improved singularization
            # Fix: Do NOT strip characters if word ends with "ge" (prevents "bridge" → "bridg")
            if item_lower.endswith('ge'):
                # Keep as-is, don't singularize words ending in "ge"
                pass
            elif item_lower.endswith('ies') and len(item_lower) > 3:
                # utilities → utility
                base = item_lower[:-3] + 'y'
                if base not in original_lower:
                    item_lower = base
            elif item_lower.endswith('es') and len(item_lower) > 2:
                # Check if base word is in ignore list
                base_es = item_lower[:-2]  # Remove "es"
                base_s = item_lower[:-1]   # Remove just "s"
                
                # Prefer base_s if it ends with 'e' (bridges → bridge, culverts → culvert)
                if base_s.endswith('e') and len(base_s) >= 4 and base_s not in ignore_suffixes:
                    if base_s not in original_lower:
                        item_lower = base_s
                elif base_es not in ignore_suffixes and len(base_es) >= 3:
                    # Only singularize if singular form doesn't exist in original
                    if base_es not in original_lower:
                        item_lower = base_es
            elif item_lower.endswith('s') and len(item_lower) > 1:
                base = item_lower[:-1]
                # Only singularize if base is not in ignore list and singular doesn't exist
                # Also check: don't strip if base ends with "ge"
                if (base not in ignore_suffixes and 
                    base not in original_lower and 
                    len(base) >= 4 and
                    not base.endswith('ge')):  # Don't strip if ends with "ge"
                    item_lower = base
            
            # Dedupe
            if item_lower not in seen:
                canonical.append(item_lower)
                seen.add(item_lower)
        
        # Canonicalize earthworks: convert "earthwork" to "earthworks"
        if "earthwork" in canonical:
            canonical = [c if c != "earthwork" else "earthworks" for c in canonical]
            # Remove duplicate if both exist
            if "earthworks" in canonical:
                canonical = [c for c in canonical if c != "earthwork"]
        
        return sorted(canonical)
    
    @staticmethod
    def expand_abbreviations(text: str) -> str:
        """
        Expand engineering abbreviations in text with improved boundary detection.
        
        Handles:
        - Standalone words: "RC" → "reinforced concrete"
        - Hyphenated: "RC-wall" → "reinforced concrete-wall"
        - Parentheses: "(RC)" → "(reinforced concrete)"
        - With numbers: "RW1" → expands if RW is in abbreviations
        - Multi-word patterns: "PC unit" → "precast unit"
        
        Prevents false expansions (e.g., "ac" inside "access").
        
        Args:
            text: Input text containing abbreviations
            
        Returns:
            str: Text with abbreviations expanded
        """
        result = text
        
        # Handle multi-word abbreviation patterns FIRST (before single-word expansion)
        # Pattern: abbreviation + space + noun (e.g., "PC unit", "MS pipe", "SS pipe")
        multi_word_patterns = [
            (r'\bPC\s+unit\b', 'precast unit'),
            (r'\bMS\s+pipe\b', 'mild steel pipe'),
            (r'\bSS\s+pipe\b', 'stainless steel pipe'),
            (r'\bRC\s+wall\b', 'reinforced concrete wall'),
            (r'\bRC\s+slab\b', 'reinforced concrete slab'),
            (r'\bRC\s+beam\b', 'reinforced concrete beam'),
            (r'\bHDPE\s+pipe\b', 'high density polyethylene pipe'),
        ]
        
        # Apply multi-word patterns first
        for pattern, replacement in multi_word_patterns:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        
        # Handle RW + number pattern (retaining wall IDs)
        result = re.sub(r'\bRW(\d+)\b', r'retaining wall \1', result, flags=re.IGNORECASE)
        
        # Sort abbreviations by length (longest first) to handle overlapping cases
        sorted_abbrevs = sorted(
            EngineeringOntology.ABBREVIATIONS.items(),
            key=lambda x: len(x[0]),
            reverse=True
        )
        
        # Check for AC context keywords (for safer AC expansion)
        text_lower = result.lower()
        ac_context_keywords = ["asphalt", "pavement", "road", "carriageway"]
        has_ac_context = any(keyword in text_lower for keyword in ac_context_keywords)
        
        # Apply single-word expansions
        for abbrev, expansion in sorted_abbrevs:
            # Special handling for AC: only expand if context exists
            if abbrev.upper() == "AC" and not has_ac_context:
                continue
            
            # Build pattern that matches:
            # - Word boundary OR hyphen OR opening parenthesis OR followed by number
            # But NOT inside a longer word
            pattern = (
                r'(?<![A-Za-z0-9])'  # Negative lookbehind: not preceded by alphanumeric
                + re.escape(abbrev)
                + r'(?=[\s\-\)]|$|[0-9]|\b)'  # Followed by: space, hyphen, closing paren, end, number, or word boundary
            )
            
            # Case-insensitive replacement
            result = re.sub(pattern, expansion, result, flags=re.IGNORECASE)
        
        # Remove duplicated nouns after expansion (e.g., "column column" → "column")
        duplicated_nouns = [
            (r'\bcolumn column\b', 'column'),
            (r'\bbeam beam\b', 'beam'),
            (r'\bwall wall\b', 'wall'),
            (r'\bculvert culvert\b', 'culvert'),
        ]
        
        for pattern, replacement in duplicated_nouns:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        
        return result
    
    @staticmethod
    def normalize_actions(text: str) -> List[str]:
        """
        Normalize engineering action verbs to canonical forms with priority logic.
        
        Priority: remove > earthworks > construct > install
        
        Handles verb forms: installing → install, placement → place, constructed → construct
        Supports multi-verb sentences split on delimiters: ",", " and ", " & ", "/", ";"
        
        Args:
            text: Input text containing action verbs
            
        Returns:
            List[str]: List with single canonical action (priority-based) or empty list
        """
        if not text:
            return []
        
        # Split input on delimiters for multi-verb sentences
        delimiters = [',', ' and ', ' & ', '/', ';']
        segments = [text]
        for delimiter in delimiters:
            new_segments = []
            for segment in segments:
                new_segments.extend(segment.split(delimiter))
            segments = new_segments
        
        detected_actions = set()
        
        # Process each segment
        for segment in segments:
            words = segment.split()
            
            for word in words:
                word_lower = word.lower().strip()
                if not word_lower:
                    continue
                
                # Remove suffixes in order: longest first
                base_word = word_lower
                suffixes = ['ments', 'ions', 'tion', 'ment', 'ing', 'ed', 's']
                
                for suffix in suffixes:
                    if base_word.endswith(suffix) and len(base_word) > len(suffix):
                        base_word = base_word[:-len(suffix)]
                        break
                
                # Try to match base form in ACTION_MAP
                if base_word in EngineeringOntology.ACTION_MAP:
                    canonical_action = EngineeringOntology.ACTION_MAP[base_word]
                    detected_actions.add(canonical_action)
        
        # Priority logic: remove > earthworks > construct > install
        if "remove" in detected_actions:
            return ["remove"]
        elif "earthworks" in detected_actions:
            return ["earthworks"]
        elif "construct" in detected_actions:
            return ["construct"]
        elif "install" in detected_actions:
            return ["install"]
        elif detected_actions:
            # Return first action found (for test, inspect, etc.)
            return [list(detected_actions)[0]]
        else:
            # No actions detected, return empty list
            return []
    
    @staticmethod
    def detect_discipline(text: str) -> str:
        """
        Detect the single most dominant engineering discipline in text.
        
        Uses weighted priority system:
        1. If assets detected, FORCE asset-discipline mapping
        2. Else, use weighted keyword frequency (count * weight)
        
        Args:
            text: Input text to analyze
            
        Returns:
            str: Single most dominant discipline, or empty string if none detected (never None)
        """
        if not text:
            return ""
        
        text_lower = text.lower()
        
        # Priority 0: Culvert discipline override to "drainage" (before weighted scoring)
        assets = EngineeringOntology.detect_assets(text)
        if assets and "culvert" in assets:
            return "drainage"
        
        # Priority 1: Check if assets are detected and FORCE asset-discipline mapping
        if assets:
            # Map canonical assets to disciplines
            asset_to_discipline = {
                "culvert": "drainage",  # Override: culvert → drainage
                "bridge": "structures",
                "drainage": "drainage",
                "utility": "utilities",
                "pavement": "highways",
            }
            
            for asset in assets:
                if asset in asset_to_discipline:
                    return asset_to_discipline[asset]
            
            # Fallback: try original asset categories
            for asset in assets:
                for asset_category, discipline in EngineeringOntology.ASSET_DISCIPLINE_MAP.items():
                    if asset in asset_category or asset_category in asset:
                        return discipline
                if asset in EngineeringOntology.ASSET_DISCIPLINE_MAP:
                    return EngineeringOntology.ASSET_DISCIPLINE_MAP[asset]
        
        # Priority 2: Use weighted keyword frequency
        discipline_scores: Dict[str, int] = {}
        
        for discipline, keywords in EngineeringOntology.DISCIPLINE_KEYWORDS.items():
            count = 0
            for keyword in keywords:
                # Count occurrences of keyword in text
                count += text_lower.count(keyword.lower())
            
            if count > 0:
                # Multiply by weight
                weight = EngineeringOntology.DISCIPLINE_WEIGHTS.get(discipline, 1)
                discipline_scores[discipline] = count * weight
        
        # Return discipline with highest weighted score
        if discipline_scores:
            return max(discipline_scores.items(), key=lambda x: x[1])[0]
        
        return ""
    
    @staticmethod
    def detect_assets(text: str) -> List[str]:
        """
        Detect asset types mentioned in text with canonicalization.
        
        Canonical forms:
        - Any culvert-type → "culvert"
        - Any bridge-type → "bridge"
        - Any drainage structure → "drainage"
        - Any utility type → "utility"
        - Any pavement/asphalt/road element → "pavement"
        
        Args:
            text: Input text to analyze
            
        Returns:
            List[str]: Canonicalized list of detected asset categories (never None)
        """
        if not text:
            return []
        
        text_lower = text.lower()
        detected = []
        
        for asset_category, keywords in EngineeringOntology.ASSET_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    if asset_category not in detected:
                        detected.append(asset_category)
                    break
        
        # Canonicalize first
        canonicalized = EngineeringOntology._canonicalize_list(detected)
        
        # Apply asset canonicalization mapping
        canonical_assets = []
        for asset in canonicalized:
            # Map to canonical form
            if "culvert" in asset:
                canonical_assets.append("culvert")
            elif "bridge" in asset:
                canonical_assets.append("bridge")
            elif "drainage" in asset or "manhole" in asset or "catch" in asset or "gully" in asset:
                canonical_assets.append("drainage")
            elif "utility" in asset or "main" in asset or "duct" in asset:
                canonical_assets.append("utility")
            elif "pavement" in asset or "carriageway" in asset or "footway" in asset or "kerb" in asset:
                canonical_assets.append("pavement")
            else:
                canonical_assets.append(asset)
        
        # Dedupe and return
        return sorted(list(set(canonical_assets)))
    
    @staticmethod
    def detect_materials(text: str) -> List[str]:
        """
        Detect construction materials mentioned in text with equivalence and canonicalization.
        
        Applies material equivalence mapping and canonical formats.
        
        Args:
            text: Input text to analyze
            
        Returns:
            List[str]: Canonicalized list of detected materials (never None)
        """
        if not text:
            return []
        
        text_lower = text.lower()
        detected = []
        
        # Detect RC, MS, SS basic terms using abbreviation map
        for abbrev, expansion in EngineeringOntology.ABBREVIATIONS.items():
            if abbrev.upper() in ["RC", "MS", "SS"]:
                # Check if abbreviation appears in text
                pattern = r'\b' + re.escape(abbrev) + r'\b'
                if re.search(pattern, text, re.IGNORECASE):
                    detected.append(expansion)
        
        # Apply material equivalence first
        for equiv, canonical in EngineeringOntology.MATERIAL_EQUIVALENCE.items():
            if equiv.lower() in text_lower:
                detected.append(canonical)
        
        # Detect materials from keywords
        for material in EngineeringOntology.MATERIAL_KEYWORDS:
            if material.lower() in text_lower:
                detected.append(material)
        
        # Canonicalize
        canonicalized = EngineeringOntology._canonicalize_list(detected)
        
        # Apply canonical material formats
        final_materials = []
        for material in canonicalized:
            # Check if material should be mapped to canonical form
            canonical_form = EngineeringOntology.CANONICAL_MATERIALS.get(material, material)
            final_materials.append(canonical_form)
        
        # Canonicalize earthworks: convert "earthwork" to "earthworks"
        if "earthwork" in final_materials:
            final_materials = [m if m != "earthwork" else "earthworks" for m in final_materials]
        
        # Dedupe and return
        return sorted(list(set(final_materials)))
    
    @staticmethod
    def detect_chainages(text: str) -> List[Tuple[str, int, int]]:
        """
        Detect chainage references in text.
        
        Args:
            text: Input text to analyze
            
        Returns:
            List[Tuple[str, int, int]]: List of (full_match, km, m) tuples (never None)
        """
        if not text:
            return []
        
        matches = []
        for match in EngineeringOntology.CHAINAGE_PATTERN.finditer(text):
            km = int(match.group(1))
            m = int(match.group(2))
            matches.append((match.group(0), km, m))
        return matches
    
    @staticmethod
    def detect_drawings(text: str) -> List[str]:
        """
        Detect drawing references in text.
        
        Args:
            text: Input text to analyze
            
        Returns:
            List[str]: List of detected drawing references (never None)
        """
        if not text:
            return []
        
        matches = []
        for match in EngineeringOntology.DRAWING_PATTERN.finditer(text):
            matches.append(match.group(0))
        return matches
    
    @staticmethod
    def detect_activity_codes(text: str) -> List[str]:
        """
        Detect activity code patterns in text (including P6-like patterns).
        
        Patterns supported:
        - A10234 (original)
        - 0100-STR-CH124 (original)
        - A-1234 (P6-like)
        - 010-STR-124 (P6-like)
        - AB-1234 (P6-like)
        
        Args:
            text: Input text to analyze
            
        Returns:
            List[str]: List of detected activity codes (never None)
        """
        if not text:
            return []
        
        matches = []
        seen = set()
        
        # Try all activity code patterns
        for pattern in EngineeringOntology.ACTIVITY_CODE_PATTERNS:
            for match in pattern.finditer(text):
                code = match.group(0)
                if code not in seen:
                    matches.append(code)
                    seen.add(code)
        
        return matches

