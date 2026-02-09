"""
Scope Extractor for NEC Contract Analysis.

Extracts and segments scope items from contract documents with fine-grained
segmentation and strict scope classification.

Sources:
- Works Description section (CD1 page 6)
- Paragraphs with physical work verbs
- Drawing Schedule tables (all pages)
- Technical descriptions in clause options
"""

import re
from typing import List, Dict, Any, Optional, Set
from app.services.extraction.core.contract_classifier import ContractClassifier
from app.services.extraction.core.feature_extractor import FeatureExtractor
from app.services.extraction.core.ontology import EngineeringOntology


class ScopeExtractor:
    """
    Extracts scope items from contract documents with strict classification.
    
    Sources:
    - Works Description section (CD1 page 6)
    - Paragraphs containing physical work verbs
    - Drawing Schedule tables (all pages)
    - Technical descriptions in clause options
    """
    
    # Physical work verbs for detection (from requirements)
    PHYSICAL_WORK_VERBS: Set[str] = {
        "construct", "construction", "constructing", "constructed",
        "demolish", "demolition", "demolishing", "demolished",
        "widen", "widening", "widened",
        "narrow", "narrowing", "narrowed",
        "resurface", "resurfacing", "resurfaced",
        "reconstruct", "reconstructing", "reconstruction", "reconstructed",
        "install", "installation", "installing", "installed",
        "refurbish", "refurbishing", "refurbished", "refurbishment",
        "landscape", "landscaping", "landscaped",
        "relocate", "relocating", "relocated", "relocation",
        "divert", "diverting", "diverted", "diversion",
        "provide", "providing", "provided",
        "supply", "supplying", "supplied",
        "coordinate", "coordinating", "coordinated", "coordination",
        # Additional common verbs
        "build", "building", "built",
        "erect", "erecting", "erected",
        "lay", "laying", "laid",
        "excavate", "excavating", "excavation", "excavated",
        "backfill", "backfilling", "backfilled",
        "remove", "removing", "removal", "removed",
        "replace", "replacing", "replacement", "replaced",
        "upgrade", "upgrading", "upgrades", "upgraded"
    }
    
    # Physical assets for scope validation
    PHYSICAL_ASSETS: Set[str] = {
        "carriageway", "footway", "pavement", "road", "highway",
        "bridge", "bridges", "culvert", "culverts",
        "retaining wall", "retaining walls", "earthworks",
        "drainage", "manhole", "manholes", "pipe", "pipes",
        "kerb", "kerbs", "fence", "fences",
        "guardrail", "guardrails", "lighting", "signage",
        "junction", "junctions", "crossing", "crossings",
        "access", "building", "buildings", "structure", "structures",
        "landscape", "landscaping", "public realm"
    }
    
    # Admin keywords to exclude
    ADMIN_EXCLUSION_KEYWORDS: Set[str] = {
        "weather", "payment", "currency", "insurance", "bond", "bonds",
        "guarantee", "adjudication", "adjudicator", "dispute", "disputes",
        "arbitration", "definition", "definitions", "term", "terms",
        "programme", "programmes", "schedule", "deadline", "deadlines",
        "date", "dates", "acceptance", "cdm", "coordinator",
        "form", "forms", "notice", "notices", "contractual",
        "mechanism", "mechanisms", "procedure", "procedures",
        "employer", "contractor", "supervisor", "project manager"
    }
    
    def __init__(self):
        """Initialize scope extractor."""
        self.classifier = ContractClassifier()
        self.feature_extractor = FeatureExtractor()
        self.scope_counter = 0
    
    def extract_scope_from_structured_pdf(
        self, 
        structured_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Extract scope items ONLY from structured clauses and tables.
        
        DISABLED: All fallback inferred_list extraction has been removed.
        
        Sources (ONLY):
        - Clause 1.2 Works Description (from table cells)
        - Drawing Schedule tables
        
        Args:
            structured_data: Structured PDF data with pages, text_blocks, tables
            
        Returns:
            List of unique scope items (no duplicates)
        """
        scope_items = []
        seen_texts: Set[str] = set()  # Track duplicates
        
        if not structured_data or "pages" not in structured_data:
            return scope_items
        
        pages = structured_data["pages"]
        
        # ONLY extract from Drawing Schedule tables
        # Clause 1.2 extraction is handled by NECParser using table extraction
        print(f"[SCOPE_EXTRACTOR] Extracting from Drawing Schedule tables ONLY...")
        drawing_items = self._extract_from_drawing_schedule_complete(pages)
        for item_data in drawing_items:
            if item_data.get("text"):
                normalized = self._normalize_text(item_data["text"])
                if normalized not in seen_texts:
                    scope_item = self._create_scope_item_from_drawing(item_data)
                    if scope_item:
                        scope_items.append(scope_item)
                        seen_texts.add(normalized)
        
        print(f"[SCOPE_EXTRACTOR] Extracted {len(scope_items)} scope items from Drawing Schedule")
        return scope_items
    
    # DISABLED: All fallback extraction methods removed
    # Only table-based extraction is used (via NECParser)
    
    def _extract_from_drawing_schedule_complete(self, pages: List[Dict]) -> List[Dict[str, Any]]:
        """
        Extract complete drawing schedule entries from ALL pages.
        
        Each entry includes: sheet number, drawing code, title, status, scale, discipline.
        
        Handles both old format (rows as lists) and new format (rows as dicts).
        """
        drawing_items = []
        
        for page in pages:
            tables = page.get("tables", [])
            for table in tables:
                rows = table.get("rows", [])
                if not rows:
                    continue
                
                # Check if rows are in new format (dicts) or old format (lists)
                is_dict_format = rows and isinstance(rows[0], dict)
                
                if is_dict_format:
                    # New format: rows as dicts
                    # Could be: [{"field": "...", "value": "..."}] (two-column)
                    # Or: [{"code": "...", "title": "...", ...}] (multi-column with headers as keys)
                    
                    # Check if it's two-column format (field/value) or multi-column (header keys)
                    first_row = rows[0] if rows else {}
                    is_two_column = "field" in first_row and "value" in first_row
                    
                    if is_two_column:
                        # Two-column format: field-value pairs
                        for row in rows:
                            if not row:
                                continue
                            
                            field = str(row.get("field", "")).strip().lower()
                            value = str(row.get("value", "")).strip()
                            
                            if not value:
                                continue
                            
                            # Check if this looks like a drawing entry
                            if any(keyword in field for keyword in ["code", "number", "title", "drawing", "sheet"]):
                                drawing_data = {
                                    "drawing_code": value if "code" in field or "number" in field else "",
                                    "title": value if "title" in field else "",
                                    "sheet_number": value if "sheet" in field else "",
                                    "status": "",
                                    "scale": "",
                                    "discipline": "",
                                    "text": value
                                }
                                
                                if drawing_data["text"] and len(drawing_data["text"].strip()) > 5:
                                    drawing_items.append(drawing_data)
                    else:
                        # Multi-column format: headers as keys
                        # Example: [{"code": "...", "title": "...", "status": "..."}, ...]
                        for row in rows:
                            if not row:
                                continue
                            
                            drawing_data = {
                                "drawing_code": str(row.get("code", "") or row.get("number", "")).strip(),
                                "title": str(row.get("title", "")).strip(),
                                "sheet_number": str(row.get("sheet", "") or row.get("sheet_number", "")).strip(),
                                "status": str(row.get("status", "")).strip(),
                                "scale": str(row.get("scale", "")).strip(),
                                "discipline": str(row.get("discipline", "")).strip(),
                                "text": ""
                            }
                            
                            # Build text from title (primary) or combine all fields
                            if drawing_data["title"]:
                                drawing_data["text"] = drawing_data["title"]
                            else:
                                # Combine all non-empty fields
                                all_fields = [
                                    drawing_data["drawing_code"],
                                    drawing_data["title"],
                                    drawing_data["status"],
                                    drawing_data["scale"]
                                ]
                                drawing_data["text"] = " ".join(f for f in all_fields if f)
                            
                            if drawing_data["text"] and len(drawing_data["text"].strip()) > 5:
                                drawing_items.append(drawing_data)
                else:
                    # Old format: rows as lists [["code", "title"], ...]
                    # Try to identify header row
                    header_row_idx = None
                    for idx, row in enumerate(rows[:3]):  # Check first 3 rows
                        if not row or not isinstance(row, list):
                            continue
                        row_text = " ".join(str(cell).lower() for cell in row if cell)
                        if any(keyword in row_text for keyword in ["number", "title", "scale", "status", "rev", "sheet"]):
                            header_row_idx = idx
                            break
                    
                    # Map column indices
                    if header_row_idx is not None and isinstance(rows[header_row_idx], list):
                        headers = [str(cell).lower().strip() if cell else "" for cell in rows[header_row_idx]]
                        col_map = {}
                        for header in ["number", "code", "title", "scale", "status", "rev", "revision", "sheet", "discipline"]:
                            for idx, h in enumerate(headers):
                                if header in h:
                                    col_map[header] = idx
                                    break
                        
                        # Extract data rows
                        for row in rows[header_row_idx + 1:]:
                            if not row or not isinstance(row, list):
                                continue
                            if not any(cell and str(cell).strip() for cell in row):
                                continue
                            
                            drawing_data = {
                                "sheet_number": "",
                                "drawing_code": "",
                                "title": "",
                                "status": "",
                                "scale": "",
                                "discipline": ""
                            }
                            
                            # Extract fields
                            if "number" in col_map or "code" in col_map:
                                code_idx = col_map.get("code") or col_map.get("number")
                                if code_idx is not None and code_idx < len(row):
                                    drawing_data["drawing_code"] = str(row[code_idx]).strip()
                            
                            if "sheet" in col_map:
                                sheet_idx = col_map["sheet"]
                                if sheet_idx < len(row):
                                    drawing_data["sheet_number"] = str(row[sheet_idx]).strip()
                            
                            if "title" in col_map:
                                title_idx = col_map["title"]
                                if title_idx < len(row):
                                    drawing_data["title"] = str(row[title_idx]).strip()
                            
                            if "status" in col_map:
                                status_idx = col_map["status"]
                                if status_idx < len(row):
                                    drawing_data["status"] = str(row[status_idx]).strip()
                            
                            if "scale" in col_map:
                                scale_idx = col_map["scale"]
                                if scale_idx < len(row):
                                    drawing_data["scale"] = str(row[scale_idx]).strip()
                            
                            # Build text from title (primary) or all fields
                            if drawing_data["title"]:
                                drawing_data["text"] = drawing_data["title"]
                            else:
                                drawing_data["text"] = " ".join(str(v) for v in drawing_data.values() if v)
                            
                            if drawing_data["text"] and len(drawing_data["text"].strip()) > 5:
                                drawing_items.append(drawing_data)
                    else:
                        # No header found - try to extract from all rows
                        for row in rows:
                            if not row or not isinstance(row, list):
                                continue
                            row_text = " ".join(str(cell).strip() for cell in row if cell)
                            if len(row_text) > 10:
                                drawing_items.append({
                                    "text": row_text,
                                    "drawing_code": str(row[0]).strip() if len(row) > 0 and row[0] else "",
                                    "title": str(row[1]).strip() if len(row) > 1 and row[1] else "",
                                    "status": "",
                                    "scale": "",
                                    "sheet_number": "",
                                    "discipline": ""
                                })
        
        return drawing_items
    
    # DISABLED: Bullet list extraction removed (was creating inferred_list items)
    
    def _segment_compound_clause(self, text: str) -> List[str]:
        """
        Segment compound clauses into atomic items.
        
        Example: "carriageway reconstruction, resurfacing and footway refurbishment"
        -> ["carriageway reconstruction", "carriageway resurfacing", "footway refurbishment"]
        
        Handles:
        - Comma-separated lists
        - "and" separated items
        - Preserves context (e.g., "carriageway" applies to both "reconstruction" and "resurfacing")
        """
        if not text:
            return []
        
        text = text.strip()
        
        # First, split on commas and semicolons
        segments = re.split(r'[,;]\s+', text)
        
        # Process each segment to handle "and" separators and preserve context
        result = []
        previous_asset = None  # Track asset from previous segment
        
        for segment in segments:
            segment = segment.strip()
            if not segment:
                continue
            
            # Check for "and" separator in this segment
            if re.search(r'\s+and\s+', segment, re.IGNORECASE):
                parts = re.split(r'\s+and\s+', segment, flags=re.IGNORECASE)
                
                # Process first part
                first_part = parts[0].strip()
                
                # Extract asset from first part if present
                asset_in_first = None
                for asset in self.PHYSICAL_ASSETS:
                    if asset in first_part.lower():
                        asset_in_first = asset
                        break
                
                # If first part has asset, use it; otherwise use previous asset
                current_asset = asset_in_first or previous_asset
                
                # Add first part
                if first_part:
                    result.append(first_part)
                    # Update previous_asset for next iteration
                    if asset_in_first:
                        previous_asset = asset_in_first
                
                # Process remaining parts (after "and")
                for part in parts[1:]:
                    part = part.strip()
                    if not part:
                        continue
                    
                    # Check if this part already has an asset
                    part_has_asset = any(asset in part.lower() for asset in self.PHYSICAL_ASSETS)
                    
                    if not part_has_asset and current_asset:
                        # Prepend the asset context
                        part = f"{current_asset} {part}"
                    
                    result.append(part)
                    # Update previous_asset if this part has one
                    if part_has_asset:
                        for asset in self.PHYSICAL_ASSETS:
                            if asset in part.lower():
                                previous_asset = asset
                                break
            else:
                # No "and" in this segment
                # Check if segment has an asset
                segment_has_asset = any(asset in segment.lower() for asset in self.PHYSICAL_ASSETS)
                
                if segment_has_asset:
                    # Extract and remember asset
                    for asset in self.PHYSICAL_ASSETS:
                        if asset in segment.lower():
                            previous_asset = asset
                            break
                elif previous_asset:
                    # Apply previous asset context
                    segment = f"{previous_asset} {segment}"
                
                result.append(segment)
        
        # Clean and filter
        cleaned = [s.strip() for s in result if s.strip() and len(s.strip()) > 5]
        
        # Remove duplicates while preserving order
        seen = set()
        unique = []
        for item in cleaned:
            normalized = self._normalize_text(item)
            if normalized not in seen:
                unique.append(item)
                seen.add(normalized)
        
        return unique if unique else [text.strip()]
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for duplicate detection."""
        if not text:
            return ""
        # Lowercase, remove extra spaces, remove punctuation
        normalized = re.sub(r'[^\w\s]', '', text.lower())
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized
    
    def _is_valid_scope_item(self, text: str) -> bool:
        """
        Strict validation: text IS scope if it contains:
        - A physical action verb AND
        - A physical asset OR location OR measurable output
        
        Examples of valid scope:
        - demolition of buildings
        - divert telecoms ducts
        - construct new access road
        - install lighting columns
        - landscape public realm
        
        Examples of admin (excluded):
        - place where weather is recorded
        - dispute procedure
        - form of adjudication
        - definitions and interpretations
        - programme submission dates
        """
        if not text or len(text.strip()) < 10:
            return False
        
        text_lower = text.lower()
        
        # MUST contain at least one physical work verb
        has_work_verb = any(verb in text_lower for verb in self.PHYSICAL_WORK_VERBS)
        if not has_work_verb:
            return False
        
        # MUST contain physical asset OR location OR measurable output
        has_asset = any(asset in text_lower for asset in self.PHYSICAL_ASSETS)
        has_location = bool(re.search(
            r'\b(ch|chainage|location|site|area|zone|section|km|m)\b', 
            text_lower
        ))
        has_measurable = bool(re.search(
            r'\b(length|width|depth|height|quantity|quantities|m\s*\d+|km\s*\d+)\b',
            text_lower
        ))
        
        if not (has_asset or has_location or has_measurable):
            return False
        
        # EXCLUDE admin keywords (strict exclusion)
        if any(admin in text_lower for admin in self.ADMIN_EXCLUSION_KEYWORDS):
            return False
        
        # EXCLUDE specific admin patterns
        admin_patterns = [
            r'place where weather',
            r'dispute procedure',
            r'form of adjudication',
            r'definitions? and interpretations?',
            r'programme submission',
            r'submission date',
            r'acceptance date',
            r'cdm coordinator',
            r'contractual mechanism'
        ]
        if any(re.search(pattern, text_lower) for pattern in admin_patterns):
            return False
        
        return True
    
    def _create_scope_item(
        self, 
        text: str, 
        source: str
    ) -> Optional[Dict[str, Any]]:
        """
        Create a compact scope item with features.
        
        Args:
            text: Scope item text
            source: Source of the item (works_description, drawing_schedule)
            
        Returns:
            Compact scope item dictionary or None if invalid
        """
        if not text or not text.strip():
            return None
        
        # Generate ID
        self.scope_counter += 1
        item_id = f"SC-{self.scope_counter:04d}"
        
        # Extract features using FeatureExtractor (Tier 1 only, offline)
        features = self.feature_extractor.extract_features(text, section_type="scope_work")
        
        # Create compact scope item (NO expanded_text, NO intermediate data)
        # Build features dict, only including non-empty fields
        features_dict = {}
        if features.get("discipline"):
            features_dict["discipline"] = features.get("discipline")
        if features.get("actions"):
            features_dict["actions"] = features.get("actions")
        if features.get("assets"):
            features_dict["assets"] = features.get("assets")
        if features.get("materials"):
            features_dict["materials"] = features.get("materials")
        if features.get("chainages"):
            features_dict["chainages"] = features.get("chainages")
        if features.get("drawings"):
            features_dict["drawings"] = features.get("drawings")
        
        scope_item = {
            "id": item_id,
            "text": text.strip(),
            "features": features_dict,
            "source": source
        }
        
        # Only return if it has meaningful features (discipline, actions, or assets)
        # This ensures we only include real scope items
        if (features_dict.get("discipline") or 
            features_dict.get("actions") or 
            features_dict.get("assets")):
            return scope_item
        
        return None
    
    def _create_scope_item_from_drawing(self, drawing_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Create scope item from drawing schedule entry.
        
        Args:
            drawing_data: Dictionary with drawing fields (title, code, status, etc.)
            
        Returns:
            Compact scope item dictionary or None if invalid
        """
        text = drawing_data.get("text", "")
        if not text or len(text.strip()) < 5:
            return None
        
        # Generate ID
        self.scope_counter += 1
        item_id = f"SC-{self.scope_counter:04d}"
        
        # Extract features using FeatureExtractor
        features = self.feature_extractor.extract_features(text, section_type="scope_work")
        
        # Infer discipline from drawing code if available
        drawing_code = drawing_data.get("drawing_code", "").upper()
        if drawing_code and not features.get("discipline"):
            # Try to infer from drawing code pattern (e.g., ELW/100/01 -> ELW might indicate discipline)
            if "/" in drawing_code:
                parts = drawing_code.split("/")
                if len(parts) > 0:
                    prefix = parts[0]
                    # Map common prefixes to disciplines
                    if "ELW" in prefix or "DRAIN" in prefix:
                        features["discipline"] = "drainage"
                    elif "STR" in prefix or "BRIDGE" in prefix:
                        features["discipline"] = "structures"
                    elif "HWY" in prefix or "ROAD" in prefix:
                        features["discipline"] = "highways"
        
        # Add drawing code to drawings list if available
        if drawing_code:
            if "drawings" not in features or not features["drawings"]:
                features["drawings"] = []
            if drawing_code not in features["drawings"]:
                features["drawings"].append(drawing_code)
        
        # Build features dict, only including non-empty fields
        features_dict = {}
        if features.get("discipline"):
            features_dict["discipline"] = features.get("discipline")
        if features.get("actions"):
            features_dict["actions"] = features.get("actions")
        if features.get("assets"):
            features_dict["assets"] = features.get("assets")
        if features.get("materials"):
            features_dict["materials"] = features.get("materials")
        if features.get("chainages"):
            features_dict["chainages"] = features.get("chainages")
        if features.get("drawings"):
            features_dict["drawings"] = features.get("drawings")
        
        scope_item = {
            "id": item_id,
            "text": text.strip(),
            "features": features_dict,
            "source": "drawing_schedule"
        }
        
        # Include drawing metadata if available
        if drawing_data.get("drawing_code"):
            scope_item["drawing_code"] = drawing_data["drawing_code"]
        if drawing_data.get("status"):
            scope_item["drawing_status"] = drawing_data["status"]
        
        return scope_item

