"""
Weighted Ensemble Decision Engine for NEC Engineering Analysis System.

Combines rule-based, embedding-based, and LLM-based matching results
into a final weighted match score and decision.
"""

import os
import logging
from typing import Dict, List, Any, Optional

from app.services.matching.engines.rule_engine import RuleBasedMatcher

# AI Mode: "real" for OpenAI, "mock" for deterministic mock engines
AI_MODE = os.getenv("AI_MODE", "mock").lower().strip()

# Set up logger
logger = logging.getLogger(__name__)

# Conditionally import engines based on AI_MODE to prevent any fallback
if AI_MODE == "mock":
    # MOCK MODE: Only import mock engines
    from app.services.matching.ai.mock.mock_embedding_engine import MockEmbeddingMatcher
    from app.services.matching.ai.mock.mock_llm_engine import MockLLMValidator
    # DO NOT import real engines in mock mode
    EmbeddingMatcher = None
    LLMEngineeringValidator = None
    logger.info("=" * 60)
    logger.info("AI_MODE = 'mock' - Using MOCK engines (no OpenAI)")
    logger.info("  - RuleBasedMatcher (deterministic)")
    logger.info("  - MockEmbeddingMatcher (Jaccard + TF-IDF)")
    logger.info("  - MockLLMValidator (synonym-based reasoning)")
    logger.info("=" * 60)
elif AI_MODE == "real":
    # REAL MODE: Only import real OpenAI engines
    from app.services.matching.ai.openai.openai_embedding_engine import EmbeddingMatcher
    from app.services.matching.ai.openai.openai_llm_engine import LLMEngineeringValidator
    # DO NOT import mock engines in real mode
    MockEmbeddingMatcher = None
    MockLLMValidator = None
    logger.info("=" * 60)
    logger.info("AI_MODE = 'real' - Using REAL OpenAI engines")
    logger.info("  - RuleBasedMatcher (deterministic)")
    logger.info("  - EmbeddingMatcher (OpenAI text-embedding-3-large)")
    logger.info("  - LLMEngineeringValidator (OpenAI gpt-4o)")
    logger.info("=" * 60)
else:
    # Invalid mode - default to mock for safety
    logger.warning(f"Invalid AI_MODE='{AI_MODE}'. Defaulting to 'mock' mode.")
    AI_MODE = "mock"
    from app.services.matching.ai.mock.mock_embedding_engine import MockEmbeddingMatcher
    from app.services.matching.ai.mock.mock_llm_engine import MockLLMValidator
    EmbeddingMatcher = None
    LLMEngineeringValidator = None
    logger.info("=" * 60)
    logger.info("AI_MODE = 'mock' (default) - Using MOCK engines")
    logger.info("=" * 60)


class EnsembleMatcher:
    """
    Weighted ensemble matcher combining multiple matching signals.
    
    Combines:
    - Rule-based matching (deterministic engineering logic)
    - Embedding-based matching (semantic similarity)
    - LLM-based matching (reasoning and validation)
    
    Uses weighted combination:
    - Rule: 55% (0.55)
    - Embedding: 25% (0.25)
    - LLM: 20% (0.20)
    """
    
    # Ensemble weights
    WEIGHTS = {
        "rule": 0.55,
        "embedding": 0.25,
        "llm": 0.20
    }
    
    # Match threshold
    MATCH_THRESHOLD = 0.5
    
    def __init__(self):
        """
        Initialize all sub-engines.
        
        Creates instances of:
        - RuleBasedMatcher (always available)
        - EmbeddingMatcher or MockEmbeddingMatcher (based on AI_MODE)
        - LLMEngineeringValidator or MockLLMValidator (based on AI_MODE)
        
        AI_MODE environment variable:
        - "real": Use OpenAI-based engines (requires OPENAI_API_KEY)
        - "mock": Use deterministic mock engines (no OpenAI required)
        
        STRICT ENFORCEMENT:
        - In "mock" mode: ONLY mock engines are imported and used
        - In "real" mode: ONLY real engines are imported and used
        - NO fallback between modes
        """
        self.rule_engine = RuleBasedMatcher()
        
        # STRICT MODE ENFORCEMENT - No fallback allowed
        if AI_MODE == "mock":
            # MOCK MODE: Only use mock engines
            if MockEmbeddingMatcher is None or MockLLMValidator is None:
                raise ImportError(
                    "MOCK engines not available. Cannot initialize EnsembleMatcher in mock mode."
                )
            self.embed_engine = MockEmbeddingMatcher()
            self.llm_engine = MockLLMValidator()
            logger.info("[EnsembleMatcher] Initialized with MOCK engines")
            
        elif AI_MODE == "real":
            # REAL MODE: Only use real OpenAI engines
            if EmbeddingMatcher is None or LLMEngineeringValidator is None:
                raise ImportError(
                    "REAL OpenAI engines not available. Cannot initialize EnsembleMatcher in real mode. "
                    "Set AI_MODE=mock to use mock engines instead."
                )
            self.embed_engine = EmbeddingMatcher()
            self.llm_engine = LLMEngineeringValidator()
            logger.info("[EnsembleMatcher] Initialized with REAL OpenAI engines")
            
        else:
            # This should never happen due to validation above, but safety check
            raise ValueError(
                f"Invalid AI_MODE='{AI_MODE}'. Must be 'mock' or 'real'."
            )
    
    def evaluate(
        self,
        scope_text: str,
        activity_text: str,
        scope_features: Dict[str, Any],
        activity_features: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        MAIN ENTRY POINT: Compute weighted ensemble match score.
        
        Steps:
        1. Compute rule-based match score
        2. Compute embedding semantic match score
        3. Compute LLM reasoning match score
        4. Apply weights and compute final score
        5. Determine match decision (>= threshold)
        6. Combine all explanations/reasoning
        
        Args:
            scope_text: Original scope item text
            activity_text: Original activity item text
            scope_features: Extracted scope features
            activity_features: Extracted activity features
            
        Returns:
            dict: {
                "final_score": float (0.0-1.0),
                "match": bool,
                "components": {
                    "rule_score": float,
                    "embedding_score": float,
                    "llm_score": float
                },
                "reasoning": list[str]
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
        
        # Step 1: Compute rule-based match
        rule_result = self.rule_engine.compute_rule_score(
            scope_features,
            activity_features
        )
        rule_score = rule_result.get("rule_score", 0.0)
        if not isinstance(rule_score, (int, float)):
            rule_score = 0.0
        rule_score = max(0.0, min(1.0, float(rule_score)))
        
        # Step 2: Compute embedding semantic match
        embed_result = self.embed_engine.compute_embedding_score(
            scope_text,
            activity_text
        )
        embedding_score = embed_result.get("embedding_score", 0.0)
        if not isinstance(embedding_score, (int, float)):
            embedding_score = 0.0
        embedding_score = max(0.0, min(1.0, float(embedding_score)))
        
        # Step 3: Compute LLM reasoning match
        llm_result = self.llm_engine.evaluate(
            scope_text,
            activity_text,
            scope_features,
            activity_features
        )
        llm_score = llm_result.get("llm_score", 0.0)
        if not isinstance(llm_score, (int, float)):
            llm_score = 0.0
        llm_score = max(0.0, min(1.0, float(llm_score)))
        
        # Step 4: Apply weights and compute final score
        final_score = (
            self.WEIGHTS["rule"] * rule_score +
            self.WEIGHTS["embedding"] * embedding_score +
            self.WEIGHTS["llm"] * llm_score
        )
        
        # Ensure final score is between 0.0 and 1.0
        final_score = max(0.0, min(1.0, final_score))
        final_score = round(final_score, 4)
        
        # Step 5: Determine match decision
        match = final_score >= self.MATCH_THRESHOLD
        
        # Step 6: Build reasoning list
        reasoning = []
        
        # Add rule-based explanations
        rule_explanations = rule_result.get("explanations", [])
        if isinstance(rule_explanations, list):
            for exp in rule_explanations:
                if isinstance(exp, str) and exp.strip():
                    reasoning.append(f"[Rule] {exp.strip()}")
        elif isinstance(rule_explanations, str):
            reasoning.append(f"[Rule] {rule_explanations.strip()}")
        
        # Add embedding explanation
        embed_explanation = embed_result.get("explanation", "")
        if isinstance(embed_explanation, str) and embed_explanation.strip():
            reasoning.append(f"[Embedding] {embed_explanation.strip()}")
        
        # Add LLM reasoning
        llm_reasoning = llm_result.get("llm_reasoning", "")
        if isinstance(llm_reasoning, str) and llm_reasoning.strip():
            reasoning.append(f"[LLM] {llm_reasoning.strip()}")
        
        # If no reasoning was collected, add default
        if not reasoning:
            reasoning.append("No detailed reasoning available.")
        
        # Build components dict
        components = {
            "rule_score": round(rule_score, 4),
            "embedding_score": round(embedding_score, 4),
            "llm_score": round(llm_score, 4)
        }
        
        return {
            "final_score": final_score,
            "match": match,
            "components": components,
            "reasoning": reasoning
        }



