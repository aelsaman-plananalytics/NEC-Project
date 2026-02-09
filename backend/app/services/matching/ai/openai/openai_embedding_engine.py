"""
Embedding Similarity Engine for NEC Engineering Analysis System.

Computes semantic similarity between scope and activity text using
OpenAI embeddings and cosine similarity.
"""

import re
import os
import math
from typing import Dict, List, Optional, Any

try:
    from openai import AzureOpenAI, OpenAI
    import numpy as np
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    AzureOpenAI = None
    OpenAI = None
    np = None

from app.services.extraction.core.ontology import EngineeringOntology

try:
    from app.config import settings
except ImportError:
    # Fallback if config not available
    class Settings:
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    settings = Settings()


class EmbeddingMatcher:
    """
    Semantic similarity matcher using OpenAI embeddings.
    
    Compares scope and activity text by:
    1. Preprocessing and expanding abbreviations
    2. Generating embeddings for both texts
    3. Computing cosine similarity
    4. Returning semantic match score (0.0-1.0)
    """
    
    def __init__(self):
        """
        Initialize embedding client.
        
        If OPENAI_API_KEY missing:
        - set embeddings_enabled = False
        - system falls back safely
        """
        import os
        from dotenv import load_dotenv
        
        self.embeddings_enabled = False
        self.openai_client = None
        self.embedding_model = "text-embedding-3-large"  # Default, will be overridden for Azure
        
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
                    self.embedding_model = azure_deployment  # Use same deployment for embeddings
                    self.embeddings_enabled = True
                except Exception as e:
                    self.openai_client = None
                    self.embeddings_enabled = False
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
                    self.embeddings_enabled = True
                except Exception as e:
                    self.openai_client = None
                    self.embeddings_enabled = False
            else:
                self.embeddings_enabled = False
    
    @staticmethod
    def _preprocess_text(text: str) -> str:
        """
        Preprocess text for embedding generation.
        
        Steps:
        1. Lowercase
        2. Strip whitespace
        3. Normalize punctuation
        4. Expand abbreviations using ontology
        
        Args:
            text: Raw input text
            
        Returns:
            str: Preprocessed and expanded text
        """
        if not text:
            return ""
        
        # Lowercase
        text = text.lower()
        
        # Strip whitespace
        text = text.strip()
        
        # Normalize whitespace (collapse multiple spaces)
        text = re.sub(r'\s+', ' ', text)
        
        # Normalize punctuation (remove extra punctuation, keep essential)
        text = re.sub(r'[^\w\s\-\(\)\+\.,]', ' ', text)
        
        # Expand abbreviations using ontology
        expanded_text = EngineeringOntology.expand_abbreviations(text)
        
        # Final trim
        expanded_text = expanded_text.strip()
        
        return expanded_text
    
    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """
        Get embedding vector for text using OpenAI API.
        
        Uses model: 'text-embedding-3-large'
        
        Args:
            text: Input text to embed
            
        Returns:
            Optional[List[float]]: Embedding vector or None if error
        """
        if not self.embeddings_enabled or not self.openai_client or not text:
            return None
        
        try:
            response = self.openai_client.embeddings.create(
                model=self.embedding_model,  # Azure uses deployment name
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            # Handle quota errors, API errors, etc.
            # Return None to allow graceful fallback
            return None
    
    @staticmethod
    def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """
        Compute cosine similarity between two vectors.
        
        Formula:
            similarity = dot(v1, v2) / (||v1|| * ||v2||)
        
        Args:
            vec1: First embedding vector
            vec2: Second embedding vector
            
        Returns:
            float: Cosine similarity score (0.0-1.0)
        """
        if not vec1 or not vec2:
            return 0.0
        
        if len(vec1) != len(vec2):
            return 0.0
        
        # Use numpy if available for efficiency
        if OPENAI_AVAILABLE and np is not None:
            try:
                vec1_np = np.array(vec1)
                vec2_np = np.array(vec2)
                
                dot_product = np.dot(vec1_np, vec2_np)
                norm1 = np.linalg.norm(vec1_np)
                norm2 = np.linalg.norm(vec2_np)
                
                if norm1 == 0 or norm2 == 0:
                    return 0.0
                
                similarity = float(dot_product / (norm1 * norm2))
                # Ensure result is between 0.0 and 1.0
                return max(0.0, min(1.0, similarity))
            except Exception:
                # Fallback to manual calculation
                pass
        
        # Manual calculation (fallback if numpy unavailable)
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        similarity = dot_product / (norm1 * norm2)
        # Ensure result is between 0.0 and 1.0
        return max(0.0, min(1.0, similarity))
    
    def compute_embedding_score(
        self,
        scope_text: str,
        activity_text: str
    ) -> Dict[str, Any]:
        """
        MAIN ENTRY POINT: Compute semantic similarity score.
        
        Steps:
        1. Preprocess scope_text and activity_text
        2. Generate embeddings for each
        3. Compute cosine similarity
        4. Return score and explanation
        
        Args:
            scope_text: Raw scope item text
            activity_text: Raw activity item text
            
        Returns:
            dict: {
                "embedding_score": float (0.0-1.0),
                "explanation": str
            }
        """
        # Handle empty inputs
        if not scope_text:
            scope_text = ""
        if not activity_text:
            activity_text = ""
        
        # Check if embeddings are enabled
        if not self.embeddings_enabled:
            return {
                "embedding_score": 0.0,
                "explanation": "Embeddings disabled: OpenAI API key not available. Semantic matching unavailable."
            }
        
        # Preprocess texts
        preprocessed_scope = self._preprocess_text(scope_text)
        preprocessed_activity = self._preprocess_text(activity_text)
        
        # Check if texts are empty after preprocessing
        if not preprocessed_scope or not preprocessed_activity:
            return {
                "embedding_score": 0.0,
                "explanation": "Cannot compute similarity: one or both texts are empty after preprocessing."
            }
        
        # Generate embeddings
        scope_embedding = self._get_embedding(preprocessed_scope)
        activity_embedding = self._get_embedding(preprocessed_activity)
        
        # Check if embeddings were generated successfully
        if not scope_embedding or not activity_embedding:
            return {
                "embedding_score": 0.0,
                "explanation": "Cannot compute similarity: failed to generate embeddings (API error or quota exceeded)."
            }
        
        # Compute cosine similarity
        similarity = self._cosine_similarity(scope_embedding, activity_embedding)
        
        # Round to 4 decimal places
        similarity = round(similarity, 4)
        
        # Generate explanation based on score
        if similarity >= 0.8:
            explanation = f"Strong semantic similarity (score: {similarity:.2f}). Texts describe closely related engineering work."
        elif similarity >= 0.6:
            explanation = f"Moderate semantic similarity (score: {similarity:.2f}). Texts refer to related construction activities in the same domain."
        elif similarity >= 0.4:
            explanation = f"Weak semantic similarity (score: {similarity:.2f}). Texts describe different elements but may share some engineering context."
        else:
            explanation = f"Low semantic similarity (score: {similarity:.2f}). Texts describe unrelated or distinct construction activities."
        
        return {
            "embedding_score": similarity,
            "explanation": explanation
        }



