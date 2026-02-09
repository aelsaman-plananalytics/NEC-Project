"""
Engineering Feature Extraction Engine for NEC Analysis System.

Three-tier hybrid system:
- Tier 1: Ontology-based deterministic extraction
- Tier 2: Embedding-based semantic matching (ontology-constrained)
- Tier 3: LLM reasoning fallback (strict, ontology-constrained)
"""

import re
import json
import os
from typing import Dict, List, Optional, Any

# Check AI_MODE - if mock, never use OpenAI/Azure
AI_MODE = os.getenv("AI_MODE", "mock").lower().strip()

try:
    from openai import AzureOpenAI, OpenAI
    import numpy as np
    from numpy.linalg import norm
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    AzureOpenAI = None
    OpenAI = None
    np = None
    norm = None

from app.services.extraction.core.ontology import EngineeringOntology

try:
    from app.config import settings
except ImportError:
    # Fallback if config not available
    class Settings:
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    settings = Settings()


class FeatureExtractor:
    """
    Three-tier hybrid feature extraction engine.
    
    Extracts structured engineering features from unstructured text using:
    1. Ontology-based deterministic rules
    2. Embedding-based semantic matching
    3. LLM reasoning fallback
    """
    
    def __init__(self):
        """
        Initialize the feature extractor.
        
        In MOCK mode: Never initializes OpenAI client (offline only)
        In REAL mode: Initializes OpenAI client if available
        """
        # NEVER use OpenAI/Azure in mock mode
        if AI_MODE == "mock":
            self.openai_client = None
            self.embedding_model = None
            self.llm_model = None
            print("[FeatureExtractor] Initialized in MOCK mode - OpenAI/Azure disabled")
            return
        
        # REAL/AZURE mode: Try to initialize Azure OpenAI or OpenAI
        from dotenv import load_dotenv
        load_dotenv()
        
        # Check for Azure OpenAI first
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        azure_api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
        azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "")
        azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
        
        if AI_MODE == "azure" or (AI_MODE == "real" and azure_endpoint and azure_api_key):
            # Use Azure OpenAI
            if OPENAI_AVAILABLE and azure_endpoint and azure_api_key and azure_deployment:
                try:
                    self.openai_client = AzureOpenAI(
                        api_key=azure_api_key,
                        api_version=azure_api_version,
                        azure_endpoint=azure_endpoint
                    )
                    self.embedding_model = azure_deployment  # Use same deployment for embeddings
                    self.llm_model = azure_deployment
                    print(f"[FeatureExtractor] Initialized in AZURE mode - Azure OpenAI enabled (deployment: {azure_deployment})")
                except Exception as e:
                    self.openai_client = None
                    self.embedding_model = None
                    self.llm_model = None
                    print(f"[FeatureExtractor] Warning: Azure OpenAI initialization failed: {e}")
            else:
                self.openai_client = None
                self.embedding_model = None
                self.llm_model = None
                print("[FeatureExtractor] Azure OpenAI not available - using offline mode")
        else:
            # Fallback to OpenAI
            api_key = None
            if hasattr(settings, 'OPENAI_API_KEY') and settings.OPENAI_API_KEY:
                api_key = settings.OPENAI_API_KEY
            else:
                api_key = os.getenv("OPENAI_API_KEY", "")
            
            if OPENAI_AVAILABLE and api_key:
                try:
                    self.openai_client = OpenAI(api_key=api_key)
                    self.embedding_model = "text-embedding-3-small"
                    self.llm_model = "gpt-4o"
                    print("[FeatureExtractor] Initialized in REAL mode - OpenAI enabled")
                except Exception as e:
                    self.openai_client = None
                    self.embedding_model = None
                    self.llm_model = None
                    print(f"[FeatureExtractor] Warning: OpenAI initialization failed: {e}")
            else:
                self.openai_client = None
                self.embedding_model = None
                self.llm_model = None
                print("[FeatureExtractor] OpenAI not available - using offline mode")
    
    @staticmethod
    def preprocess_text(text: str) -> str:
        """
        Preprocess input text for feature extraction.
        
        - Lowercase
        - Trim whitespace
        - Normalize punctuation
        - Collapse multiple spaces
        - Strip newlines
        
        Args:
            text: Raw input text
            
        Returns:
            str: Preprocessed text
        """
        if not text:
            return ""
        
        # Lowercase
        text = text.lower()
        
        # Normalize whitespace: collapse multiple spaces/tabs to single space
        text = re.sub(r'\s+', ' ', text)
        
        # Strip newlines and carriage returns
        text = text.replace('\n', ' ').replace('\r', ' ')
        
        # Normalize punctuation (remove extra punctuation, keep essential)
        text = re.sub(r'[^\w\s\-\(\)\+\.,]', ' ', text)
        
        # Trim whitespace
        text = text.strip()
        
        return text
    
    @staticmethod
    def extract_tier1_ontology(text: str) -> Dict[str, Any]:
        """
        Tier 1: Ontology-based deterministic extraction.
        
        Uses EngineeringOntology for:
        - Abbreviation expansion
        - Action extraction
        - Asset detection
        - Discipline detection
        - Material detection
        - Chainage detection
        - Drawing detection
        - Activity code detection
        
        Args:
            text: Preprocessed input text
            
        Returns:
            dict: Raw Tier 1 feature dictionary
        """
        if not text:
            return {
                "discipline": "",
                "assets": [],
                "actions": [],
                "materials": [],
                "chainages": [],
                "drawings": [],
                "activity_codes": [],
                "expanded_text": "",
            }
        
        # Expand abbreviations
        expanded_text = EngineeringOntology.expand_abbreviations(text)
        
        # Extract features using ontology
        discipline = EngineeringOntology.detect_discipline(expanded_text)
        assets = EngineeringOntology.detect_assets(expanded_text)
        actions = EngineeringOntology.normalize_actions(expanded_text)
        materials = EngineeringOntology.detect_materials(expanded_text)
        chainages = EngineeringOntology.detect_chainages(expanded_text)
        drawings = EngineeringOntology.detect_drawings(expanded_text)
        activity_codes = EngineeringOntology.detect_activity_codes(expanded_text)
        
        # Format chainages as strings
        chainage_strings = [f"{ch[0]} ({ch[1]}+{ch[2]})" for ch in chainages]
        
        return {
            "discipline": discipline if discipline else "",
            "assets": assets if assets else [],
            "actions": actions if actions else [],
            "materials": materials if materials else [],
            "chainages": chainage_strings if chainage_strings else [],
            "drawings": drawings if drawings else [],
            "activity_codes": activity_codes if activity_codes else [],
            "expanded_text": expanded_text,
        }
    
    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """
        Get embedding vector for text using OpenAI.
        
        Args:
            text: Input text
            
        Returns:
            Optional[List[float]]: Embedding vector or None if error
        """
        if not self.openai_client or not text:
            return None
        
        try:
            response = self.openai_client.embeddings.create(
                model=self.embedding_model,  # Azure uses deployment name
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            # Check if it's a quota error
            error_str = str(e)
            if "429" in error_str or "quota" in error_str.lower():
                # Quota error - return None to allow graceful fallback
                return None
            # Other errors - also return None
            return None
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Compute cosine similarity between two vectors.
        
        Args:
            vec1: First vector
            vec2: Second vector
            
        Returns:
            float: Cosine similarity score (0-1)
        """
        if not OPENAI_AVAILABLE or not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        
        vec1_np = np.array(vec1)
        vec2_np = np.array(vec2)
        
        dot_product = np.dot(vec1_np, vec2_np)
        norm1 = norm(vec1_np)
        norm2 = norm(vec2_np)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))
    
    def extract_tier2_embeddings(self, text: str, existing_features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Tier 2: Embedding-based semantic matching for missing fields.
        
        For any missing fields, use embeddings to find closest ontology category.
        Only assigns labels that exist in ontology - never creates new labels.
        
        Args:
            text: Preprocessed input text
            existing_features: Features from Tier 1
            
        Returns:
            dict: Additional features found via semantic matching
        """
        if not self.openai_client or not text:
            return {}
        
        # Check if we actually need to call API (avoid quota errors if not needed)
        if not existing_features.get("discipline") and not existing_features.get("assets") and \
           not existing_features.get("actions") and not existing_features.get("materials"):
            # All critical fields missing, worth trying
            pass
        elif existing_features.get("discipline") and existing_features.get("actions"):
            # Already have key fields, skip to avoid quota usage
            return {}
        
        # Get text embedding
        try:
            text_embedding = self._get_embedding(text)
            if not text_embedding:
                # Quota or API error - return empty to allow Tier 3 to try
                return {}
        except Exception as e:
            # Quota or API error - gracefully skip Tier 2
            return {}
        
        additional_features = {}
        
        # Define ontology categories for each field
        discipline_categories = list(EngineeringOntology.DISCIPLINE_KEYWORDS.keys())
        asset_categories = list(EngineeringOntology.ASSET_KEYWORDS.keys())
        action_categories = list(set(EngineeringOntology.ACTION_MAP.values()))
        material_categories = EngineeringOntology.MATERIAL_KEYWORDS
        
        # Fill missing discipline
        if not existing_features.get("discipline"):
            best_discipline = self._find_best_match(text_embedding, discipline_categories)
            if best_discipline:
                additional_features["discipline"] = best_discipline
        
        # Fill missing assets
        if not existing_features.get("assets"):
            best_assets = self._find_best_matches(text_embedding, asset_categories, top_k=3)
            if best_assets:
                additional_features["assets"] = best_assets
        
        # Fill missing actions
        if not existing_features.get("actions"):
            best_action = self._find_best_match(text_embedding, action_categories)
            if best_action:
                additional_features["actions"] = [best_action]
        
        # Fill missing materials
        if not existing_features.get("materials"):
            best_materials = self._find_best_matches(text_embedding, material_categories, top_k=3)
            if best_materials:
                additional_features["materials"] = best_materials
        
        return additional_features
    
    def _find_best_match(self, text_embedding: List[float], categories: List[str]) -> Optional[str]:
        """
        Find best matching category using cosine similarity.
        
        Args:
            text_embedding: Text embedding vector
            categories: List of category labels
            
        Returns:
            Optional[str]: Best matching category or None
        """
        if not categories:
            return None
        
        best_match = None
        best_score = -1.0
        
        for category in categories:
            category_embedding = self._get_embedding(category)
            if not category_embedding:
                continue
            
            similarity = self._cosine_similarity(text_embedding, category_embedding)
            if similarity > best_score:
                best_score = similarity
                best_match = category
        
        # Only return if similarity is above threshold
        if best_score > 0.5:
            return best_match
        
        return None
    
    def _find_best_matches(self, text_embedding: List[float], categories: List[str], top_k: int = 3) -> List[str]:
        """
        Find top-k best matching categories using cosine similarity.
        
        Args:
            text_embedding: Text embedding vector
            categories: List of category labels
            top_k: Number of top matches to return
            
        Returns:
            List[str]: Top-k matching categories
        """
        if not categories:
            return []
        
        scores = []
        for category in categories:
            category_embedding = self._get_embedding(category)
            if not category_embedding:
                continue
            
            similarity = self._cosine_similarity(text_embedding, category_embedding)
            scores.append((category, similarity))
        
        # Sort by similarity (descending)
        scores.sort(key=lambda x: x[1], reverse=True)
        
        # Return top-k above threshold
        threshold = 0.4
        matches = [cat for cat, score in scores[:top_k] if score > threshold]
        
        return matches
    
    def extract_tier3_llm_reasoning(self, text: str, existing_features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Tier 3: LLM reasoning fallback with strict ontology constraints.
        
        Uses LLM to infer missing features, but ONLY from ontology categories.
        No hallucination allowed - must return valid ontology labels.
        
        Args:
            text: Preprocessed input text
            existing_features: Features from Tier 1 and Tier 2
            
        Returns:
            dict: Additional features found via LLM reasoning
        """
        if not self.openai_client or not text:
            return {}
        
        # Check what's missing
        missing_fields = []
        if not existing_features.get("discipline"):
            missing_fields.append("discipline")
        if not existing_features.get("assets"):
            missing_fields.append("assets")
        if not existing_features.get("actions"):
            missing_fields.append("actions")
        if not existing_features.get("materials"):
            missing_fields.append("materials")
        
        if not missing_fields:
            return {}
        
        # Build ontology category lists
        discipline_categories = list(EngineeringOntology.DISCIPLINE_KEYWORDS.keys())
        asset_categories = list(EngineeringOntology.ASSET_KEYWORDS.keys())
        action_categories = list(set(EngineeringOntology.ACTION_MAP.values()))
        material_categories = EngineeringOntology.MATERIAL_KEYWORDS
        
        # Construct prompt
        prompt = self._build_llm_prompt(
            text,
            existing_features.get("expanded_text", text),
            missing_fields,
            discipline_categories,
            asset_categories,
            action_categories,
            material_categories
        )
        
        # Call LLM
        try:
            response = self.openai_client.chat.completions.create(
                model=self.llm_model,  # Azure uses deployment name
                messages=[
                    {
                        "role": "system",
                        "content": "You are an engineering text analysis system. You must ONLY return valid JSON with ontology-defined categories. Never invent new categories."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,  # Low temperature for deterministic output
                response_format={"type": "json_object"}
            )
            
            result_text = response.choices[0].message.content
            result_dict = json.loads(result_text)
            
            # Validate and filter results to only include ontology categories
            validated_result = self._validate_llm_result(
                result_dict,
                discipline_categories,
                asset_categories,
                action_categories,
                material_categories
            )
            
            return validated_result
            
        except json.JSONDecodeError:
            # Retry once if JSON is invalid
            try:
                response = self.openai_client.chat.completions.create(
                    model=self.llm_model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an engineering text analysis system. You must ONLY return valid JSON with ontology-defined categories. Never invent new categories."
                        },
                        {
                            "role": "user",
                            "content": prompt + "\n\nIMPORTANT: Return ONLY valid JSON, no other text."
                        }
                    ],
                    temperature=0.1,
                    response_format={"type": "json_object"}
                )
                
                result_text = response.choices[0].message.content
                result_dict = json.loads(result_text)
                
                validated_result = self._validate_llm_result(
                    result_dict,
                    discipline_categories,
                    asset_categories,
                    action_categories,
                    material_categories
                )
                
                return validated_result
            except Exception:
                return {}
        
        except Exception:
            return {}
    
    def _build_llm_prompt(
        self,
        text: str,
        expanded_text: str,
        missing_fields: List[str],
        discipline_categories: List[str],
        asset_categories: List[str],
        action_categories: List[str],
        material_categories: List[str]
    ) -> str:
        """
        Build LLM prompt for feature extraction.
        
        Args:
            text: Original text
            expanded_text: Expanded text with abbreviations
            missing_fields: List of missing field names
            discipline_categories: Valid discipline categories
            asset_categories: Valid asset categories
            action_categories: Valid action categories
            material_categories: Valid material categories
            
        Returns:
            str: Formatted prompt
        """
        prompt = f"""Analyze the following engineering text and extract missing features.

Original text: {text}
Expanded text: {expanded_text}

Missing fields to extract: {', '.join(missing_fields)}

You MUST only use categories from the following ontology:

Disciplines (choose ONE): {', '.join(discipline_categories)}
Assets (choose 0-3): {', '.join(asset_categories)}
Actions (choose 0-2): {', '.join(action_categories)}
Materials (choose 0-3): {', '.join(material_categories)}

Return a JSON object with ONLY the missing fields. Use empty string "" for discipline if unsure, empty list [] for lists if unsure.

Example format:
{{
  "discipline": "structures",
  "assets": ["culverts", "bridges"],
  "actions": ["construct"],
  "materials": ["concrete", "steel"]
}}

IMPORTANT:
- Only use categories from the lists above
- Never invent new categories
- Return valid JSON only
- If uncertain, use empty values
"""
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
            result_dict: LLM result dictionary
            discipline_categories: Valid discipline categories
            asset_categories: Valid asset categories
            action_categories: Valid action categories
            material_categories: Valid material categories
            
        Returns:
            dict: Validated result with only ontology categories
        """
        validated = {}
        
        # Validate discipline
        if "discipline" in result_dict:
            disc = result_dict["discipline"]
            if isinstance(disc, str) and disc in discipline_categories:
                validated["discipline"] = disc
            else:
                validated["discipline"] = ""
        
        # Validate assets
        if "assets" in result_dict:
            assets = result_dict["assets"]
            if isinstance(assets, list):
                validated_assets = [a for a in assets if isinstance(a, str) and a in asset_categories]
                validated["assets"] = validated_assets[:3]  # Limit to 3
            else:
                validated["assets"] = []
        
        # Validate actions
        if "actions" in result_dict:
            actions = result_dict["actions"]
            if isinstance(actions, list):
                validated_actions = [a for a in actions if isinstance(a, str) and a in action_categories]
                validated["actions"] = validated_actions[:2]  # Limit to 2
            else:
                validated["actions"] = []
        
        # Validate materials
        if "materials" in result_dict:
            materials = result_dict["materials"]
            if isinstance(materials, list):
                validated_materials = [m for m in materials if isinstance(m, str) and m in material_categories]
                validated["materials"] = validated_materials[:3]  # Limit to 3
            else:
                validated["materials"] = []
        
        return validated
    
    @staticmethod
    def merge_features(*feature_dicts: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge Tier 1, Tier 2, and Tier 3 features into final structured vector.
        
        Canonicalizes lists, ensures no None values, and combines results.
        Later tiers override earlier tiers for the same field.
        
        Args:
            *feature_dicts: Variable number of feature dictionaries to merge
            
        Returns:
            dict: Merged feature dictionary
        """
        merged = {
            "discipline": "",
            "assets": [],
            "actions": [],
            "materials": [],
            "chainages": [],
            "drawings": [],
            "activity_codes": [],
            "expanded_text": "",
            "fallback_used": False,
        }
        
        # Merge dictionaries (later ones override earlier ones)
        for features in feature_dicts:
            if not features:
                continue
            
            # Merge discipline (string)
            if features.get("discipline") and not merged["discipline"]:
                merged["discipline"] = features["discipline"]
            
            # Merge assets (list)
            if features.get("assets"):
                merged["assets"].extend(features["assets"])
            
            # Merge actions (list)
            if features.get("actions"):
                merged["actions"].extend(features["actions"])
            
            # Merge materials (list)
            if features.get("materials"):
                merged["materials"].extend(features["materials"])
            
            # Merge chainages (list)
            if features.get("chainages"):
                merged["chainages"].extend(features["chainages"])
            
            # Merge drawings (list)
            if features.get("drawings"):
                merged["drawings"].extend(features["drawings"])
            
            # Merge activity codes (list)
            if features.get("activity_codes"):
                merged["activity_codes"].extend(features["activity_codes"])
            
            # Merge expanded text
            if features.get("expanded_text") and not merged["expanded_text"]:
                merged["expanded_text"] = features["expanded_text"]
            
            # Track fallback usage
            if features.get("fallback_used"):
                if merged["fallback_used"] == False:
                    merged["fallback_used"] = features["fallback_used"]
                elif merged["fallback_used"] == "semantic" and features["fallback_used"] == "llm":
                    merged["fallback_used"] = "llm"
        
        # Deduplicate and canonicalize lists
        merged["assets"] = sorted(list(set(merged["assets"])))
        merged["actions"] = sorted(list(set(merged["actions"])))
        merged["materials"] = sorted(list(set(merged["materials"])))
        merged["chainages"] = sorted(list(set(merged["chainages"])))
        merged["drawings"] = sorted(list(set(merged["drawings"])))
        merged["activity_codes"] = sorted(list(set(merged["activity_codes"])))
        
        # Ensure no None values
        if merged["discipline"] is None:
            merged["discipline"] = ""
        if merged["expanded_text"] is None:
            merged["expanded_text"] = ""
        
        return merged
    
    def extract_features(self, text: str, section_type: Optional[str] = None) -> Dict[str, Any]:
        """
        MAIN ENTRY POINT: Extract features using three-tier hybrid system.
        
        Process:
        1. Check section_type - if not "scope_work", return empty features
        2. Preprocess text
        3. Run Tier 1 (ontology-based)
        4. Identify missing features
        5. Run Tier 2 (semantic embeddings) if needed
        6. Run Tier 3 (LLM reasoning) if needed
        7. Merge all features
        8. Return final feature vector
        
        Args:
            text: Raw input text
            section_type: Section type from ContractClassifier. If not "scope_work",
                         returns empty features for admin lines.
            
        Returns:
            dict: Complete feature vector with all fields populated
        """
        # Return empty features for non-scope_work sections
        if section_type and section_type != "scope_work":
            return {
                "discipline": "",
                "assets": [],
                "actions": [],
                "materials": [],
                "chainages": [],
                "drawings": [],
                "activity_codes": [],
                "expanded_text": text if text else "",
                "fallback_used": False,
            }
        
        if not text:
            return {
                "discipline": "",
                "assets": [],
                "actions": [],
                "materials": [],
                "chainages": [],
                "drawings": [],
                "activity_codes": [],
                "expanded_text": "",
                "fallback_used": False,
            }
        
        # Preprocess
        preprocessed = self.preprocess_text(text)
        
        # Tier 1: Ontology-based extraction
        tier1_features = self.extract_tier1_ontology(preprocessed)
        tier1_features["fallback_used"] = False
        
        # Check for missing critical fields
        missing_critical = []
        if not tier1_features.get("discipline"):
            missing_critical.append("discipline")
        if not tier1_features.get("assets"):
            missing_critical.append("assets")
        if not tier1_features.get("actions"):
            missing_critical.append("actions")
        if not tier1_features.get("materials"):
            missing_critical.append("materials")
        
        tier2_features = {}
        tier3_features = {}
        
        # NEVER use Tier 2 or Tier 3 in MOCK mode - only use Tier 1 (ontology)
        if AI_MODE == "mock":
            # Skip Tier 2 and Tier 3 - use only Tier 1
            pass
        else:
            # REAL mode: Use Tier 2 and Tier 3 if OpenAI available
            # Tier 2: Semantic embeddings (if OpenAI available and fields missing)
            if missing_critical and self.openai_client:
                tier2_features = self.extract_tier2_embeddings(preprocessed, tier1_features)
                tier2_features["fallback_used"] = "semantic" if tier2_features else False
                
                # Update missing list after Tier 2
                if tier2_features:
                    if tier2_features.get("discipline"):
                        missing_critical = [f for f in missing_critical if f != "discipline"]
                    if tier2_features.get("assets"):
                        missing_critical = [f for f in missing_critical if f != "assets"]
                    if tier2_features.get("actions"):
                        missing_critical = [f for f in missing_critical if f != "actions"]
                    if tier2_features.get("materials"):
                        missing_critical = [f for f in missing_critical if f != "materials"]
            
            # Tier 3: LLM reasoning (if still missing and OpenAI available)
            if missing_critical and self.openai_client:
                # Merge Tier 1 and Tier 2 for LLM context
                combined_features = self.merge_features(tier1_features, tier2_features)
                tier3_features = self.extract_tier3_llm_reasoning(preprocessed, combined_features)
                tier3_features["fallback_used"] = "llm" if tier3_features else False
        
        # Merge all tiers
        final_features = self.merge_features(tier1_features, tier2_features, tier3_features)
        
        # Ensure all fields are present and not None
        final_features.setdefault("discipline", "")
        final_features.setdefault("assets", [])
        final_features.setdefault("actions", [])
        final_features.setdefault("materials", [])
        final_features.setdefault("chainages", [])
        final_features.setdefault("drawings", [])
        final_features.setdefault("activity_codes", [])
        final_features.setdefault("expanded_text", preprocessed)
        final_features.setdefault("fallback_used", False)
        
        return final_features

