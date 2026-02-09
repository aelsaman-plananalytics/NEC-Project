"""
Section extraction for scope, constraints, milestones, and contract dates.
"""

import re
from typing import List, Dict, Any, Optional
from app.services.extraction.core.feature_extractor import FeatureExtractor
from app.services.extraction.core.scope_extractor import ScopeExtractor
from app.contract_parser.cleaner import TextCleaner


class SectionExtractor:
    """Extracts programme-critical information from contract sections."""
    
    def __init__(self):
        """Initialize section extractor."""
        self.feature_extractor = FeatureExtractor()
        self.scope_extractor = ScopeExtractor()
        self.cleaner = TextCleaner()
    
    def extract_works_description_exact(self, text: str) -> Optional[str]:
        """
        Extract the exact Works Description paragraph (1.2).
        
        Returns the full paragraph text as written.
        """
        if not text:
            return None
        
        # Look for "1.2 Works Description" or "Works Description" followed by paragraph
        pattern = r'(?:1\.2\s+)?works\s+description[:\s]+(.+?)(?=\d+\.\d+\s+|$)'
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        
        if match:
            paragraph = match.group(1).strip()
            # Clean up: remove extra whitespace, keep original structure
            paragraph = re.sub(r'\s+', ' ', paragraph)
            return paragraph
        
        return None
    
    def split_works_description(self, paragraph: str) -> List[str]:
        """
        Split Works Description paragraph into atomic scope items.
        
        Uses separators: [".", ";", ",", "and", "including", "comprising"]
        Cleans each item (removes trailing commas and clauses).
        
        Handles:
        - Comma-separated lists
        - "and" separated items
        - Preserves context (e.g., "carriageway" applies to both "reconstruction" and "resurfacing")
        """
        if not paragraph:
            return []
        
        # Remove "The Works are" prefix if present
        paragraph = re.sub(r'^the\s+works\s+are[:\s,]+', '', paragraph, flags=re.IGNORECASE).strip()
        
        items = []
        
        # Split on separators: ".", ";", ",", "and", "including", "comprising"
        # Use regex to split on these separators while preserving context
        separators = [
            r'\.\s+',  # Period followed by space
            r';\s+',   # Semicolon followed by space
            r',\s+',   # Comma followed by space
            r'\s+and\s+',  # "and" with spaces
            r'\s+including\s+',  # "including" with spaces
            r'\s+comprising\s+'  # "comprising" with spaces
        ]
        
        # Combine separators into one pattern
        separator_pattern = '|'.join(separators)
        
        # Split on separators
        parts = re.split(separator_pattern, paragraph)
        
        current_context = []  # Track context words (e.g., "carriageway")
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            # Remove trailing commas and clauses
            part = re.sub(r',\s*$', '', part)  # Remove trailing comma
            part = re.sub(r'\.\s*$', '', part)  # Remove trailing period
            
            # Check if this part starts a new context (e.g., "carriageway reconstruction")
            words = part.split()
            if len(words) > 0:
                # Check if first word is a noun that should be context
                first_word = words[0].lower()
                context_words = ["carriageway", "footway", "junction", "bridge", "drainage", 
                                "pavement", "kerb", "lighting", "signage", "landscape"]
                
                if first_word in context_words:
                    current_context = [first_word]
                    # Remove context word from part if it's just context
                    if len(words) > 1:
                        part = " ".join(words[1:])
                    else:
                        continue
                
                # Apply context if we have one
                if current_context:
                    full_item = f"{' '.join(current_context)} {part}"
                else:
                    full_item = part
                
                # Clean up: remove extra whitespace
                full_item = re.sub(r'\s+', ' ', full_item).strip()
                
                # Remove trailing clauses like "and", "including", etc.
                full_item = re.sub(r'\s+(and|including|comprising)\s*$', '', full_item, flags=re.IGNORECASE)
                
                if full_item and len(full_item) > 5:
                    items.append(full_item)
        
        return items if items else [paragraph]  # Fallback to original if splitting failed
    
    def create_scope_item(self, text: str, source: str) -> Optional[Dict[str, Any]]:
        """
        Create a scope item with features from text.
        
        Args:
            text: Scope item text
            source: Source of the item (works_description, works_information, etc.)
            
        Returns:
            Scope item dict or None if not valid
        """
        if not text or len(text.strip()) < 5:
            return None
        
        # Check if it's valid scope
        if not self._is_scope_clause(text):
            return None
        
        # Extract features
        features = self.feature_extractor.extract_features(text, section_type="scope_work")
        
        return {
            "text": text.strip(),
            "source": source,
            "discipline": features.get("discipline", ""),
            "assets": features.get("assets", []),
            "actions": features.get("actions", []),
            "materials": features.get("materials", []),
            "locations": features.get("chainages", []),
            "drawings": features.get("drawings", [])
        }
    
    def extract_scope_from_table(
        self, 
        table: Dict[str, Any], 
        source: str
    ) -> List[Dict[str, Any]]:
        """
        Extract scope items from a table in Works Information.
        
        Args:
            table: Table dict with "rows" key
            source: Source identifier
            
        Returns:
            List of scope items
        """
        scope_items = []
        rows = table.get("rows", [])
        
        for row in rows:
            if not row:
                continue
            
            # Combine row cells into text
            row_text = " ".join(str(cell) for cell in row if cell).strip()
            
            if row_text and self._is_scope_clause(row_text):
                scope_item = self.create_scope_item(row_text, source)
                if scope_item:
                    scope_items.append(scope_item)
        
        return scope_items
    
    def extract_scope_from_drawing_table(
        self,
        table: Dict[str, Any],
        source: str
    ) -> List[Dict[str, Any]]:
        """
        Extract scope items from drawing schedule table.
        
        Args:
            table: Table dict with "rows" key
            source: Source identifier (should be "drawing_schedule")
            
        Returns:
            List of scope items with drawing information
        """
        scope_items = []
        rows = table.get("rows", [])
        if not rows:
            return []
        
        # Try to identify header row
        header_row_idx = None
        for idx, row in enumerate(rows[:3]):
            row_text = " ".join(str(cell).lower() for cell in row if cell)
            if any(keyword in row_text for keyword in ["number", "title", "scale", "status", "rev", "sheet"]):
                header_row_idx = idx
                break
        
        # Map column indices
        col_map = {}
        if header_row_idx is not None:
            headers = [str(cell).lower().strip() if cell else "" for cell in rows[header_row_idx]]
            for header in ["number", "code", "title", "scale", "status", "rev", "revision", "sheet"]:
                for idx, h in enumerate(headers):
                    if header in h:
                        col_map[header] = idx
                        break
        
        # Extract data rows
        start_idx = header_row_idx + 1 if header_row_idx is not None else 0
        for row in rows[start_idx:]:
            if not any(cell and str(cell).strip() for cell in row):
                continue
            
            # Extract drawing information
            drawing_code = ""
            title = ""
            if "code" in col_map or "number" in col_map:
                code_idx = col_map.get("code") or col_map.get("number")
                if code_idx is not None and code_idx < len(row):
                    drawing_code = str(row[code_idx]).strip()
            
            if "title" in col_map:
                title_idx = col_map["title"]
                if title_idx < len(row):
                    title = str(row[title_idx]).strip()
            
            # Use title as text, or combine all cells if no title column
            if title:
                row_text = title
            else:
                row_text = " ".join(str(cell).strip() for cell in row if cell).strip()
            
            # Only create scope item if it contains physical work
            if row_text and self._is_scope_clause(row_text):
                scope_item = self.create_scope_item(row_text, source)
                if scope_item:
                    # Add drawing code if available
                    if drawing_code:
                        scope_item["drawing_code"] = drawing_code
                    scope_items.append(scope_item)
        
        return scope_items
    
    def extract_scope_items(self, text: str, source: str = "unknown") -> List[Dict[str, Any]]:
        """
        Extract scope items from text.
        
        Returns list of scope items with features:
        {
            "text": "",
            "discipline": "",
            "assets": [],
            "actions": [],
            "materials": [],
            "locations": [],
            "drawings": []
        }
        """
        if not text:
            return []
        
        # Clean text
        cleaned_text = self.cleaner.clean_text(text)
        cleaned_text = self.cleaner.remove_boilerplate(cleaned_text)
        
        # Use existing scope extractor for segmentation
        # Split into sentences/clauses
        clauses = self._split_into_clauses(cleaned_text)
        
        scope_items = []
        for clause in clauses:
            if not clause or len(clause.strip()) < 10:
                continue
            
            # Check if clause is scope-related
            if self._is_scope_clause(clause):
                scope_item = self.create_scope_item(clause, source)
                if scope_item:
                    scope_items.append(scope_item)
        
        return scope_items
    
    def extract_constraints(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract constraints from text.
        
        Returns list of constraints:
        {
            "type": "access | sequencing | environmental | utility | temp_works | traffic | approval",
            "description": "",
            "related_assets": [],
            "locations": []
        }
        """
        if not text:
            return []
        
        cleaned_text = self.cleaner.clean_text(text)
        
        constraints = []
        
        # Constraint patterns
        constraint_patterns = {
            "access": [
                r'shall not work',
                r'may only work',
                r'restricted to',
                r'access constraint',
                r'possession constraint',
                r'closed',
                r'opened after'
            ],
            "sequencing": [
                r'traffic management sequencing',
                r'temporary works sequencing',
                r'must be completed before',
                r'cannot commence until'
            ],
            "environmental": [
                r'noise constraint',
                r'dust constraint',
                r'vibration constraint',
                r'environmental constraint',
                r'working hours',
                r'no work outside'
            ],
            "utility": [
                r'utility diversion',
                r'must coordinate with utilities',
                r'statutory undertakers',
                r'utility approval required'
            ],
            "temp_works": [
                r'temporary works',
                r'temp works',
                r'temporary structure'
            ],
            "traffic": [
                r'traffic management',
                r'traffic regulation',
                r'traffic control'
            ],
            "approval": [
                r'requires approval',
                r'approval required',
                r'must obtain approval',
                r'prior approval'
            ]
        }
        
        # Split into sentences
        sentences = re.split(r'[.!?]\s+', cleaned_text)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence or len(sentence) < 10:
                continue
            
            # Check each constraint type
            for constraint_type, patterns in constraint_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, sentence, re.IGNORECASE):
                        # Extract features to get assets and locations
                        features = self.feature_extractor.extract_features(sentence, section_type="scope_work")
                        
                        constraint = {
                            "type": constraint_type,
                            "description": sentence,
                            "related_assets": features.get("assets", []),
                            "locations": features.get("chainages", [])
                        }
                        
                        constraints.append(constraint)
                        break  # Found constraint, move to next sentence
        
        return constraints
    
    def extract_milestones(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract milestones/deliverables from text.
        
        Returns list of milestones:
        {
            "name": "",
            "description": "",
            "category": "design | approval | test | handover | certificate"
        }
        """
        if not text:
            return []
        
        cleaned_text = self.cleaner.clean_text(text)
        
        milestones = []
        
        # Milestone patterns
        milestone_patterns = {
            "design": [
                r'design submission',
                r'submit design',
                r'design approval',
                r'drawing submission'
            ],
            "approval": [
                r'approval required',
                r'obtain approval',
                r'approval from',
                r'consent required'
            ],
            "test": [
                r'inspection required',
                r'test required',
                r'testing',
                r'witness test'
            ],
            "handover": [
                r'handover',
                r'hand over',
                r'take over',
                r'completion certificate'
            ],
            "certificate": [
                r'certificate',
                r'certification',
                r'certified'
            ]
        }
        
        # Split into sentences
        sentences = re.split(r'[.!?]\s+', cleaned_text)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence or len(sentence) < 10:
                continue
            
            # Check each milestone category
            for category, patterns in milestone_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, sentence, re.IGNORECASE):
                        # Extract milestone name (first part of sentence)
                        name_match = re.match(r'^([^,\.]+)', sentence)
                        name = name_match.group(1).strip() if name_match else sentence[:50]
                        
                        milestone = {
                            "name": name,
                            "description": sentence,
                            "category": category
                        }
                        
                        milestones.append(milestone)
                        break  # Found milestone, move to next sentence
        
        return milestones
    
    def extract_programme_constraints(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract programme submission timelines and revised programme requirements.
        
        Returns list of constraints related to programme submission.
        """
        constraints = []
        if not text:
            return constraints
        
        cleaned_text = self.cleaner.clean_text(text)
        
        # Programme submission patterns
        patterns = [
            (r'programme\s+submission[^\n]+', "programme_submission"),
            (r'submit\s+(a|the)\s+programme[^\n]+', "programme_submission"),
            (r'revised\s+programme[^\n]+', "programme_revision"),
            (r'programme\s+at\s+intervals[^\n]+', "programme_revision"),
        ]
        
        for pattern, constraint_type in patterns:
            matches = re.finditer(pattern, cleaned_text, re.IGNORECASE)
            for match in matches:
                description = match.group(0).strip()
                constraints.append({
                    "type": "programme",
                    "description": description,
                    "related_assets": [],
                    "locations": []
                })
        
        return constraints
    
    def extract_takeover_rules(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract take-over rules from Section 3.
        
        Returns list of constraints related to take-over.
        """
        constraints = []
        if not text:
            return constraints
        
        cleaned_text = self.cleaner.clean_text(text)
        
        # Take-over patterns
        patterns = [
            r'take\s+over[^\n]+',
            r'taking\s+over[^\n]+',
            r'not\s+willing\s+to\s+take\s+over[^\n]+',
            r'employer\s+is\s+not\s+willing[^\n]+',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, cleaned_text, re.IGNORECASE)
            for match in matches:
                description = match.group(0).strip()
                constraints.append({
                    "type": "takeover",
                    "description": description,
                    "related_assets": [],
                    "locations": []
                })
        
        return constraints
    
    def extract_contract_dates(self, text: str) -> Dict[str, Any]:
        """
        Extract contract dates from text.
        
        Returns:
        {
            "starting_date": "",
            "completion_date": "",
            "access_dates": [],
            "key_dates": [],
            "programme_submission_rules": "",
            "programme_revision_rules": ""
        }
        """
        if not text:
            return {
                "starting_date": "",
                "completion_date": "",
                "access_dates": [],
                "key_dates": [],
                "programme_submission_rules": "",
                "programme_revision_rules": ""
            }
        
        cleaned_text = self.cleaner.clean_text(text)
        
        dates = {
            "starting_date": "",
            "completion_date": "",
            "access_dates": [],
            "key_dates": [],
            "programme_submission_rules": "",
            "programme_revision_rules": ""
        }
        
        # Date patterns
        date_pattern = r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+\w+\s+\d{4})\b'
        
        # Starting date
        starting_match = re.search(r'starting\s+date[:\s]+([^\n]+)', cleaned_text, re.IGNORECASE)
        if starting_match:
            date_str = starting_match.group(1).strip()
            date_found = re.search(date_pattern, date_str)
            if date_found:
                dates["starting_date"] = date_found.group(1)
        
        # Completion date
        completion_match = re.search(r'completion\s+date[:\s]+([^\n]+)', cleaned_text, re.IGNORECASE)
        if completion_match:
            date_str = completion_match.group(1).strip()
            date_found = re.search(date_pattern, date_str)
            if date_found:
                dates["completion_date"] = date_found.group(1)
        
        # Access dates (possession dates)
        access_matches = re.finditer(
            r'(?:possession|access)\s+date[:\s]+([^\n]+)',
            cleaned_text,
            re.IGNORECASE
        )
        for match in access_matches:
            date_str = match.group(1).strip()
            date_found = re.search(date_pattern, date_str)
            if date_found:
                dates["access_dates"].append(date_found.group(1))
        
        # Programme submission rules
        programme_match = re.search(
            r'programme\s+submission[^\n]+',
            cleaned_text,
            re.IGNORECASE
        )
        if programme_match:
            dates["programme_submission_rules"] = programme_match.group(0).strip()
        
        # Programme revision rules
        revision_match = re.search(
            r'(?:programme\s+revision|revised\s+programme)[^\n]+',
            cleaned_text,
            re.IGNORECASE
        )
        if revision_match:
            dates["programme_revision_rules"] = revision_match.group(0).strip()
        
        # Key dates (look for "key date" or numbered dates in time section)
        key_date_matches = re.finditer(
            r'key\s+date[:\s]+([^\n]+)',
            cleaned_text,
            re.IGNORECASE
        )
        for match in key_date_matches:
            date_str = match.group(1).strip()
            date_found = re.search(date_pattern, date_str)
            if date_found:
                dates["key_dates"].append(date_found.group(1))
        
        return dates
    
    def _split_into_clauses(self, text: str) -> List[str]:
        """Split text into clauses/sentences."""
        # Split on sentence boundaries
        clauses = re.split(r'[.!?]\s+', text)
        
        # Also split on common list separators
        result = []
        for clause in clauses:
            # Split on commas if it's a list
            if ',' in clause and len(clause) > 50:
                parts = re.split(r',\s+(?=[a-z])', clause, flags=re.IGNORECASE)
                result.extend([p.strip() for p in parts if p.strip()])
            else:
                result.append(clause.strip())
        
        return [c for c in result if c and len(c) > 5]
    
    def _is_scope_clause(self, clause: str) -> bool:
        """Check if clause describes scope work."""
        clause_lower = clause.lower()
        
        # Must contain work verb
        work_verbs = [
            "construct", "demolish", "install", "reconstruct",
            "resurface", "divert", "refurbish", "landscape",
            "build", "erect", "lay", "excavate", "remove", "replace"
        ]
        
        has_verb = any(verb in clause_lower for verb in work_verbs)
        
        # Must contain asset or location
        has_asset = any(asset in clause_lower for asset in [
            "carriageway", "footway", "bridge", "drainage",
            "road", "highway", "junction", "crossing"
        ])
        
        has_location = bool(re.search(r'\b(ch|chainage|location|site)\b', clause_lower))
        
        return has_verb and (has_asset or has_location)


