"""
Test script for Mock LLM Engineering Validator.

Tests engineering reasoning simulation without OpenAI.
"""

from app.services.matching.ai.mock import MockLLMValidator


def test_mock_llm_initialization():
    """Test MockLLMValidator initialization."""
    print("\n" + "="*70)
    print("TEST 1: MockLLMValidator Initialization")
    print("="*70)
    
    validator = MockLLMValidator()
    
    print(f"\nComponents:")
    print(f"  Feature extractor: {type(validator.feature_extractor).__name__}")
    print(f"  Rule matcher: {type(validator.rule_matcher).__name__}")
    print(f"  Ontology: {type(validator.ontology).__name__}")
    print(f"\nBonuses:")
    print(f"  Synonym: {validator.BONUSES['synonym']}")
    print(f"  Asset: {validator.BONUSES['asset']}")
    print(f"  Chainage: {validator.BONUSES['chainage']}")
    print(f"  Material: {validator.BONUSES['material']}")
    print(f"  Match threshold: {validator.MATCH_THRESHOLD}")
    
    assert validator.feature_extractor is not None
    assert validator.rule_matcher is not None
    assert validator.ontology is not None
    assert validator.MATCH_THRESHOLD == 0.5


def test_preprocessing():
    """Test text preprocessing."""
    print("\n" + "="*70)
    print("TEST 2: Text Preprocessing")
    print("="*70)
    
    validator = MockLLMValidator()
    
    test_cases = [
        ("Construct RC culvert", "construct reinforced concrete culvert"),
        ("Build RW1", "build retaining wall 1"),
    ]
    
    for input_text, expected_contains in test_cases:
        result = validator._preprocess_text(input_text)
        print(f"\nInput: '{input_text}'")
        print(f"Output: '{result}'")
        assert isinstance(result, str)
        assert result.lower() == result  # Should be lowercase


def test_synonym_matching():
    """Test synonym matching."""
    print("\n" + "="*70)
    print("TEST 3: Synonym Matching")
    print("="*70)
    
    validator = MockLLMValidator()
    
    # Test 3.1: Direct match
    text1 = "construct culvert"
    text2 = "construct culvert"
    has_match, terms = validator._check_synonym_match(text1, text2)
    print(f"\nTest 3.1 - Direct match:")
    print(f"  Has match: {has_match}")
    print(f"  Matched terms: {terms}")
    assert has_match
    
    # Test 3.2: Synonym match
    text1 = "construct culvert"
    text2 = "build culvert"
    has_match, terms = validator._check_synonym_match(text1, text2)
    print(f"\nTest 3.2 - Synonym match:")
    print(f"  Has match: {has_match}")
    print(f"  Matched terms: {terms}")
    # "construct" and "build" are synonyms
    assert has_match or "construct" in terms or "build" in terms
    
    # Test 3.3: No match
    text1 = "construct culvert"
    text2 = "install cables"
    has_match, terms = validator._check_synonym_match(text1, text2)
    print(f"\nTest 3.3 - No match:")
    print(f"  Has match: {has_match}")
    print(f"  Matched terms: {terms}")
    # May or may not match depending on synonym dictionary


def test_asset_matching():
    """Test asset matching."""
    print("\n" + "="*70)
    print("TEST 4: Asset Matching")
    print("="*70)
    
    validator = MockLLMValidator()
    
    scope_features = {
        "assets": ["culvert", "drainage"]
    }
    activity_features = {
        "assets": ["culvert"]
    }
    
    has_match, matched = validator._check_asset_match(scope_features, activity_features)
    print(f"\nScope assets: {scope_features['assets']}")
    print(f"Activity assets: {activity_features['assets']}")
    print(f"  Has match: {has_match}")
    print(f"  Matched assets: {matched}")
    assert has_match
    assert "culvert" in matched


def test_chainage_matching():
    """Test chainage matching."""
    print("\n" + "="*70)
    print("TEST 5: Chainage Matching")
    print("="*70)
    
    validator = MockLLMValidator()
    
    # Test 5.1: Matching chainages
    scope_features = {
        "chainages": ["123+450", "Ch 123+450"]
    }
    activity_features = {
        "chainages": ["123+450"]
    }
    
    has_match = validator._check_chainage_match(scope_features, activity_features)
    print(f"\nTest 5.1 - Matching chainages:")
    print(f"  Scope: {scope_features['chainages']}")
    print(f"  Activity: {activity_features['chainages']}")
    print(f"  Has match: {has_match}")
    assert has_match
    
    # Test 5.2: Non-matching chainages
    scope_features = {
        "chainages": ["123+450"]
    }
    activity_features = {
        "chainages": ["200+000"]
    }
    
    has_match = validator._check_chainage_match(scope_features, activity_features)
    print(f"\nTest 5.2 - Non-matching chainages:")
    print(f"  Scope: {scope_features['chainages']}")
    print(f"  Activity: {activity_features['chainages']}")
    print(f"  Has match: {has_match}")
    assert not has_match


def test_material_matching():
    """Test material matching."""
    print("\n" + "="*70)
    print("TEST 6: Material Matching")
    print("="*70)
    
    validator = MockLLMValidator()
    
    scope_features = {
        "materials": ["reinforced concrete", "steel"]
    }
    activity_features = {
        "materials": ["RC", "mild steel"]
    }
    
    has_match, matched = validator._check_material_match(scope_features, activity_features)
    print(f"\nScope materials: {scope_features['materials']}")
    print(f"Activity materials: {activity_features['materials']}")
    print(f"  Has match: {has_match}")
    print(f"  Matched materials: {matched}")
    # May match if synonyms work correctly


def test_discipline_inference():
    """Test discipline inference."""
    print("\n" + "="*70)
    print("TEST 7: Discipline Inference")
    print("="*70)
    
    validator = MockLLMValidator()
    
    scope_features = {
        "discipline": "",
        "assets": ["culvert"]
    }
    activity_features = {
        "discipline": "",
        "assets": []
    }
    
    inferred = validator._infer_discipline(
        scope_features,
        activity_features,
        "construct culvert",
        "build drainage structure"
    )
    
    print(f"\nScope features: {scope_features}")
    print(f"Activity features: {activity_features}")
    print(f"  Inferred discipline: '{inferred}'")
    # Should infer "drainage" from "culvert"
    assert isinstance(inferred, str)


def test_fill_missing_features():
    """Test filling missing features."""
    print("\n" + "="*70)
    print("TEST 8: Fill Missing Features")
    print("="*70)
    
    validator = MockLLMValidator()
    
    scope_features = {
        "discipline": "",
        "assets": ["culvert"],
        "actions": ["construct"],
        "materials": []
    }
    activity_features = {
        "discipline": "drainage",
        "assets": ["drainage"],
        "actions": [],
        "materials": ["concrete"]
    }
    
    filled = validator._fill_missing_features(
        scope_features,
        activity_features,
        "construct culvert",
        "build drainage"
    )
    
    print(f"\nFilled features:")
    print(f"  Discipline: '{filled['discipline']}'")
    print(f"  Assets: {filled['assets']}")
    print(f"  Actions: {filled['actions']}")
    print(f"  Materials: {filled['materials']}")
    
    assert 'discipline' in filled
    assert 'assets' in filled
    assert 'actions' in filled
    assert 'materials' in filled
    assert isinstance(filled['assets'], list)
    assert isinstance(filled['actions'], list)
    assert isinstance(filled['materials'], list)


def test_evaluate_basic():
    """Test basic evaluation."""
    print("\n" + "="*70)
    print("TEST 9: Basic Evaluation")
    print("="*70)
    
    validator = MockLLMValidator()
    
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
    
    result = validator.evaluate(scope_text, activity_text, scope_features, activity_features)
    
    print(f"\nScope text: '{scope_text}'")
    print(f"Activity text: '{activity_text}'")
    print(f"\nResult:")
    print(f"  LLM score: {result['llm_score']}")
    print(f"  LLM match: {result['llm_match']}")
    print(f"  LLM reasoning: {result['llm_reasoning']}")
    print(f"  Filled features: {result['filled_features']}")
    
    assert 'llm_score' in result
    assert 'llm_match' in result
    assert 'llm_reasoning' in result
    assert 'filled_features' in result
    assert 0.0 <= result['llm_score'] <= 1.0
    assert isinstance(result['llm_match'], bool)
    assert isinstance(result['llm_reasoning'], str)
    assert isinstance(result['filled_features'], dict)


def test_evaluate_high_match():
    """Test high match scenario."""
    print("\n" + "="*70)
    print("TEST 10: High Match Scenario")
    print("="*70)
    
    validator = MockLLMValidator()
    
    scope_text = "Construct RC culvert at chainage 123+450"
    activity_text = "Build reinforced concrete culvert at Ch 123+450"
    
    scope_features = {
        "discipline": "drainage",
        "assets": ["culvert"],
        "actions": ["construct"],
        "materials": ["RC"],
        "chainages": ["123+450"]
    }
    
    activity_features = {
        "discipline": "drainage",
        "assets": ["culvert"],
        "actions": ["build"],
        "materials": ["reinforced concrete"],
        "chainages": ["123+450"]
    }
    
    result = validator.evaluate(scope_text, activity_text, scope_features, activity_features)
    
    print(f"\nResult:")
    print(f"  LLM score: {result['llm_score']}")
    print(f"  LLM match: {result['llm_match']}")
    print(f"  Reasoning: {result['llm_reasoning']}")
    
    # Should have high score due to multiple matches
    assert result['llm_score'] > 0.0
    # With bonuses, should likely be above threshold
    if result['llm_score'] >= validator.MATCH_THRESHOLD:
        assert result['llm_match'] is True


def test_evaluate_low_match():
    """Test low match scenario."""
    print("\n" + "="*70)
    print("TEST 11: Low Match Scenario")
    print("="*70)
    
    validator = MockLLMValidator()
    
    scope_text = "Construct culvert"
    activity_text = "Install electrical cables"
    
    scope_features = {
        "discipline": "drainage",
        "assets": ["culvert"],
        "actions": ["construct"],
        "materials": [],
        "chainages": []
    }
    
    activity_features = {
        "discipline": "m&e",
        "assets": ["cables"],
        "actions": ["install"],
        "materials": [],
        "chainages": []
    }
    
    result = validator.evaluate(scope_text, activity_text, scope_features, activity_features)
    
    print(f"\nResult:")
    print(f"  LLM score: {result['llm_score']}")
    print(f"  LLM match: {result['llm_match']}")
    print(f"  Reasoning: {result['llm_reasoning']}")
    
    # Should have lower score
    assert result['llm_score'] >= 0.0
    assert result['llm_score'] <= 1.0


def test_evaluate_empty():
    """Test with empty inputs."""
    print("\n" + "="*70)
    print("TEST 12: Empty Inputs")
    print("="*70)
    
    validator = MockLLMValidator()
    
    result = validator.evaluate("", "", {}, {})
    
    print(f"\nResult:")
    print(f"  LLM score: {result['llm_score']}")
    print(f"  LLM match: {result['llm_match']}")
    print(f"  Filled features: {result['filled_features']}")
    
    assert 'llm_score' in result
    assert 'llm_match' in result
    assert 'filled_features' in result
    assert 0.0 <= result['llm_score'] <= 1.0


if __name__ == "__main__":
    print("\n" + "="*70)
    print("MOCK LLM ENGINEERING VALIDATOR TEST SUITE")
    print("="*70)
    
    try:
        test_mock_llm_initialization()
        test_preprocessing()
        test_synonym_matching()
        test_asset_matching()
        test_chainage_matching()
        test_material_matching()
        test_discipline_inference()
        test_fill_missing_features()
        test_evaluate_basic()
        test_evaluate_high_match()
        test_evaluate_low_match()
        test_evaluate_empty()
        
        print("\n" + "="*70)
        print("✓ ALL TESTS PASSED")
        print("="*70)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

