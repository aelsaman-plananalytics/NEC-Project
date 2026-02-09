"""
Mock LLM Engineering Validator for NEC Engineering Analysis System.

Simulates engineering reasoning WITHOUT OpenAI using:
- Synonym matching
- Feature-based inference
- Rule-based scoring with bonuses
- Ontology-constrained feature filling
"""

import re
from typing import Dict, List, Any, Set, Optional, Tuple

from app.services.extraction.core.ontology import EngineeringOntology
from app.services.extraction.core.feature_extractor import FeatureExtractor
from app.services.matching.engines.rule_engine import RuleBasedMatcher


class MockLLMValidator:
    """
    Mock LLM validator using deterministic engineering reasoning.
    
    Simulates LLM reasoning by:
    1. Extracting features from scope and activity
    2. Matching synonyms and engineering terms
    3. Computing base score from rule-based matching
    4. Applying bonuses for matches
    5. Inferring missing features from context
    """
    
    # Engineering synonym dictionary
    SYNONYMS = {
        # Actions
        "construct": ["build", "form", "cast", "create", "erect", "fabricate"],
        "install": ["lay", "placement", "fit", "place", "mount", "set"],
        "excavate": ["dig", "cut", "remove", "earthworks"],
        "repair": ["fix", "restore", "maintain", "rehabilitate"],
        "remove": ["demolish", "dismantle", "strip", "clear"],
        "reinforce": ["strengthen", "support", "brace"],
        
        # Assets
        "culvert": ["rcbc", "water crossing", "drainage structure", "pipe culvert"],
        "pavement": ["carriageway", "road surface", "asphalt", "bitumen"],
        "drainage": ["stormwater", "pipework", "sewer", "drain"],
        "bridge": ["structure", "span", "viaduct"],
        "retaining wall": ["rw", "wall", "retaining structure"],
        "kerb": ["curb", "edge", "kerbing"],
        "manhole": ["mh", "inspection chamber", "access point"],
        
        # Materials
        "reinforced concrete": ["rc", "concrete", "rcc"],
        "mild steel": ["ms", "steel"],
        "stainless steel": ["ss", "stainless"],
        "bitumen": ["dbm", "asphalt", "blacktop"],
        "grp": ["glass reinforced plastic", "fiberglass"],
        
        # Disciplines
        "structures": ["structural", "bridge", "culvert"],
        "drainage": ["stormwater", "sewer", "water"],
        "highways": ["pavement", "road", "carriageway"],
        "earthworks": ["excavation", "cut", "fill"],
    }
    
    # Bonus values for matches
    BONUSES = {
        "synonym": 0.15,
        "asset": 0.20,
        "chainage": 0.25,
        "material": 0.10,
        "discipline": 0.15
    }
    
    # Match threshold
    MATCH_THRESHOLD = 0.5
    
    def __init__(self):
        """
        Initialize mock LLM validator.
        
        Creates:
        - FeatureExtractor for feature extraction
        - RuleBasedMatcher for base scoring
        - EngineeringOntology for constraints
        """
        self.feature_extractor = FeatureExtractor()
        self.rule_matcher = RuleBasedMatcher()
        self.ontology = EngineeringOntology()
    
    @staticmethod
    def _preprocess_text(text: str) -> str:
        """
        Preprocess text for comparison.
        
        Steps:
        1. Lowercase
        2. Expand abbreviations
        3. Normalize whitespace
        
        Args:
            text: Raw input text
            
        Returns:
            str: Preprocessed text
        """
        if not text:
            return ""
        
        # Lowercase
        text = text.lower()
        
        # Expand abbreviations
        text = EngineeringOntology.expand_abbreviations(text)
        
        # Normalize whitespace
        text = ' '.join(text.split())
        
        return text.strip()
    
    @staticmethod
    def _tokenize(text: str) -> Set[str]:
        """
        Tokenize text into word set.
        
        Args:
            text: Preprocessed text
            
        Returns:
            set: Set of unique words
        """
        if not text:
            return set()
        
        words = [w for w in text.split() if w]
        return set(words)
    
    def _check_synonym_match(
        self,
        text1: str,
        text2: str
    ) -> Tuple[bool, List[str]]:
        """
        Check if texts match via synonyms.
        
        Args:
            text1: First preprocessed text
            text2: Second preprocessed text
            
        Returns:
            tuple: (has_match, matched_terms)
        """
        if not text1 or not text2:
            return (False, [])
        
        words1 = self._tokenize(text1)
        words2 = self._tokenize(text2)
        
        matched_terms = []
        
        # Check direct word matches
        direct_matches = words1 & words2
        if direct_matches:
            matched_terms.extend(list(direct_matches))
        
        # Check synonym matches
        for term, synonyms in self.SYNONYMS.items():
            term_words = set(term.split())
            
            # Check if term appears in text1
            in_text1 = any(word in words1 for word in term_words) or any(syn in text1 for syn in synonyms)
            # Check if term or synonym appears in text2
            in_text2 = any(word in words2 for word in term_words) or any(syn in text2 for syn in synonyms)
            
            if in_text1 and in_text2:
                matched_terms.append(term)
        
        return (len(matched_terms) > 0, matched_terms)
    
    def _check_asset_match(
        self,
        scope_features: Dict[str, Any],
        activity_features: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """
        Check if assets match or have synonym matches.
        
        Args:
            scope_features: Scope feature dictionary
            activity_features: Activity feature dictionary
            
        Returns:
            tuple: (has_match, matched_assets)
        """
        scope_assets = scope_features.get("assets", [])
        activity_assets = activity_features.get("assets", [])
        
        if not scope_assets or not activity_assets:
            return (False, [])
        
        # Normalize to sets
        scope_assets_set = {a.lower() for a in scope_assets if a}
        activity_assets_set = {a.lower() for a in activity_assets if a}
        
        # Direct matches
        matched = list(scope_assets_set & activity_assets_set)
        
        # Synonym matches
        for scope_asset in scope_assets_set:
            for activity_asset in activity_assets_set:
                # Check if they're synonyms
                for term, synonyms in self.SYNONYMS.items():
                    if (scope_asset in term or any(scope_asset in syn for syn in synonyms)) and \
                       (activity_asset in term or any(activity_asset in syn for syn in synonyms)):
                        if scope_asset not in matched:
                            matched.append(scope_asset)
                        if activity_asset not in matched:
                            matched.append(activity_asset)
        
        return (len(matched) > 0, matched)
    
    def _check_chainage_match(
        self,
        scope_features: Dict[str, Any],
        activity_features: Dict[str, Any]
    ) -> bool:
        """
        Check if chainages match.
        
        Args:
            scope_features: Scope feature dictionary
            activity_features: Activity feature dictionary
            
        Returns:
            bool: True if chainages match
        """
        scope_chainages = scope_features.get("chainages", [])
        activity_chainages = activity_features.get("chainages", [])
        
        if not scope_chainages or not activity_chainages:
            return False
        
        # Normalize chainages (remove spaces, convert to comparable format)
        scope_ch_set = {re.sub(r'[^\d+]', '', str(ch).lower()) for ch in scope_chainages if ch}
        activity_ch_set = {re.sub(r'[^\d+]', '', str(ch).lower()) for ch in activity_chainages if ch}
        
        # Check for overlap
        return len(scope_ch_set & activity_ch_set) > 0
    
    def _check_material_match(
        self,
        scope_features: Dict[str, Any],
        activity_features: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """
        Check if materials match or have synonym matches.
        
        Args:
            scope_features: Scope feature dictionary
            activity_features: Activity feature dictionary
            
        Returns:
            tuple: (has_match, matched_materials)
        """
        scope_materials = scope_features.get("materials", [])
        activity_materials = activity_features.get("materials", [])
        
        if not scope_materials or not activity_materials:
            return (False, [])
        
        # Normalize to sets
        scope_mats_set = {m.lower() for m in scope_materials if m}
        activity_mats_set = {m.lower() for m in activity_materials if m}
        
        # Direct matches
        matched = list(scope_mats_set & activity_mats_set)
        
        # Synonym matches
        for scope_mat in scope_mats_set:
            for activity_mat in activity_mats_set:
                for term, synonyms in self.SYNONYMS.items():
                    if (scope_mat in term or any(scope_mat in syn for syn in synonyms)) and \
                       (activity_mat in term or any(activity_mat in syn for syn in synonyms)):
                        if scope_mat not in matched:
                            matched.append(scope_mat)
                        if activity_mat not in matched:
                            matched.append(activity_mat)
        
        return (len(matched) > 0, matched)
    
    def _infer_discipline(
        self,
        scope_features: Dict[str, Any],
        activity_features: Dict[str, Any],
        scope_text: str,
        activity_text: str
    ) -> str:
        """
        Infer discipline from keywords if missing.
        
        Args:
            scope_features: Scope feature dictionary
            activity_features: Activity feature dictionary
            scope_text: Scope text
            activity_text: Activity text
            
        Returns:
            str: Inferred discipline (empty if cannot infer)
        """
        # Check existing disciplines
        scope_disc = scope_features.get("discipline", "").lower()
        activity_disc = activity_features.get("discipline", "").lower()
        
        if scope_disc:
            return scope_disc
        if activity_disc:
            return activity_disc
        
        # Infer from assets
        scope_assets = scope_features.get("assets", [])
        activity_assets = activity_features.get("assets", [])
        all_assets = [a.lower() for a in scope_assets + activity_assets if a]
        
        # Check asset-based discipline mapping
        for asset in all_assets:
            discipline = self.ontology.detect_discipline(asset)
            if discipline:
                return discipline.lower()
        
        # Infer from text keywords
        combined_text = (scope_text + " " + activity_text).lower()
        
        # Check discipline keywords
        for discipline, keywords in self.ontology.DISCIPLINE_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in combined_text:
                    return discipline.lower()
        
        return ""
    
    def _fill_missing_features(
        self,
        scope_features: Dict[str, Any],
        activity_features: Dict[str, Any],
        scope_text: str,
        activity_text: str
    ) -> Dict[str, Any]:
        """
        Fill missing features by merging scope and activity features.
        
        Args:
            scope_features: Scope feature dictionary
            activity_features: Activity feature dictionary
            scope_text: Scope text
            activity_text: Activity text
            
        Returns:
            dict: Filled features dictionary
        """
        filled = {
            "discipline": "",
            "assets": [],
            "actions": [],
            "materials": []
        }
        
        # Discipline: prefer non-empty, infer if both empty
        scope_disc = scope_features.get("discipline", "").strip()
        activity_disc = activity_features.get("discipline", "").strip()
        
        if scope_disc:
            filled["discipline"] = scope_disc.lower()
        elif activity_disc:
            filled["discipline"] = activity_disc.lower()
        else:
            filled["discipline"] = self._infer_discipline(
                scope_features, activity_features, scope_text, activity_text
            )
        
        # Assets: merge both lists
        scope_assets = scope_features.get("assets", [])
        activity_assets = activity_features.get("assets", [])
        all_assets = [a for a in scope_assets + activity_assets if a]
        filled["assets"] = list(set([a.lower() for a in all_assets if a]))
        
        # Actions: merge both lists
        scope_actions = scope_features.get("actions", [])
        activity_actions = activity_features.get("actions", [])
        all_actions = [a for a in scope_actions + activity_actions if a]
        filled["actions"] = list(set([a.lower() for a in all_actions if a]))
        
        # Materials: merge both lists
        scope_materials = scope_features.get("materials", [])
        activity_materials = activity_features.get("materials", [])
        all_materials = [m for m in scope_materials + activity_materials if m]
        filled["materials"] = list(set([m.lower() for m in all_materials if m]))
        
        return filled
    
    def evaluate(
        self,
        scope_text: str,
        activity_text: str,
        scope_features: Dict[str, Any],
        activity_features: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        MAIN ENTRY POINT: Evaluate match using mock LLM reasoning.
        
        Steps:
        1. Preprocess texts
        2. Extract/validate features
        3. Compute base rule score
        4. Check synonym matches
        5. Check asset matches
        6. Check chainage matches
        7. Check material matches
        8. Apply bonuses
        9. Fill missing features
        10. Generate reasoning
        
        Args:
            scope_text: Original scope item text
            activity_text: Original activity item text
            scope_features: Extracted scope features
            activity_features: Extracted activity features
            
        Returns:
            dict: {
                "llm_score": float (0.0-1.0),
                "llm_match": bool,
                "llm_reasoning": str,
                "filled_features": {
                    "discipline": str,
                    "assets": list[str],
                    "actions": list[str],
                    "materials": list[str]
                }
            }
        """
        # Handle empty inputs
        if not scope_text:
            scope_text = ""
        if not activity_text:
            activity_text = ""
        if not scope_features:
            scope_features = {}
        if not activity_features:
            activity_features = {}
        
        # Preprocess texts
        preprocessed_scope = self._preprocess_text(scope_text)
        preprocessed_activity = self._preprocess_text(activity_text)
        
        # Ensure features are extracted (if missing, extract now)
        if not scope_features or not scope_features.get("discipline"):
            try:
                scope_features = self.feature_extractor.extract_features(scope_text)
            except Exception:
                scope_features = scope_features or {}
        
        if not activity_features or not activity_features.get("discipline"):
            try:
                activity_features = self.feature_extractor.extract_features(activity_text)
            except Exception:
                activity_features = activity_features or {}
        
        # Compute base rule score
        try:
            rule_result = self.rule_matcher.compute_rule_score(scope_features, activity_features)
            base_score = rule_result.get("rule_score", 0.5)
        except Exception:
            base_score = 0.5
        
        # Ensure base_score is valid
        if not isinstance(base_score, (int, float)):
            base_score = 0.5
        base_score = max(0.0, min(1.0, float(base_score)))
        
        # Initialize final score
        final_score = base_score
        
        # Track bonuses for reasoning
        bonus_reasons = []
        
        # Check synonym match
        has_synonym, matched_terms = self._check_synonym_match(
            preprocessed_scope,
            preprocessed_activity
        )
        if has_synonym:
            final_score += self.BONUSES["synonym"]
            bonus_reasons.append(f"synonym match ({', '.join(matched_terms[:3])})")
        
        # Check asset match
        has_asset, matched_assets = self._check_asset_match(scope_features, activity_features)
        if has_asset:
            final_score += self.BONUSES["asset"]
            bonus_reasons.append(f"asset match ({', '.join(matched_assets[:2])})")
        
        # Check chainage match
        has_chainage = self._check_chainage_match(scope_features, activity_features)
        if has_chainage:
            final_score += self.BONUSES["chainage"]
            bonus_reasons.append("chainage match")
        
        # Check material match
        has_material, matched_materials = self._check_material_match(scope_features, activity_features)
        if has_material:
            final_score += self.BONUSES["material"]
            bonus_reasons.append(f"material match ({', '.join(matched_materials[:2])})")
        
        # Clamp score to [0.0, 1.0]
        final_score = max(0.0, min(1.0, final_score))
        
        # Round to 4 decimal places
        final_score = round(final_score, 4)
        
        # Determine match
        llm_match = final_score >= self.MATCH_THRESHOLD
        
        # Fill missing features
        filled_features = self._fill_missing_features(
            scope_features,
            activity_features,
            scope_text,
            activity_text
        )
        
        # Generate reasoning
        if bonus_reasons:
            reasoning = f"Match score {final_score:.2f} based on rule score {base_score:.2f} with bonuses: {', '.join(bonus_reasons)}."
        else:
            reasoning = f"Match score {final_score:.2f} based on rule score {base_score:.2f} with no additional matches."
        
        return {
            "llm_score": final_score,
            "llm_match": llm_match,
            "llm_reasoning": reasoning,
            "filled_features": filled_features
        }

