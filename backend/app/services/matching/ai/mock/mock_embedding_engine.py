"""
Mock Embedding Similarity Engine for NEC Engineering Analysis System.

Simulates semantic similarity WITHOUT OpenAI using:
- Jaccard Word Overlap
- Sequence Similarity (difflib)
- TF-IDF Cosine Similarity

This is a fallback when OpenAI embeddings are unavailable.
"""

import re
import string
from typing import Dict, List, Any, Set, Tuple
from difflib import SequenceMatcher

try:
    from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore
    from sklearn.metrics.pairwise import cosine_similarity  # type: ignore
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    TfidfVectorizer = None
    cosine_similarity = None

from app.services.extraction.core.ontology import EngineeringOntology


class MockEmbeddingMatcher:
    """
    Mock semantic similarity matcher without OpenAI.
    
    Uses three similarity measures:
    1. Jaccard Word Overlap (40% weight)
    2. Sequence Similarity (30% weight)
    3. TF-IDF Cosine Similarity (30% weight)
    
    Combines them into a final semantic similarity score.
    """
    
    # Weights for combining similarity measures
    WEIGHTS = {
        "jaccard": 0.4,
        "sequence": 0.3,
        "tfidf": 0.3
    }
    
    def __init__(self):
        """
        Initialize mock embedding matcher.
        
        No external dependencies required (sklearn optional).
        """
        self.ontology = EngineeringOntology()
    
    @staticmethod
    def _preprocess_text(text: str) -> str:
        """
        Preprocess text for similarity computation.
        
        Steps:
        1. Lowercase
        2. Remove punctuation
        3. Expand abbreviations using ontology
        4. Normalize whitespace
        
        Args:
            text: Raw input text
            
        Returns:
            str: Preprocessed text
        """
        if not text:
            return ""
        
        # Lowercase
        text = text.lower()
        
        # Expand abbreviations using ontology
        text = EngineeringOntology.expand_abbreviations(text)
        
        # Remove punctuation (keep spaces)
        text = text.translate(str.maketrans('', '', string.punctuation))
        
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
        
        # Split on whitespace and filter empty strings
        words = [w for w in text.split() if w]
        return set(words)
    
    def _compute_jaccard_similarity(
        self,
        text1: str,
        text2: str
    ) -> Tuple[float, List[str]]:
        """
        Compute Jaccard similarity based on word overlap.
        
        Formula:
            jaccard = |intersection(words1, words2)| / |union(words1, words2)|
        
        Args:
            text1: First preprocessed text
            text2: Second preprocessed text
            
        Returns:
            tuple: (similarity_score, overlapping_words)
        """
        if not text1 or not text2:
            return (0.0, [])
        
        words1 = self._tokenize(text1)
        words2 = self._tokenize(text2)
        
        if not words1 or not words2:
            return (0.0, [])
        
        # Compute intersection and union
        intersection = words1 & words2
        union = words1 | words2
        
        if not union:
            return (0.0, [])
        
        # Jaccard similarity
        similarity = len(intersection) / len(union)
        
        # Get overlapping words (sorted for consistency)
        overlapping_words = sorted(list(intersection))
        
        return (similarity, overlapping_words)
    
    def _compute_sequence_similarity(
        self,
        text1: str,
        text2: str
    ) -> float:
        """
        Compute sequence similarity using difflib.SequenceMatcher.
        
        Args:
            text1: First preprocessed text
            text2: Second preprocessed text
            
        Returns:
            float: Sequence similarity score (0.0-1.0)
        """
        if not text1 or not text2:
            return 0.0
        
        if text1 == text2:
            return 1.0
        
        # Use SequenceMatcher to compute ratio
        matcher = SequenceMatcher(None, text1, text2)
        similarity = matcher.ratio()
        
        # Ensure result is between 0.0 and 1.0
        return max(0.0, min(1.0, similarity))
    
    def _compute_tfidf_similarity(
        self,
        text1: str,
        text2: str
    ) -> float:
        """
        Compute TF-IDF cosine similarity.
        
        Args:
            text1: First preprocessed text
            text2: Second preprocessed text
            
        Returns:
            float: TF-IDF cosine similarity score (0.0-1.0)
        """
        if not text1 or not text2:
            return 0.0
        
        if not SKLEARN_AVAILABLE:
            # Fallback: use simple word overlap if sklearn unavailable
            words1 = self._tokenize(text1)
            words2 = self._tokenize(text2)
            
            if not words1 or not words2:
                return 0.0
            
            intersection = len(words1 & words2)
            total = len(words1 | words2)
            
            if total == 0:
                return 0.0
            
            return intersection / total
        
        try:
            # Create TF-IDF vectorizer
            vectorizer = TfidfVectorizer()
            
            # Fit and transform both texts
            tfidf_matrix = vectorizer.fit_transform([text1, text2])
            
            # Compute cosine similarity
            similarity_matrix = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])
            
            # Extract similarity score
            similarity = float(similarity_matrix[0][0])
            
            # Ensure result is between 0.0 and 1.0
            return max(0.0, min(1.0, similarity))
            
        except Exception:
            # If TF-IDF fails, fallback to simple word overlap
            words1 = self._tokenize(text1)
            words2 = self._tokenize(text2)
            
            if not words1 or not words2:
                return 0.0
            
            intersection = len(words1 & words2)
            total = len(words1 | words2)
            
            if total == 0:
                return 0.0
            
            return intersection / total
    
    def compute_embedding_score(
        self,
        scope_text: str,
        activity_text: str
    ) -> Dict[str, Any]:
        """
        MAIN ENTRY POINT: Compute mock semantic similarity score.
        
        Steps:
        1. Preprocess both texts
        2. Compute Jaccard similarity
        3. Compute sequence similarity
        4. Compute TF-IDF similarity
        5. Combine with weights
        6. Generate explanation
        
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
        
        # Preprocess texts
        preprocessed_scope = self._preprocess_text(scope_text)
        preprocessed_activity = self._preprocess_text(activity_text)
        
        # Check if texts are empty after preprocessing
        if not preprocessed_scope or not preprocessed_activity:
            return {
                "embedding_score": 0.0,
                "explanation": "Cannot compute similarity: one or both texts are empty after preprocessing."
            }
        
        # Compute Jaccard similarity
        jaccard_score, overlapping_words = self._compute_jaccard_similarity(
            preprocessed_scope,
            preprocessed_activity
        )
        
        # Compute sequence similarity
        sequence_score = self._compute_sequence_similarity(
            preprocessed_scope,
            preprocessed_activity
        )
        
        # Compute TF-IDF similarity
        tfidf_score = self._compute_tfidf_similarity(
            preprocessed_scope,
            preprocessed_activity
        )
        
        # Combine scores with weights
        final_score = (
            self.WEIGHTS["jaccard"] * jaccard_score +
            self.WEIGHTS["sequence"] * sequence_score +
            self.WEIGHTS["tfidf"] * tfidf_score
        )
        
        # Ensure result is between 0.0 and 1.0
        final_score = max(0.0, min(1.0, final_score))
        
        # Round to 4 decimal places
        final_score = round(final_score, 4)
        
        # Build explanation
        explanation_parts = []
        
        # Add score summary
        explanation_parts.append(
            f"Mock semantic similarity score: {final_score:.4f} "
            f"(Jaccard: {jaccard_score:.4f}, Sequence: {sequence_score:.4f}, TF-IDF: {tfidf_score:.4f})"
        )
        
        # Add overlapping words if any
        if overlapping_words:
            # Limit to top 10 words for readability
            top_words = overlapping_words[:10]
            words_str = ", ".join(top_words)
            if len(overlapping_words) > 10:
                words_str += f" (+{len(overlapping_words) - 10} more)"
            explanation_parts.append(f"Key overlapping words: {words_str}")
        
        # Identify which method contributed most
        contributions = [
            ("Jaccard", jaccard_score * self.WEIGHTS["jaccard"]),
            ("Sequence", sequence_score * self.WEIGHTS["sequence"]),
            ("TF-IDF", tfidf_score * self.WEIGHTS["tfidf"])
        ]
        contributions.sort(key=lambda x: x[1], reverse=True)
        
        if contributions[0][1] > 0:
            explanation_parts.append(
                f"Primary contribution: {contributions[0][0]} similarity "
                f"({contributions[0][1]:.4f})"
            )
        
        # Add overall assessment
        if final_score >= 0.7:
            assessment = "Strong semantic similarity. Texts describe closely related engineering work."
        elif final_score >= 0.5:
            assessment = "Moderate semantic similarity. Texts refer to related construction activities."
        elif final_score >= 0.3:
            assessment = "Weak semantic similarity. Texts share some engineering context."
        else:
            assessment = "Low semantic similarity. Texts describe distinct or unrelated activities."
        
        explanation_parts.append(assessment)
        
        explanation = " ".join(explanation_parts)
        
        return {
            "embedding_score": final_score,
            "explanation": explanation
        }


