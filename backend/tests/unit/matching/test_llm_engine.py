"""
Test script for LLM Engineering Validator.

Tests strict engineering reasoning for scope-activity matching.
"""

from app.services.matching.ai.openai import LLMEngineeringValidator


def test_llm_validator_initialization():
    """Test LLMEngineeringValidator initialization."""
    print("\n" + "="*70)
    print("TEST 1: LLMEngineeringValidator Initialization")
    print("="*70)
    
    validator = LLMEngineeringValidator()
    
    print(f"\nLLM enabled: {validator.llm_enabled}")
    print(f"OpenAI client available: {validator.openai_client is not None}")
    print(f"LLM model: {validator.llm_model}")
    
    if validator.llm_enabled:
        print("✓ LLM is enabled and ready")
    else:
        print("⚠ LLM disabled (OpenAI API key not available)")
        print("  This is expected if API key is missing or quota exceeded")


def test_prompt_building():
    """Test prompt building."""
    print("\n" + "="*70)
    print("TEST 2: Prompt Building")
    print("="*70)
    
    validator = LLMEngineeringValidator()
    
    scope_text = "Construct reinforced concrete culvert at chainage 123+450"
    activity_text = "Build RC culvert at Ch 123+450"
    
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
    
    prompt = validator._build_prompt(
        scope_text,
        activity_text,
        scope_features,
        activity_features,
        None  # Ontology not needed for prompt building
    )
    
    print(f"\nPrompt length: {len(prompt)} characters")
    print(f"Prompt contains scope text: {'scope_text' in prompt.lower() or scope_text.lower()[:20] in prompt.lower()}")
    print(f"Prompt contains activity text: {'activity_text' in prompt.lower() or activity_text.lower()[:20] in prompt.lower()}")
    print(f"Prompt contains ontology categories: {'disciplines' in prompt.lower()}")
    print(f"Prompt demands JSON: {'json' in prompt.lower()}")
    
    assert len(prompt) > 100  # Prompt should be substantial
    assert "json" in prompt.lower()
    assert "ontology" in prompt.lower() or "categories" in prompt.lower()


def test_evaluate_disabled():
    """Test evaluate when LLM is disabled."""
    print("\n" + "="*70)
    print("TEST 3: Evaluate with LLM Disabled")
    print("="*70)
    
    validator = LLMEngineeringValidator()
    
    if validator.llm_enabled:
        print("\n⚠ Skipping test - LLM is enabled")
        return
    
    scope_text = "Construct culvert"
    activity_text = "Build culvert"
    
    scope_features = {"discipline": "drainage", "assets": ["culvert"]}
    activity_features = {"discipline": "drainage", "assets": ["culvert"]}
    
    result = validator.evaluate(scope_text, activity_text, scope_features, activity_features)
    
    print(f"\nResult:")
    print(f"  LLM Score: {result['llm_score']}")
    print(f"  LLM Match: {result['llm_match']}")
    print(f"  LLM Reasoning: {result['llm_reasoning']}")
    print(f"  Filled Features: {result['filled_features']}")
    
    assert result['llm_score'] == 0.0
    assert result['llm_match'] == False
    assert 'llm_reasoning' in result
    assert 'filled_features' in result
    assert result['filled_features']['discipline'] == ""
    assert isinstance(result['filled_features']['assets'], list)


def test_evaluate_enabled():
    """Test evaluate when LLM is enabled."""
    print("\n" + "="*70)
    print("TEST 4: Evaluate with LLM Enabled")
    print("="*70)
    
    validator = LLMEngineeringValidator()
    
    if not validator.llm_enabled:
        print("\n⚠ Skipping test - LLM is disabled")
        print("  This is expected if API key is missing or quota exceeded")
        return
    
    # Test 4.1: Similar items (should match)
    scope_text1 = "Construct reinforced concrete culvert at chainage 123+450"
    activity_text1 = "Build RC culvert at Ch 123+450"
    
    scope_features1 = {
        "discipline": "drainage",
        "assets": ["culvert"],
        "actions": ["construct"],
        "materials": ["rc"],
        "chainages": ["Ch 123+450"],
        "drawings": [],
        "activity_codes": []
    }
    
    activity_features1 = {
        "discipline": "drainage",
        "assets": ["culvert"],
        "actions": ["construct"],
        "materials": ["rc"],
        "chainages": ["Ch 123+450"],
        "drawings": [],
        "activity_codes": []
    }
    
    result1 = validator.evaluate(scope_text1, activity_text1, scope_features1, activity_features1)
    
    print(f"\nTest 4.1 - Similar items:")
    print(f"  Scope: '{scope_text1}'")
    print(f"  Activity: '{activity_text1}'")
    print(f"  LLM Score: {result1['llm_score']}")
    print(f"  LLM Match: {result1['llm_match']}")
    print(f"  LLM Reasoning: {result1['llm_reasoning']}")
    print(f"  Filled Features: {result1['filled_features']}")
    
    assert 0.0 <= result1['llm_score'] <= 1.0
    assert isinstance(result1['llm_match'], bool)
    assert isinstance(result1['llm_reasoning'], str)
    assert isinstance(result1['filled_features'], dict)
    assert 'discipline' in result1['filled_features']
    assert 'assets' in result1['filled_features']
    assert 'actions' in result1['filled_features']
    assert 'materials' in result1['filled_features']
    
    # Test 4.2: Different items (should not match)
    scope_text2 = "Construct reinforced concrete culvert"
    activity_text2 = "Install electrical cables and conduits"
    
    scope_features2 = {
        "discipline": "drainage",
        "assets": ["culvert"],
        "actions": ["construct"],
        "materials": ["rc"],
        "chainages": [],
        "drawings": [],
        "activity_codes": []
    }
    
    activity_features2 = {
        "discipline": "m&e",
        "assets": ["cable"],
        "actions": ["install"],
        "materials": ["copper"],
        "chainages": [],
        "drawings": [],
        "activity_codes": []
    }
    
    result2 = validator.evaluate(scope_text2, activity_text2, scope_features2, activity_features2)
    
    print(f"\nTest 4.2 - Different items:")
    print(f"  Scope: '{scope_text2}'")
    print(f"  Activity: '{activity_text2}'")
    print(f"  LLM Score: {result2['llm_score']}")
    print(f"  LLM Match: {result2['llm_match']}")
    print(f"  LLM Reasoning: {result2['llm_reasoning']}")
    
    assert 0.0 <= result2['llm_score'] <= 1.0
    # Different items should have lower score than similar items
    if result1['llm_score'] > 0.0 and result2['llm_score'] > 0.0:
        assert result2['llm_score'] < result1['llm_score']


def test_error_handling():
    """Test error handling."""
    print("\n" + "="*70)
    print("TEST 5: Error Handling")
    print("="*70)
    
    validator = LLMEngineeringValidator()
    
    # Test 5.1: Empty inputs
    result1 = validator.evaluate("", "", {}, {})
    print(f"\nTest 5.1 - Empty inputs:")
    print(f"  Result type: {type(result1)}")
    print(f"  Keys: {list(result1.keys())}")
    assert isinstance(result1, dict)
    assert 'llm_score' in result1
    assert 'llm_match' in result1
    assert 'llm_reasoning' in result1
    assert 'filled_features' in result1
    
    # Test 5.2: None values never returned
    result2 = validator.evaluate("test", "test", {}, {})
    print(f"\nTest 5.2 - No None values:")
    print(f"  LLM Score is None: {result2['llm_score'] is None}")
    print(f"  LLM Match is None: {result2['llm_match'] is None}")
    print(f"  LLM Reasoning is None: {result2['llm_reasoning'] is None}")
    assert result2['llm_score'] is not None
    assert result2['llm_match'] is not None
    assert result2['llm_reasoning'] is not None
    assert result2['filled_features'] is not None


if __name__ == "__main__":
    print("\n" + "="*70)
    print("LLM ENGINEERING VALIDATOR TEST SUITE")
    print("="*70)
    
    try:
        test_llm_validator_initialization()
        test_prompt_building()
        test_evaluate_disabled()
        test_evaluate_enabled()
        test_error_handling()
        
        print("\n" + "="*70)
        print("✓ ALL TESTS PASSED")
        print("="*70)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

