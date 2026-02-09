"""
Full Scope ↔ Activity Matching Engine for NEC Engineering Analysis System.

Orchestrates feature extraction and ensemble matching to produce
complete scope-to-activity mappings with status and ranking.
"""

from typing import Dict, List, Any, Optional

from app.services.extraction.core.feature_extractor import FeatureExtractor
from app.services.matching.engines.ensemble_engine import EnsembleMatcher


class ScopeMatchingEngine:
    """
    Full scope-to-activity matching engine.
    
    Orchestrates:
    - Feature extraction for scope and activity items
    - Ensemble matching between all pairs
    - Ranking and status determination
    - Identification of unmatched items
    """
    
    # Status thresholds
    COVERED_THRESHOLD = 0.50
    WEAK_THRESHOLD = 0.30
    
    def __init__(self):
        """
        Initialize matching engine.
        
        Creates:
        - FeatureExtractor for extracting features from text
        - EnsembleMatcher for computing match scores
        """
        self.feature_extractor = FeatureExtractor()
        self.ensemble_matcher = EnsembleMatcher()
    
    def match_scope_to_activities(
        self,
        scope_items: List[Dict[str, Any]],
        activities: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Match scope items to activities using ensemble scoring.
        
        For each scope item:
        1. Extract features
        2. Match against all activities
        3. Rank matches by score
        4. Determine status (covered/weak/missing)
        5. Identify best match
        
        After processing:
        6. Identify extra activities (not used as best match)
        
        Args:
            scope_items: List of scope items, each with:
                {
                    "id": str,
                    "text": str
                }
            activities: List of activities, each with:
                {
                    "id": str,
                    "text": str
                }
                
        Returns:
            dict: {
                "scope_matches": [
                    {
                        "scope_id": str,
                        "scope_text": str,
                        "best_match": {
                            "activity_id": str,
                            "activity_text": str,
                            "final_score": float,
                            "match": bool,
                            "components": {...},
                            "reasoning": [...]
                        },
                        "all_matches_ranked": [
                            {
                                "activity_id": str,
                                "activity_text": str,
                                "final_score": float,
                                "match": bool,
                                "components": {...}
                            },
                            ...
                        ],
                        "status": "covered" | "weak" | "missing"
                    },
                    ...
                ],
                "missing_scope": [
                    {
                        "scope_id": str,
                        "scope_text": str,
                        "best_score": float,
                        "status": "missing"
                    },
                    ...
                ],
                "extra_activities": [
                    {
                        "activity_id": str,
                        "activity_text": str,
                        "reason": "not matched to any scope"
                    },
                    ...
                ]
            }
        """
        # Handle empty inputs
        if not scope_items:
            scope_items = []
        if not activities:
            activities = []
        
        # Normalize inputs (ensure required fields exist)
        normalized_scope_items = []
        for item in scope_items:
            if not isinstance(item, dict):
                continue
            normalized_scope_items.append({
                "id": str(item.get("id", "")),
                "text": str(item.get("text", ""))
            })
        
        normalized_activities = []
        for item in activities:
            if not isinstance(item, dict):
                continue
            normalized_activities.append({
                "id": str(item.get("id", "")),
                "text": str(item.get("text", ""))
            })
        
        # Process each scope item
        scope_matches = []
        missing_scope = []
        best_match_activity_ids = set()  # Track activities used as best matches
        
        for scope_item in normalized_scope_items:
            scope_id = scope_item["id"]
            scope_text = scope_item["text"] or ""
            
            # Extract scope features
            try:
                scope_features = self.feature_extractor.extract_features(scope_text)
            except Exception as e:
                # If feature extraction fails, use empty features
                scope_features = {
                    "discipline": "",
                    "assets": [],
                    "actions": [],
                    "materials": [],
                    "chainages": [],
                    "drawings": [],
                    "activity_codes": [],
                    "expanded_text": scope_text,
                    "fallback_used": False
                }
            
            # Match against all activities
            all_matches = []
            
            for activity_item in normalized_activities:
                activity_id = activity_item["id"]
                activity_text = activity_item["text"] or ""
                
                # Extract activity features
                try:
                    activity_features = self.feature_extractor.extract_features(activity_text)
                except Exception as e:
                    # If feature extraction fails, use empty features
                    activity_features = {
                        "discipline": "",
                        "assets": [],
                        "actions": [],
                        "materials": [],
                        "chainages": [],
                        "drawings": [],
                        "activity_codes": [],
                        "expanded_text": activity_text,
                        "fallback_used": False
                    }
                
                # Compute ensemble match score
                try:
                    match_result = self.ensemble_matcher.evaluate(
                        scope_text,
                        activity_text,
                        scope_features,
                        activity_features
                    )
                except Exception as e:
                    # If matching fails, use zero score
                    match_result = {
                        "final_score": 0.0,
                        "match": False,
                        "components": {
                            "rule_score": 0.0,
                            "embedding_score": 0.0,
                            "llm_score": 0.0
                        },
                        "reasoning": [f"Matching failed: {str(e)}"]
                    }
                
                # Build match entry
                match_entry = {
                    "activity_id": activity_id,
                    "activity_text": activity_text,
                    "final_score": float(match_result.get("final_score", 0.0)),
                    "match": bool(match_result.get("match", False)),
                    "components": match_result.get("components", {
                        "rule_score": 0.0,
                        "embedding_score": 0.0,
                        "llm_score": 0.0
                    })
                }
                
                all_matches.append(match_entry)
            
            # Sort matches by final_score (highest first)
            all_matches.sort(key=lambda x: x["final_score"], reverse=True)
            
            # Determine best match
            best_match = None
            best_score = 0.0
            
            if all_matches:
                best_match_entry = all_matches[0]
                best_score = best_match_entry["final_score"]
                
                # Get full match result for best match (with reasoning)
                best_activity = None
                for activity_item in normalized_activities:
                    if activity_item["id"] == best_match_entry["activity_id"]:
                        best_activity = activity_item
                        break
                
                if best_activity:
                    # Re-compute match result to get full reasoning
                    try:
                        best_activity_features = self.feature_extractor.extract_features(
                            best_activity["text"] or ""
                        )
                        full_match_result = self.ensemble_matcher.evaluate(
                            scope_text,
                            best_activity["text"] or "",
                            scope_features,
                            best_activity_features
                        )
                    except Exception:
                        full_match_result = match_result
                    
                    best_match = {
                        "activity_id": best_match_entry["activity_id"],
                        "activity_text": best_match_entry["activity_text"],
                        "final_score": float(full_match_result.get("final_score", 0.0)),
                        "match": bool(full_match_result.get("match", False)),
                        "components": full_match_result.get("components", {
                            "rule_score": 0.0,
                            "embedding_score": 0.0,
                            "llm_score": 0.0
                        }),
                        "reasoning": full_match_result.get("reasoning", [])
                    }
                    
                    # Track this activity as used
                    best_match_activity_ids.add(best_match_entry["activity_id"])
            
            # Determine status
            if best_score >= self.COVERED_THRESHOLD:
                status = "covered"
            elif best_score >= self.WEAK_THRESHOLD:
                status = "weak"
            else:
                status = "missing"
            
            # Build scope match result
            scope_match_result = {
                "scope_id": scope_id,
                "scope_text": scope_text,
                "best_match": best_match or {
                    "activity_id": "",
                    "activity_text": "",
                    "final_score": 0.0,
                    "match": False,
                    "components": {
                        "rule_score": 0.0,
                        "embedding_score": 0.0,
                        "llm_score": 0.0
                    },
                    "reasoning": ["No matches found."]
                },
                "all_matches_ranked": all_matches,
                "status": status
            }
            
            if status == "missing":
                missing_scope.append({
                    "scope_id": scope_id,
                    "scope_text": scope_text,
                    "best_score": best_score,
                    "status": "missing"
                })
            
            scope_matches.append(scope_match_result)
        
        # Identify extra activities (not used as best match)
        extra_activities = []
        for activity_item in normalized_activities:
            activity_id = activity_item["id"]
            if activity_id not in best_match_activity_ids:
                extra_activities.append({
                    "activity_id": activity_id,
                    "activity_text": activity_item["text"] or "",
                    "reason": "not matched to any scope"
                })
        
        # Build final result
        return {
            "scope_matches": scope_matches,
            "missing_scope": missing_scope,
            "extra_activities": extra_activities
        }



