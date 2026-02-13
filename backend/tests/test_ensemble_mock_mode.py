"""
Test script for Ensemble Engine with Mock AI Mode.

Tests that the ensemble engine correctly switches between real and mock AI engines.
"""

import os
from app.services.matching.engines.ensemble_engine import EnsembleMatcher, AI_MODE


def test_ai_mode_detection():
    """Test that AI_MODE is correctly detected."""
    print("\n" + "="*70)
    print("TEST 1: AI Mode Detection")
    print("="*70)
    
    print(f"\nCurrent AI_MODE: {AI_MODE}")
    print(f"AI_MODE type: {type(AI_MODE)}")
    
    assert AI_MODE in ["real", "mock"]
    print(f"\n✓ AI_MODE is valid: {AI_MODE}")


def test_ensemble_initialization():
    """Test ensemble engine initialization with current AI_MODE."""
    print("\n" + "="*70)
    print("TEST 2: Ensemble Engine Initialization")
    print("="*70)
    
    engine = EnsembleMatcher()
    
    print(f"\nAI_MODE: {AI_MODE}")
    print(f"Rule engine: {type(engine.rule_engine).__name__}")
    print(f"Embedding engine: {type(engine.embed_engine).__name__}")
    print(f"LLM engine: {type(engine.llm_engine).__name__}")
    
    # Rule engine should always be RuleBasedMatcher
    assert type(engine.rule_engine).__name__ == "RuleBasedMatcher"
    
    # Check embedding engine
    if AI_MODE == "mock":
        assert type(engine.embed_engine).__name__ == "MockEmbeddingMatcher"
        print("\n✓ Using MockEmbeddingMatcher (mock mode)")
    else:
        assert type(engine.embed_engine).__name__ == "EmbeddingMatcher"
        print("\n✓ Using EmbeddingMatcher (real mode)")
    
    # Check LLM engine
    if AI_MODE == "mock":
        assert type(engine.llm_engine).__name__ == "MockLLMValidator"
        print("✓ Using MockLLMValidator (mock mode)")
    else:
        assert type(engine.llm_engine).__name__ == "LLMEngineeringValidator"
        print("✓ Using LLMEngineeringValidator (real mode)")


def test_ensemble_evaluation():
    """Test ensemble evaluation with current AI_MODE."""
    print("\n" + "="*70)
    print("TEST 3: Ensemble Evaluation")
    print("="*70)
    
    engine = EnsembleMatcher()
    
    scope_text = "Construct reinforced concrete culvert at chainage 123+450"
    activity_text = "Build RC culvert at Ch 123+450"
    
    scope_features = {
        "discipline": "drainage",
        "assets": ["culvert"],
        "actions": ["construct"],
        "materials": ["reinforced concrete"],
        "chainages": ["123+450"]
    }
    
    activity_features = {
        "discipline": "drainage",
        "assets": ["culvert"],
        "actions": ["build"],
        "materials": ["RC"],
        "chainages": ["123+450"]
    }
    
    result = engine.evaluate(
        scope_text,
        activity_text,
        scope_features,
        activity_features
    )
    
    print(f"\nAI_MODE: {AI_MODE}")
    print(f"\nScope text: '{scope_text}'")
    print(f"Activity text: '{activity_text}'")
    print(f"\nResult:")
    print(f"  Final score: {result['final_score']}")
    print(f"  Match: {result['match']}")
    print(f"  Components:")
    print(f"    Rule score: {result['components']['rule_score']}")
    print(f"    Embedding score: {result['components']['embedding_score']}")
    print(f"    LLM score: {result['components']['llm_score']}")
    print(f"  Reasoning: {len(result['reasoning'])} items")
    
    # Verify result structure
    assert 'final_score' in result
    assert 'match' in result
    assert 'components' in result
    assert 'reasoning' in result
    assert 0.0 <= result['final_score'] <= 1.0
    assert isinstance(result['match'], bool)
    assert isinstance(result['components'], dict)
    assert isinstance(result['reasoning'], list)
    
    print("\n✓ Result structure is valid")
    
    # In mock mode, scores should be deterministic and reasonable
    if AI_MODE == "mock":
        print("\n✓ Mock mode: Using deterministic engines")
        # Mock engines should produce scores
        assert result['components']['embedding_score'] >= 0.0
        assert result['components']['llm_score'] >= 0.0


def test_ensemble_with_empty_inputs():
    """Test ensemble with empty inputs."""
    print("\n" + "="*70)
    print("TEST 4: Ensemble with Empty Inputs")
    print("="*70)
    
    engine = EnsembleMatcher()
    
    result = engine.evaluate("", "", {}, {})
    
    print(f"\nResult:")
    print(f"  Final score: {result['final_score']}")
    print(f"  Match: {result['match']}")
    print(f"  Components: {result['components']}")
    
    assert 'final_score' in result
    assert 0.0 <= result['final_score'] <= 1.0
    print("\n✓ Handles empty inputs gracefully")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("ENSEMBLE ENGINE MOCK AI MODE TEST SUITE")
    print("="*70)
    print(f"\nCurrent AI_MODE: {AI_MODE}")
    print("(Set AI_MODE environment variable to 'mock' or 'real' to switch modes)")
    
    try:
        test_ai_mode_detection()
        test_ensemble_initialization()
        test_ensemble_evaluation()
        test_ensemble_with_empty_inputs()
        
        print("\n" + "="*70)
        print("✓ ALL TESTS PASSED")
        print("="*70)
        print(f"\nCurrent mode: {AI_MODE}")
        if AI_MODE == "mock":
            print("Using mock engines (no OpenAI required)")
        else:
            print("Using real OpenAI engines (requires API key)")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

