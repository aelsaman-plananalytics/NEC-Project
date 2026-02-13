"""
Test script for Weighted Ensemble Decision Engine.

Tests combination of rule-based, embedding, and LLM matching results.
"""

from app.services.matching.engines.ensemble_engine import EnsembleMatcher


def test_ensemble_initialization():
    """Test EnsembleMatcher initialization."""
    print("\n" + "="*70)
    print("TEST 1: EnsembleMatcher Initialization")
    print("="*70)
    
    ensemble = EnsembleMatcher()
    
    print(f"\nRule engine: {type(ensemble.rule_engine).__name__}")
    print(f"Embedding engine: {type(ensemble.embed_engine).__name__}")
    print(f"LLM engine: {type(ensemble.llm_engine).__name__}")
    print(f"\nWeights: {ensemble.WEIGHTS}")
    print(f"Match threshold: {ensemble.MATCH_THRESHOLD}")
    
    assert ensemble.rule_engine is not None
    assert ensemble.embed_engine is not None
    assert ensemble.llm_engine is not None
    assert ensemble.WEIGHTS["rule"] == 0.55
    assert ensemble.WEIGHTS["embedding"] == 0.25
    assert ensemble.WEIGHTS["llm"] == 0.20


def test_evaluate_all_engines_agree():
    """Test Case 1: All engines agree (high scores)."""
    print("\n" + "="*70)
    print("TEST 2: All Engines Agree (High Scores)")
    print("="*70)
    
    ensemble = EnsembleMatcher()
    
    scope_text = "Construct reinforced concrete culvert at chainage 123+450"
    activity_text = "Build RC culvert at Ch 123+450"
    
    scope_features = {
        "discipline": "drainage",
        "assets": ["culvert"],
        "actions": ["construct"],
        "materials": ["rc"],
        "chainages": ["Ch 123+450"],
        "drawings": ["DRG-102"],
        "activity_codes": ["STR-001"]
    }
    
    activity_features = {
        "discipline": "drainage",
        "assets": ["culvert"],
        "actions": ["construct"],
        "materials": ["rc"],
        "chainages": ["Ch 123+450"],
        "drawings": ["DRG-102"],
        "activity_codes": ["STR-001"]
    }
    
    result = ensemble.evaluate(scope_text, activity_text, scope_features, activity_features)
    
    print(f"\nResult:")
    print(f"  Final Score: {result['final_score']}")
    print(f"  Match: {result['match']}")
    print(f"  Components:")
    print(f"    Rule Score: {result['components']['rule_score']}")
    print(f"    Embedding Score: {result['components']['embedding_score']}")
    print(f"    LLM Score: {result['components']['llm_score']}")
    print(f"\n  Reasoning ({len(result['reasoning'])} items):")
    for i, reason in enumerate(result['reasoning'][:3], 1):
        print(f"    {i}. {reason[:80]}...")
    
    assert 0.0 <= result['final_score'] <= 1.0
    assert isinstance(result['match'], bool)
    assert 'components' in result
    assert 'reasoning' in result
    assert isinstance(result['reasoning'], list)
    
    # With all features matching, rule score should be high
    # Final score should be high if rule score is high (even if embeddings/LLM are 0)
    if result['components']['rule_score'] >= 0.8:
        assert result['final_score'] >= 0.4  # At least 0.55 * 0.8 = 0.44


def test_evaluate_rule_only():
    """Test Case 2: Rule engine strong, others disabled."""
    print("\n" + "="*70)
    print("TEST 3: Rule Engine Strong, Others Disabled")
    print("="*70)
    
    ensemble = EnsembleMatcher()
    
    scope_text = "Construct culvert"
    activity_text = "Build culvert"
    
    scope_features = {
        "discipline": "drainage",
        "assets": ["culvert"],
        "actions": ["construct"],
        "materials": ["rc"],
        "chainages": [],
        "drawings": [],
        "activity_codes": []
    }
    
    activity_features = {
        "discipline": "drainage",
        "assets": ["culvert"],
        "actions": ["construct"],
        "materials": ["rc"],
        "chainages": [],
        "drawings": [],
        "activity_codes": []
    }
    
    result = ensemble.evaluate(scope_text, activity_text, scope_features, activity_features)
    
    print(f"\nResult:")
    print(f"  Final Score: {result['final_score']}")
    print(f"  Match: {result['match']}")
    print(f"  Components:")
    print(f"    Rule Score: {result['components']['rule_score']}")
    print(f"    Embedding Score: {result['components']['embedding_score']}")
    print(f"    LLM Score: {result['components']['llm_score']}")
    
    # Rule score should dominate
    # If rule_score = 1.0, final_score = 0.55 * 1.0 + 0.25 * 0.0 + 0.20 * 0.0 = 0.55
    # If rule_score = 0.8, final_score = 0.55 * 0.8 = 0.44
    rule_score = result['components']['rule_score']
    embedding_score = result['components']['embedding_score']
    llm_score = result['components']['llm_score']
    
    # Calculate expected score
    expected_score = 0.55 * rule_score + 0.25 * embedding_score + 0.20 * llm_score
    expected_score = round(expected_score, 4)
    
    # Allow small floating point differences
    assert abs(result['final_score'] - expected_score) < 0.0001
    assert isinstance(result['match'], bool)
    assert isinstance(result['reasoning'], list)


def test_evaluate_all_zero():
    """Test Case 3: All scores zero."""
    print("\n" + "="*70)
    print("TEST 4: All Scores Zero")
    print("="*70)
    
    ensemble = EnsembleMatcher()
    
    scope_text = "Construct culvert"
    activity_text = "Install electrical cables"
    
    scope_features = {
        "discipline": "drainage",
        "assets": ["culvert"],
        "actions": ["construct"],
        "materials": ["rc"],
        "chainages": [],
        "drawings": [],
        "activity_codes": []
    }
    
    activity_features = {
        "discipline": "m&e",
        "assets": ["cable"],
        "actions": ["install"],
        "materials": ["copper"],
        "chainages": [],
        "drawings": [],
        "activity_codes": []
    }
    
    result = ensemble.evaluate(scope_text, activity_text, scope_features, activity_features)
    
    print(f"\nResult:")
    print(f"  Final Score: {result['final_score']}")
    print(f"  Match: {result['match']}")
    print(f"  Components:")
    print(f"    Rule Score: {result['components']['rule_score']}")
    print(f"    Embedding Score: {result['components']['embedding_score']}")
    print(f"    LLM Score: {result['components']['llm_score']}")
    
    # Even if all scores are low, final_score should be computed correctly
    assert 0.0 <= result['final_score'] <= 1.0
    # If all components are 0, final_score should be 0
    if (result['components']['rule_score'] == 0.0 and
        result['components']['embedding_score'] == 0.0 and
        result['components']['llm_score'] == 0.0):
        assert result['final_score'] == 0.0
        assert result['match'] == False


def test_error_handling():
    """Test error handling."""
    print("\n" + "="*70)
    print("TEST 5: Error Handling")
    print("="*70)
    
    ensemble = EnsembleMatcher()
    
    # Test 5.1: Empty inputs
    result1 = ensemble.evaluate("", "", {}, {})
    print(f"\nTest 5.1 - Empty inputs:")
    print(f"  Final Score: {result1['final_score']}")
    print(f"  Match: {result1['match']}")
    assert 'final_score' in result1
    assert 'match' in result1
    assert 'components' in result1
    assert 'reasoning' in result1
    
    # Test 5.2: None values never returned
    result2 = ensemble.evaluate("test", "test", {}, {})
    print(f"\nTest 5.2 - No None values:")
    print(f"  Final Score is None: {result2['final_score'] is None}")
    print(f"  Match is None: {result2['match'] is None}")
    print(f"  Components is None: {result2['components'] is None}")
    print(f"  Reasoning is None: {result2['reasoning'] is None}")
    assert result2['final_score'] is not None
    assert result2['match'] is not None
    assert result2['components'] is not None
    assert result2['reasoning'] is not None
    
    # Test 5.3: Missing fields in features
    result3 = ensemble.evaluate("test", "test", None, None)
    print(f"\nTest 5.3 - Missing fields:")
    print(f"  Final Score: {result3['final_score']}")
    assert 'final_score' in result3
    assert 'match' in result3


def test_weight_calculation():
    """Test weight calculation accuracy."""
    print("\n" + "="*70)
    print("TEST 6: Weight Calculation Accuracy")
    print("="*70)
    
    ensemble = EnsembleMatcher()
    
    # Test with known scores
    scope_features = {
        "discipline": "drainage",
        "assets": ["culvert"],
        "actions": ["construct"],
        "materials": ["rc"],
        "chainages": ["Ch 123+450"],
        "drawings": [],
        "activity_codes": []
    }
    
    activity_features = {
        "discipline": "drainage",
        "assets": ["culvert"],
        "actions": ["construct"],
        "materials": ["rc"],
        "chainages": ["Ch 123+450"],
        "drawings": [],
        "activity_codes": []
    }
    
    result = ensemble.evaluate("test", "test", scope_features, activity_features)
    
    rule_score = result['components']['rule_score']
    embedding_score = result['components']['embedding_score']
    llm_score = result['components']['llm_score']
    final_score = result['final_score']
    
    # Calculate expected score
    expected_score = (
        0.55 * rule_score +
        0.25 * embedding_score +
        0.20 * llm_score
    )
    expected_score = round(expected_score, 4)
    
    print(f"\nWeight Calculation:")
    print(f"  Rule Score: {rule_score} (weight: 0.55)")
    print(f"  Embedding Score: {embedding_score} (weight: 0.25)")
    print(f"  LLM Score: {llm_score} (weight: 0.20)")
    print(f"  Expected Final Score: {expected_score}")
    print(f"  Actual Final Score: {final_score}")
    
    # Allow small floating point differences
    assert abs(final_score - expected_score) < 0.0001


if __name__ == "__main__":
    print("\n" + "="*70)
    print("WEIGHTED ENSEMBLE DECISION ENGINE TEST SUITE")
    print("="*70)
    
    try:
        test_ensemble_initialization()
        test_evaluate_all_engines_agree()
        test_evaluate_rule_only()
        test_evaluate_all_zero()
        test_error_handling()
        test_weight_calculation()
        
        print("\n" + "="*70)
        print("✓ ALL TESTS PASSED")
        print("="*70)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

