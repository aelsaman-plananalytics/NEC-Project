"""
Rule-Based Matching Engine for NEC Engineering Analysis System.

Deterministic engineering logic for matching scope items with activities
based on extracted features. No AI required - pure rule-based scoring.
"""

import re
from typing import Dict, List, Any, Optional


class RuleBasedMatcher:
    """
    Rule-based matcher for comparing scope and activity features.
    
    Uses deterministic engineering logic to compute match scores
    based on discipline, assets, actions, materials, chainages,
    drawings, and activity codes.
    """
    
    # Match weights for final score calculation
    WEIGHTS = {
        "discipline": 0.15,
        "assets": 0.25,
        "actions": 0.10,
        "materials": 0.05,
        "chainage": 0.30,
        "drawings": 0.10,
        "activity_codes": 0.05
    }
    
    @staticmethod
    def match_discipline(scope_disc: str, act_disc: str) -> Dict[str, Any]:
        """
        Match discipline between scope and activity.
        
        Rules:
        - Both empty → score=0.0, match=False
        - Identical → score=1.0, match=True
        - Different → score=0.0, match=False
        
        Args:
            scope_disc: Scope discipline (string)
            act_disc: Activity discipline (string)
            
        Returns:
            dict: {
                "score": float,
                "match": bool,
                "explanation": str
            }
        """
        # Normalize inputs
        scope_disc = (scope_disc or "").strip().lower()
        act_disc = (act_disc or "").strip().lower()
        
        # Both empty
        if not scope_disc and not act_disc:
            return {
                "score": 0.0,
                "match": False,
                "explanation": "No discipline specified in either item."
            }
        
        # Identical match
        if scope_disc == act_disc:
            return {
                "score": 1.0,
                "match": True,
                "explanation": f"Discipline match: '{scope_disc}'."
            }
        
        # No match
        return {
            "score": 0.0,
            "match": False,
            "explanation": f"Discipline mismatch: scope '{scope_disc}' vs activity '{act_disc}'."
        }
    
    @staticmethod
    def match_assets(scope_assets: List[str], act_assets: List[str]) -> Dict[str, Any]:
        """
        Match assets between scope and activity.
        
        Rules:
        - Both empty → score=0.0, match=False
        - Exact same set → score=1.0, match=True
        - Intersection exists (partial match) → score=0.7, match=True
        - No overlap → score=0.0, match=False
        
        Args:
            scope_assets: Scope assets (list of strings)
            act_assets: Activity assets (list of strings)
            
        Returns:
            dict: {
                "score": float,
                "match": bool,
                "explanation": str
            }
        """
        # Normalize inputs
        scope_assets = [a.strip().lower() for a in (scope_assets or []) if a and a.strip()]
        act_assets = [a.strip().lower() for a in (act_assets or []) if a and a.strip()]
        
        # Both empty
        if not scope_assets and not act_assets:
            return {
                "score": 0.0,
                "match": False,
                "explanation": "No assets specified in either item."
            }
        
        # Convert to sets for comparison
        scope_set = set(scope_assets)
        act_set = set(act_assets)
        
        # Exact match
        if scope_set == act_set:
            assets_str = ", ".join(sorted(scope_set))
            return {
                "score": 1.0,
                "match": True,
                "explanation": f"Assets match exactly: [{assets_str}]."
            }
        
        # Partial match (intersection exists)
        intersection = scope_set & act_set
        if intersection:
            matched = ", ".join(sorted(intersection))
            scope_only = ", ".join(sorted(scope_set - act_set)) if (scope_set - act_set) else "none"
            act_only = ", ".join(sorted(act_set - scope_set)) if (act_set - scope_set) else "none"
            return {
                "score": 0.7,
                "match": True,
                "explanation": f"Partial asset overlap: matched [{matched}]. Scope only: [{scope_only}]. Activity only: [{act_only}]."
            }
        
        # No match
        scope_str = ", ".join(sorted(scope_set)) if scope_set else "none"
        act_str = ", ".join(sorted(act_set)) if act_set else "none"
        return {
            "score": 0.0,
            "match": False,
            "explanation": f"No asset match. Scope: [{scope_str}]. Activity: [{act_str}]."
        }
    
    @staticmethod
    def match_actions(scope_actions: List[str], act_actions: List[str]) -> Dict[str, Any]:
        """
        Match actions between scope and activity.
        
        Rules:
        - Exact same action present → score=1.0
        - Overlapping verbs (e.g., install ↔ placement) → score=0.6
        - No overlap → score=0.0
        
        Args:
            scope_actions: Scope actions (list of strings)
            act_actions: Activity actions (list of strings)
            
        Returns:
            dict: {
                "score": float,
                "match": bool,
                "explanation": str
            }
        """
        # Normalize inputs
        scope_actions = [a.strip().lower() for a in (scope_actions or []) if a and a.strip()]
        act_actions = [a.strip().lower() for a in (act_actions or []) if a and a.strip()]
        
        # Both empty
        if not scope_actions and not act_actions:
            return {
                "score": 0.0,
                "match": False,
                "explanation": "No actions specified in either item."
            }
        
        # Convert to sets
        scope_set = set(scope_actions)
        act_set = set(act_actions)
        
        # Exact match
        intersection = scope_set & act_set
        if intersection:
            matched = ", ".join(sorted(intersection))
            return {
                "score": 1.0,
                "match": True,
                "explanation": f"Actions match: [{matched}]."
            }
        
        # Overlapping verbs mapping (install ↔ placement, construct ↔ build, etc.)
        action_equivalents = {
            "install": ["install", "placement", "place", "fit", "mount"],
            "construct": ["construct", "build", "erect", "create"],
            "remove": ["remove", "demolish", "dismantle", "strip"],
            "earthworks": ["earthworks", "excavate", "dig", "cut", "fill"],
            "repair": ["repair", "maintain", "restore", "fix"]
        }
        
        # Check for overlapping verbs
        for scope_action in scope_set:
            for act_action in act_set:
                # Check if they're in the same equivalence group
                for group, equivalents in action_equivalents.items():
                    if scope_action in equivalents and act_action in equivalents:
                        return {
                            "score": 0.6,
                            "match": True,
                            "explanation": f"Overlapping actions: scope '{scope_action}' ↔ activity '{act_action}' (both map to '{group}')."
                        }
        
        # No match
        scope_str = ", ".join(sorted(scope_set)) if scope_set else "none"
        act_str = ", ".join(sorted(act_set)) if act_set else "none"
        return {
            "score": 0.0,
            "match": False,
            "explanation": f"No action match. Scope: [{scope_str}]. Activity: [{act_str}]."
        }
    
    @staticmethod
    def match_materials(scope_mats: List[str], act_mats: List[str]) -> Dict[str, Any]:
        """
        Match materials between scope and activity.
        
        Rules:
        - Both empty → score=0.0, match=False
        - Exact overlap → score=1.0
        - Partial overlap → score=0.5
        - No overlap → score=0.0
        
        Args:
            scope_mats: Scope materials (list of strings)
            act_mats: Activity materials (list of strings)
            
        Returns:
            dict: {
                "score": float,
                "match": bool,
                "explanation": str
            }
        """
        # Normalize inputs
        scope_mats = [m.strip().lower() for m in (scope_mats or []) if m and m.strip()]
        act_mats = [m.strip().lower() for m in (act_mats or []) if m and m.strip()]
        
        # Both empty
        if not scope_mats and not act_mats:
            return {
                "score": 0.0,
                "match": False,
                "explanation": "No materials specified in either item."
            }
        
        # Convert to sets
        scope_set = set(scope_mats)
        act_set = set(act_mats)
        
        # Exact match
        if scope_set == act_set:
            mats_str = ", ".join(sorted(scope_set))
            return {
                "score": 1.0,
                "match": True,
                "explanation": f"Materials match exactly: [{mats_str}]."
            }
        
        # Partial match
        intersection = scope_set & act_set
        if intersection:
            matched = ", ".join(sorted(intersection))
            scope_only = ", ".join(sorted(scope_set - act_set)) if (scope_set - act_set) else "none"
            act_only = ", ".join(sorted(act_set - scope_set)) if (act_set - scope_set) else "none"
            return {
                "score": 0.5,
                "match": True,
                "explanation": f"Partial material overlap: matched [{matched}]. Scope only: [{scope_only}]. Activity only: [{act_only}]."
            }
        
        # No match
        scope_str = ", ".join(sorted(scope_set)) if scope_set else "none"
        act_str = ", ".join(sorted(act_set)) if act_set else "none"
        return {
            "score": 0.0,
            "match": False,
            "explanation": f"No material match. Scope: [{scope_str}]. Activity: [{act_str}]."
        }
    
    @staticmethod
    def _parse_chainage(chainage_str: str) -> Optional[Dict[str, int]]:
        """
        Parse chainage string to extract km and meter components.
        
        Handles formats:
        - "Ch 123+450"
        - "CH.123+100"
        - "Ch123+050"
        - "123+450"
        
        Args:
            chainage_str: Chainage string
            
        Returns:
            dict: {"km": int, "meters": int, "total_meters": int} or None
        """
        if not chainage_str:
            return None
        
        # Normalize: remove "Ch", "CH", "CH.", spaces, case
        normalized = re.sub(r'^ch\.?\s*', '', chainage_str.strip(), flags=re.IGNORECASE)
        normalized = normalized.replace(' ', '')
        
        # Match pattern: digits+digits (e.g., 123+450)
        match = re.match(r'(\d+)\+(\d+)', normalized)
        if match:
            km = int(match.group(1))
            meters = int(match.group(2))
            total_meters = km * 1000 + meters
            return {
                "km": km,
                "meters": meters,
                "total_meters": total_meters
            }
        
        return None
    
    @staticmethod
    def match_chainage(scope_ch: List[str], act_ch: List[str]) -> Dict[str, Any]:
        """
        Match chainages between scope and activity.
        
        Rules:
        - Exact chainage → score=1.0
        - Same km number (123+xxx) → score=0.7
        - Numeric difference < 100m → score=0.4
        - Otherwise → score=0.0
        
        Args:
            scope_ch: Scope chainages (list of strings)
            act_ch: Activity chainages (list of strings)
            
        Returns:
            dict: {
                "score": float,
                "match": bool,
                "explanation": str
            }
        """
        # Normalize inputs
        scope_ch = [c.strip() for c in (scope_ch or []) if c and c.strip()]
        act_ch = [c.strip() for c in (act_ch or []) if c and c.strip()]
        
        # Both empty
        if not scope_ch and not act_ch:
            return {
                "score": 0.0,
                "match": False,
                "explanation": "No chainages specified in either item."
            }
        
        # Parse all chainages
        scope_parsed = []
        for ch in scope_ch:
            parsed = RuleBasedMatcher._parse_chainage(ch)
            if parsed:
                scope_parsed.append((ch, parsed))
        
        act_parsed = []
        for ch in act_ch:
            parsed = RuleBasedMatcher._parse_chainage(ch)
            if parsed:
                act_parsed.append((ch, parsed))
        
        # No valid chainages
        if not scope_parsed and not act_parsed:
            return {
                "score": 0.0,
                "match": False,
                "explanation": "No valid chainage format found in either item."
            }
        
        # Compare all pairs
        best_score = 0.0
        best_explanation = ""
        best_match = False
        
        for scope_str, scope_data in scope_parsed:
            for act_str, act_data in act_parsed:
                # Exact match
                if scope_data["total_meters"] == act_data["total_meters"]:
                    return {
                        "score": 1.0,
                        "match": True,
                        "explanation": f"Exact chainage match: {scope_str} ↔ {act_str} ({scope_data['km']}+{scope_data['meters']})."
                    }
                
                # Same km number
                if scope_data["km"] == act_data["km"]:
                    score = 0.7
                    match = True
                    explanation = f"Same km section: {scope_str} ↔ {act_str} (km {scope_data['km']}, meters differ: {scope_data['meters']} vs {act_data['meters']})."
                    if score > best_score:
                        best_score = score
                        best_explanation = explanation
                        best_match = match
                    continue
                
                # Numeric difference < 100m
                diff_meters = abs(scope_data["total_meters"] - act_data["total_meters"])
                if diff_meters < 100:
                    score = 0.4
                    match = True
                    explanation = f"Close chainage proximity: {scope_str} ↔ {act_str} (difference: {diff_meters}m)."
                    if score > best_score:
                        best_score = score
                        best_explanation = explanation
                        best_match = match
        
        # Return best match found
        if best_score > 0.0:
            return {
                "score": best_score,
                "match": best_match,
                "explanation": best_explanation
            }
        
        # No match
        scope_str = ", ".join(scope_ch) if scope_ch else "none"
        act_str = ", ".join(act_ch) if act_ch else "none"
        return {
            "score": 0.0,
            "match": False,
            "explanation": f"No chainage match. Scope: [{scope_str}]. Activity: [{act_str}]."
        }
    
    @staticmethod
    def _extract_drawing_series(drawing_str: str) -> Optional[str]:
        """
        Extract drawing series/numeric prefix from drawing reference.
        
        Examples:
        - "DRG-102" → "102"
        - "SHT03" → "03"
        - "500/xx" → "500"
        - "GA-100" → "100"
        
        Args:
            drawing_str: Drawing reference string
            
        Returns:
            str: Numeric prefix/series or None
        """
        if not drawing_str:
            return None
        
        # Extract first numeric block (3+ digits preferred, but accept any)
        match = re.search(r'(\d{3,})', drawing_str)
        if match:
            return match.group(1)
        
        # Try 2-digit block
        match = re.search(r'(\d{2})', drawing_str)
        if match:
            return match.group(1)
        
        return None
    
    @staticmethod
    def match_drawings(scope_draw: List[str], act_draw: List[str]) -> Dict[str, Any]:
        """
        Match drawings between scope and activity.
        
        Rules:
        - Exact drawing match (DRG-102 ↔ DRG-102) → score=1.0
        - Same series (500/xx vs 500/yy) → score=0.5
        - None or mismatch → score=0.0
        
        Args:
            scope_draw: Scope drawings (list of strings)
            act_draw: Activity drawings (list of strings)
            
        Returns:
            dict: {
                "score": float,
                "match": bool,
                "explanation": str
            }
        """
        # Normalize inputs
        scope_draw = [d.strip().upper() for d in (scope_draw or []) if d and d.strip()]
        act_draw = [d.strip().upper() for d in (act_draw or []) if d and d.strip()]
        
        # Both empty
        if not scope_draw and not act_draw:
            return {
                "score": 0.0,
                "match": False,
                "explanation": "No drawings specified in either item."
            }
        
        # Convert to sets for exact match
        scope_set = set(scope_draw)
        act_set = set(act_draw)
        
        # Exact match
        intersection = scope_set & act_set
        if intersection:
            matched = ", ".join(sorted(intersection))
            return {
                "score": 1.0,
                "match": True,
                "explanation": f"Exact drawing match: [{matched}]."
            }
        
        # Same series match
        scope_series = {}
        for draw in scope_draw:
            series = RuleBasedMatcher._extract_drawing_series(draw)
            if series:
                if series not in scope_series:
                    scope_series[series] = []
                scope_series[series].append(draw)
        
        act_series = {}
        for draw in act_draw:
            series = RuleBasedMatcher._extract_drawing_series(draw)
            if series:
                if series not in act_series:
                    act_series[series] = []
                act_series[series].append(draw)
        
        # Check for same series
        common_series = set(scope_series.keys()) & set(act_series.keys())
        if common_series:
            series_str = ", ".join(sorted(common_series))
            scope_examples = ", ".join(scope_series[list(common_series)[0]][:2])
            act_examples = ", ".join(act_series[list(common_series)[0]][:2])
            return {
                "score": 0.5,
                "match": True,
                "explanation": f"Same drawing series: [{series_str}]. Scope examples: [{scope_examples}]. Activity examples: [{act_examples}]."
            }
        
        # No match
        scope_str = ", ".join(scope_draw) if scope_draw else "none"
        act_str = ", ".join(act_draw) if act_draw else "none"
        return {
            "score": 0.0,
            "match": False,
            "explanation": f"No drawing match. Scope: [{scope_str}]. Activity: [{act_str}]."
        }
    
    @staticmethod
    def match_activity_codes(scope_codes: List[str], act_codes: List[str]) -> Dict[str, Any]:
        """
        Match activity codes between scope and activity.
        
        Rules:
        - Exact match → score=1.0
        - Same prefix (e.g., DRN-xxx ↔ DRN) → score=0.5
        - No match → score=0.0
        
        Args:
            scope_codes: Scope activity codes (list of strings)
            act_codes: Activity activity codes (list of strings)
            
        Returns:
            dict: {
                "score": float,
                "match": bool,
                "explanation": str
            }
        """
        # Normalize inputs
        scope_codes = [c.strip().upper() for c in (scope_codes or []) if c and c.strip()]
        act_codes = [c.strip().upper() for c in (act_codes or []) if c and c.strip()]
        
        # Both empty
        if not scope_codes and not act_codes:
            return {
                "score": 0.0,
                "match": False,
                "explanation": "No activity codes specified in either item."
            }
        
        # Convert to sets for exact match
        scope_set = set(scope_codes)
        act_set = set(act_codes)
        
        # Exact match
        intersection = scope_set & act_set
        if intersection:
            matched = ", ".join(sorted(intersection))
            return {
                "score": 1.0,
                "match": True,
                "explanation": f"Exact activity code match: [{matched}]."
            }
        
        # Prefix match
        # Extract prefixes (everything before first dash or number)
        scope_prefixes = {}
        for code in scope_codes:
            # Extract prefix: everything before first dash, number, or end
            prefix_match = re.match(r'^([A-Z]+)', code)
            if prefix_match:
                prefix = prefix_match.group(1)
                if prefix not in scope_prefixes:
                    scope_prefixes[prefix] = []
                scope_prefixes[prefix].append(code)
        
        act_prefixes = {}
        for code in act_codes:
            prefix_match = re.match(r'^([A-Z]+)', code)
            if prefix_match:
                prefix = prefix_match.group(1)
                if prefix not in act_prefixes:
                    act_prefixes[prefix] = []
                act_prefixes[prefix].append(code)
        
        # Check for common prefix
        common_prefixes = set(scope_prefixes.keys()) & set(act_prefixes.keys())
        if common_prefixes:
            prefix_str = ", ".join(sorted(common_prefixes))
            scope_examples = ", ".join(scope_prefixes[list(common_prefixes)[0]][:2])
            act_examples = ", ".join(act_prefixes[list(common_prefixes)[0]][:2])
            return {
                "score": 0.5,
                "match": True,
                "explanation": f"Same activity code prefix: [{prefix_str}]. Scope examples: [{scope_examples}]. Activity examples: [{act_examples}]."
            }
        
        # No match
        scope_str = ", ".join(scope_codes) if scope_codes else "none"
        act_str = ", ".join(act_codes) if act_codes else "none"
        return {
            "score": 0.0,
            "match": False,
            "explanation": f"No activity code match. Scope: [{scope_str}]. Activity: [{act_str}]."
        }
    
    @classmethod
    def compute_rule_score(
        cls,
        scope_features: Dict[str, Any],
        activity_features: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Compute overall rule-based match score between scope and activity features.
        
        Uses weighted combination of all match criteria:
        - discipline: 0.15
        - assets: 0.25
        - actions: 0.10
        - materials: 0.05
        - chainage: 0.30
        - drawings: 0.10
        - activity_codes: 0.05
        
        Args:
            scope_features: Feature dictionary from scope item
            activity_features: Feature dictionary from activity item
            
        Returns:
            dict: {
                "rule_score": float (0.0-1.0),
                "matches": {
                    "discipline": bool,
                    "assets": bool,
                    "actions": bool,
                    "materials": bool,
                    "chainage": bool,
                    "drawings": bool,
                    "activity_codes": bool
                },
                "explanations": list[str]
            }
        """
        # Normalize inputs (handle None, missing keys)
        scope_features = scope_features or {}
        activity_features = activity_features or {}
        
        # Extract feature values with defaults
        scope_disc = scope_features.get("discipline", "") or ""
        act_disc = activity_features.get("discipline", "") or ""
        
        scope_assets = scope_features.get("assets", []) or []
        act_assets = activity_features.get("assets", []) or []
        
        scope_actions = scope_features.get("actions", []) or []
        act_actions = activity_features.get("actions", []) or []
        
        scope_mats = scope_features.get("materials", []) or []
        act_mats = activity_features.get("materials", []) or []
        
        scope_ch = scope_features.get("chainages", []) or []
        act_ch = activity_features.get("chainages", []) or []
        
        scope_draw = scope_features.get("drawings", []) or []
        act_draw = activity_features.get("drawings", []) or []
        
        scope_codes = scope_features.get("activity_codes", []) or []
        act_codes = activity_features.get("activity_codes", []) or []
        
        # Run all match functions
        disc_result = cls.match_discipline(scope_disc, act_disc)
        assets_result = cls.match_assets(scope_assets, act_assets)
        actions_result = cls.match_actions(scope_actions, act_actions)
        materials_result = cls.match_materials(scope_mats, act_mats)
        chainage_result = cls.match_chainage(scope_ch, act_ch)
        drawings_result = cls.match_drawings(scope_draw, act_draw)
        codes_result = cls.match_activity_codes(scope_codes, act_codes)
        
        # Compute weighted score
        final_score = (
            disc_result["score"] * cls.WEIGHTS["discipline"] +
            assets_result["score"] * cls.WEIGHTS["assets"] +
            actions_result["score"] * cls.WEIGHTS["actions"] +
            materials_result["score"] * cls.WEIGHTS["materials"] +
            chainage_result["score"] * cls.WEIGHTS["chainage"] +
            drawings_result["score"] * cls.WEIGHTS["drawings"] +
            codes_result["score"] * cls.WEIGHTS["activity_codes"]
        )
        
        # Ensure score is between 0.0 and 1.0
        final_score = max(0.0, min(1.0, final_score))
        
        # Collect matches and explanations
        matches = {
            "discipline": disc_result["match"],
            "assets": assets_result["match"],
            "actions": actions_result["match"],
            "materials": materials_result["match"],
            "chainage": chainage_result["match"],
            "drawings": drawings_result["match"],
            "activity_codes": codes_result["match"]
        }
        
        explanations = [
            disc_result["explanation"],
            assets_result["explanation"],
            actions_result["explanation"],
            materials_result["explanation"],
            chainage_result["explanation"],
            drawings_result["explanation"],
            codes_result["explanation"]
        ]
        
        return {
            "rule_score": round(final_score, 4),
            "matches": matches,
            "explanations": explanations
        }


