"""
LLM Engineering Validator for NEC Engineering Analysis System.

Uses strict engineering reasoning mode to validate matches between
scope and activity items, fill missing features, and produce LLM scores.
"""

import json
import os
import traceback
from typing import Dict, List, Any, Optional

try:
    from openai import AzureOpenAI, OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    AzureOpenAI = None
    OpenAI = None

from app.services.extraction.core.ontology import EngineeringOntology

try:
    from app.config import settings
except ImportError:
    # Fallback if config not available
    class Settings:
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    settings = Settings()


class LLMEngineeringValidator:
    """
    LLM-based engineering validator with strict ontology constraints.
    
    Uses LLM reasoning to:
    - Validate if scope and activity describe the same engineering work
    - Fill missing features from ontology categories
    - Produce confidence scores (0.0-1.0)
    - Enforce ontology-only categories (no hallucination)
    """
    
    def __init__(self):
        """
        Initialize OpenAI client.
        
        If OPENAI_API_KEY missing:
            self.llm_enabled = False
        Otherwise:
            self.llm_enabled = True
        """
        import os
        from dotenv import load_dotenv
        
        self.llm_enabled = False
        self.openai_client = None
        self.llm_model = "gpt-4o"  # Default, will be overridden for Azure
        
        # Check AI_MODE
        ai_mode = os.getenv("AI_MODE", "real").lower().strip()
        
        # Check for Azure OpenAI first
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        azure_api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
        azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "")
        azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
        
        if ai_mode == "azure" or (ai_mode == "real" and azure_endpoint and azure_api_key):
            # Use Azure OpenAI
            if OPENAI_AVAILABLE and azure_endpoint and azure_api_key and azure_deployment:
                try:
                    self.openai_client = AzureOpenAI(
                        api_key=azure_api_key,
                        api_version=azure_api_version,
                        azure_endpoint=azure_endpoint
                    )
                    self.llm_model = azure_deployment
                    self.llm_enabled = True
                except Exception as e:
                    self.openai_client = None
                    self.llm_enabled = False
        else:
            # Fallback to OpenAI
            api_key = None
            if hasattr(settings, 'OPENAI_API_KEY') and settings.OPENAI_API_KEY:
                api_key = settings.OPENAI_API_KEY
            else:
                load_dotenv()
                api_key = os.getenv("OPENAI_API_KEY", "")
            
            if OPENAI_AVAILABLE and api_key:
                try:
                    self.openai_client = OpenAI(api_key=api_key)
                    self.llm_enabled = True
                except Exception as e:
                    self.openai_client = None
                    self.llm_enabled = False
            else:
                self.llm_enabled = False
    
    @staticmethod
    def _build_prompt(
        scope_text: str,
        activity_text: str,
        scope_features: Dict[str, Any],
        activity_features: Dict[str, Any],
        ontology: Optional[EngineeringOntology] = None
    ) -> str:
        """
        Build a STRICT engineering prompt.
        
        Requirements:
        - Provide allowed ontology categories (disciplines, assets, actions, materials)
        - Demand JSON output ONLY
        - Forbid hallucination
        - Ask LLM to fill in missing or uncertain fields
        - Ask LLM to compute a confidence score (0.0–1.0)
        - Ask LLM to explain match reasoning in one short sentence
        
        Args:
            scope_text: Original scope text
            activity_text: Original activity text
            scope_features: Extracted scope features
            activity_features: Extracted activity features
            ontology: EngineeringOntology instance
            
        Returns:
            str: Complete prompt for LLM
        """
        # Get ontology categories
        discipline_categories = list(EngineeringOntology.DISCIPLINE_KEYWORDS.keys())
        asset_categories = list(EngineeringOntology.ASSET_KEYWORDS.keys())
        action_categories = list(set(EngineeringOntology.ACTION_MAP.values()))
        material_categories = list(EngineeringOntology.MATERIAL_KEYWORDS)  # MATERIAL_KEYWORDS is a list, not dict
        
        # Format scope features
        scope_disc = scope_features.get("discipline", "") or ""
        scope_assets = scope_features.get("assets", []) or []
        scope_actions = scope_features.get("actions", []) or []
        scope_materials = scope_features.get("materials", []) or []
        scope_chainages = scope_features.get("chainages", []) or []
        scope_drawings = scope_features.get("drawings", []) or []
        
        # Format activity features
        act_disc = activity_features.get("discipline", "") or ""
        act_assets = activity_features.get("assets", []) or []
        act_actions = activity_features.get("actions", []) or []
        act_materials = activity_features.get("materials", []) or []
        act_chainages = activity_features.get("chainages", []) or []
        act_drawings = activity_features.get("drawings", []) or []
        
        prompt = f"""You are an engineering text analysis system for NEC contract compliance. Analyze if the scope item and activity item describe the same engineering work.

SCOPE TEXT:
"{scope_text}"

ACTIVITY TEXT:
"{activity_text}"

EXTRACTED SCOPE FEATURES:
- Discipline: {scope_disc if scope_disc else "(missing)"}
- Assets: {', '.join(scope_assets) if scope_assets else "(missing)"}
- Actions: {', '.join(scope_actions) if scope_actions else "(missing)"}
- Materials: {', '.join(scope_materials) if scope_materials else "(missing)"}
- Chainages: {', '.join(scope_chainages) if scope_chainages else "(none)"}
- Drawings: {', '.join(scope_drawings) if scope_drawings else "(none)"}

EXTRACTED ACTIVITY FEATURES:
- Discipline: {act_disc if act_disc else "(missing)"}
- Assets: {', '.join(act_assets) if act_assets else "(missing)"}
- Actions: {', '.join(act_actions) if act_actions else "(missing)"}
- Materials: {', '.join(act_materials) if act_materials else "(missing)"}
- Chainages: {', '.join(act_chainages) if act_chainages else "(none)"}
- Drawings: {', '.join(act_drawings) if act_drawings else "(none)"}

ALLOWED ONTOLOGY CATEGORIES (YOU MUST USE ONLY THESE):

Disciplines: {', '.join(discipline_categories)}
Assets: {', '.join(asset_categories)}
Actions: {', '.join(action_categories)}
Materials: {', '.join(material_categories)}

TASK:
1. Determine if these items describe the SAME engineering work (match: true/false)
2. Compute confidence score (0.0-1.0) based on:
   - Text similarity
   - Feature alignment
   - Engineering equivalence (e.g., "RCBC" = "RC box culvert")
   - Chainage/drawing matches
3. Fill missing features using ONLY ontology categories above
4. Provide one short engineering reasoning sentence

CRITICAL RULES:
- Return ONLY valid JSON, no other text
- Use ONLY categories from the ontology lists above
- Never invent new categories
- If discipline is missing, infer from assets/context
- If assets are missing, infer from text and discipline
- Match score should be high (0.8+) if chainages match AND assets/actions align
- Match score should be low (0.3-) if disciplines differ significantly
- Match score should be moderate (0.5-0.7) if partial alignment exists

OUTPUT FORMAT (JSON ONLY):
{{
  "llm_match": true/false,
  "llm_score": 0.0-1.0,
  "llm_reasoning": "One short sentence explaining the match decision.",
  "filled_features": {{
    "discipline": "string from ontology disciplines or empty string",
    "assets": ["list", "of", "ontology", "assets"],
    "actions": ["list", "of", "ontology", "actions"],
    "materials": ["list", "of", "ontology", "materials"]
  }}
}}

Return ONLY the JSON object, nothing else."""
        
        return prompt
    
    def _validate_llm_result(
        self,
        result_dict: Dict[str, Any],
        discipline_categories: List[str],
        asset_categories: List[str],
        action_categories: List[str],
        material_categories: List[str]
    ) -> Dict[str, Any]:
        """
        Validate LLM result to ensure only ontology categories are used.
        
        Args:
            result_dict: Raw LLM response dictionary
            discipline_categories: Allowed discipline categories
            asset_categories: Allowed asset categories
            action_categories: Allowed action categories
            material_categories: Allowed material categories
            
        Returns:
            dict: Validated result with only ontology categories
        """
        validated = {
            "llm_score": 0.0,
            "llm_match": False,
            "llm_reasoning": "Validation failed.",
            "filled_features": {
                "discipline": "",
                "assets": [],
                "actions": [],
                "materials": []
            }
        }
        
        # Extract and validate llm_score
        llm_score = result_dict.get("llm_score", 0.0)
        if isinstance(llm_score, (int, float)):
            validated["llm_score"] = max(0.0, min(1.0, float(llm_score)))
        
        # Extract and validate llm_match
        llm_match = result_dict.get("llm_match", False)
        if isinstance(llm_match, bool):
            validated["llm_match"] = llm_match
        
        # Extract and validate llm_reasoning
        llm_reasoning = result_dict.get("llm_reasoning", "")
        if isinstance(llm_reasoning, str):
            validated["llm_reasoning"] = llm_reasoning.strip() or "No reasoning provided."
        else:
            validated["llm_reasoning"] = "No reasoning provided."
        
        # Extract and validate filled_features
        filled_features = result_dict.get("filled_features", {})
        if not isinstance(filled_features, dict):
            filled_features = {}
        
        # Validate discipline
        discipline = filled_features.get("discipline", "")
        if isinstance(discipline, str) and discipline.strip():
            discipline_lower = discipline.strip().lower()
            if discipline_lower in [d.lower() for d in discipline_categories]:
                validated["filled_features"]["discipline"] = discipline_lower
            else:
                # Try to find closest match
                for cat in discipline_categories:
                    if cat.lower() == discipline_lower or discipline_lower in cat.lower():
                        validated["filled_features"]["discipline"] = cat.lower()
                        break
        
        # Validate assets
        assets = filled_features.get("assets", [])
        if isinstance(assets, list):
            validated_assets = []
            for asset in assets:
                if isinstance(asset, str) and asset.strip():
                    asset_lower = asset.strip().lower()
                    # Check if asset matches any ontology category
                    for cat in asset_categories:
                        if asset_lower == cat.lower() or asset_lower in cat.lower():
                            validated_assets.append(cat.lower())
                            break
            validated["filled_features"]["assets"] = list(set(validated_assets))
        
        # Validate actions
        actions = filled_features.get("actions", [])
        if isinstance(actions, list):
            validated_actions = []
            for action in actions:
                if isinstance(action, str) and action.strip():
                    action_lower = action.strip().lower()
                    if action_lower in [a.lower() for a in action_categories]:
                        validated_actions.append(action_lower)
            validated["filled_features"]["actions"] = list(set(validated_actions))
        
        # Validate materials
        materials = filled_features.get("materials", [])
        if isinstance(materials, list):
            validated_materials = []
            for material in materials:
                if isinstance(material, str) and material.strip():
                    material_lower = material.strip().lower()
                    if material_lower in [m.lower() for m in material_categories]:
                        validated_materials.append(material_lower)
            validated["filled_features"]["materials"] = list(set(validated_materials))
        
        return validated
    
    def evaluate(
        self,
        scope_text: str,
        activity_text: str,
        scope_features: Dict[str, Any],
        activity_features: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        MAIN ENTRY POINT: Evaluate match using LLM reasoning.
        
        Steps:
        1. Check if LLM is enabled
        2. Build prompt
        3. Call OpenAI LLM
        4. Parse JSON safely
        5. Validate fields against ontology
        6. Return structured result
        
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
        
        # Check if LLM is enabled
        if not self.llm_enabled:
            return {
                "llm_score": 0.0,
                "llm_match": False,
                "llm_reasoning": "LLM disabled: OpenAI API key not available.",
                "filled_features": {
                    "discipline": "",
                    "assets": [],
                    "actions": [],
                    "materials": []
                }
            }
        
        # Get ontology categories for validation
        discipline_categories = list(EngineeringOntology.DISCIPLINE_KEYWORDS.keys())
        asset_categories = list(EngineeringOntology.ASSET_KEYWORDS.keys())
        action_categories = list(set(EngineeringOntology.ACTION_MAP.values()))
        material_categories = list(EngineeringOntology.MATERIAL_KEYWORDS)  # MATERIAL_KEYWORDS is a list, not dict
        
        # Build prompt
        prompt = self._build_prompt(
            scope_text,
            activity_text,
            scope_features,
            activity_features,
            EngineeringOntology
        )
        
        # Call LLM with retry logic
        try:
            response = self.openai_client.chat.completions.create(
                model=self.llm_model,  # Azure uses deployment name
                messages=[
                    {
                        "role": "system",
                        "content": "You are an engineering text analysis system. You must ONLY return valid JSON with ontology-defined categories. Never invent new categories. Return ONLY JSON, no other text."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,  # Low temperature for deterministic output
                response_format={"type": "json_object"}
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Try to extract JSON if wrapped in markdown
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.startswith("```"):
                result_text = result_text[3:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]
            result_text = result_text.strip()
            
            # Parse JSON
            result_dict = json.loads(result_text)
            
            # Validate result
            validated_result = self._validate_llm_result(
                result_dict,
                discipline_categories,
                asset_categories,
                action_categories,
                material_categories
            )
            
            return validated_result
            
        except json.JSONDecodeError as e:
            # Retry once if JSON is invalid
            try:
                response = self.openai_client.chat.completions.create(
                    model=self.llm_model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an engineering text analysis system. You must ONLY return valid JSON with ontology-defined categories. Never invent new categories. Return ONLY JSON, no other text."
                        },
                        {
                            "role": "user",
                            "content": prompt + "\n\nCRITICAL: Return ONLY valid JSON. No markdown, no explanations, just the JSON object."
                        }
                    ],
                    temperature=0.1,
                    response_format={"type": "json_object"}
                )
                
                result_text = response.choices[0].message.content.strip()
                
                # Try to extract JSON if wrapped in markdown
                if result_text.startswith("```json"):
                    result_text = result_text[7:]
                if result_text.startswith("```"):
                    result_text = result_text[3:]
                if result_text.endswith("```"):
                    result_text = result_text[:-3]
                result_text = result_text.strip()
                
                result_dict = json.loads(result_text)
                
                validated_result = self._validate_llm_result(
                    result_dict,
                    discipline_categories,
                    asset_categories,
                    action_categories,
                    material_categories
                )
                
                return validated_result
                
            except Exception as retry_error:
                # Both attempts failed - return safe fallback
                return {
                    "llm_score": 0.0,
                    "llm_match": False,
                    "llm_reasoning": f"LLM response parsing failed after retry: {str(retry_error)}",
                    "filled_features": {
                        "discipline": "",
                        "assets": [],
                        "actions": [],
                        "materials": []
                    }
                }
        
        except Exception as e:
            # Any other error - return safe fallback
            return {
                "llm_score": 0.0,
                "llm_match": False,
                "llm_reasoning": f"LLM evaluation failed: {str(e)}",
                "filled_features": {
                    "discipline": "",
                    "assets": [],
                    "actions": [],
                    "materials": []
                }
            }

