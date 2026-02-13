"""
Test script for Rule-Based Matching Engine.

Tests deterministic matching logic for scope and activity features.
"""

from app.services.matching.engines.rule_engine import RuleBasedMatcher


def test_discipline_matching():
    """Test discipline matching."""
    print("\n" + "="*70)
    print("TEST 1: Discipline Matching")
    print("="*70)
    
    # Test 1.1: Exact match
    result = RuleBasedMatcher.match_discipline("structures", "structures")
    print(f"\nTest 1.1 - Exact match:")
    print(f"  Input: 'structures' vs 'structures'")
    print(f"  Score: {result['score']}, Match: {result['match']}")
    print(f"  Explanation: {result['explanation']}")
    assert result['score'] == 1.0 and result['match'] == True
    
    # Test 1.2: Mismatch
    result = RuleBasedMatcher.match_discipline("structures", "drainage")
    print(f"\nTest 1.2 - Mismatch:")
    print(f"  Input: 'structures' vs 'drainage'")
    print(f"  Score: {result['score']}, Match: {result['match']}")
    print(f"  Explanation: {result['explanation']}")
    assert result['score'] == 0.0 and result['match'] == False
    
    # Test 1.3: Both empty
    result = RuleBasedMatcher.match_discipline("", "")
    print(f"\nTest 1.3 - Both empty:")
    print(f"  Input: '' vs ''")
    print(f"  Score: {result['score']}, Match: {result['match']}")
    assert result['score'] == 0.0 and result['match'] == False


def test_assets_matching():
    """Test assets matching."""
    print("\n" + "="*70)
    print("TEST 2: Assets Matching")
    print("="*70)
    
    # Test 2.1: Exact match
    result = RuleBasedMatcher.match_assets(["culvert"], ["culvert"])
    print(f"\nTest 2.1 - Exact match:")
    print(f"  Input: ['culvert'] vs ['culvert']")
    print(f"  Score: {result['score']}, Match: {result['match']}")
    print(f"  Explanation: {result['explanation']}")
    assert result['score'] == 1.0 and result['match'] == True
    
    # Test 2.2: Partial match
    result = RuleBasedMatcher.match_assets(["pavement"], ["kerb", "pavement"])
    print(f"\nTest 2.2 - Partial match:")
    print(f"  Input: ['pavement'] vs ['kerb', 'pavement']")
    print(f"  Score: {result['score']}, Match: {result['match']}")
    print(f"  Explanation: {result['explanation']}")
    assert result['score'] == 0.7 and result['match'] == True
    
    # Test 2.3: No match
    result = RuleBasedMatcher.match_assets(["bridge"], ["culvert"])
    print(f"\nTest 2.3 - No match:")
    print(f"  Input: ['bridge'] vs ['culvert']")
    print(f"  Score: {result['score']}, Match: {result['match']}")
    print(f"  Explanation: {result['explanation']}")
    assert result['score'] == 0.0 and result['match'] == False


def test_chainage_matching():
    """Test chainage matching."""
    print("\n" + "="*70)
    print("TEST 3: Chainage Matching")
    print("="*70)
    
    # Test 3.1: Exact match
    result = RuleBasedMatcher.match_chainage(["Ch 123+450"], ["Ch 123+450"])
    print(f"\nTest 3.1 - Exact match:")
    print(f"  Input: ['Ch 123+450'] vs ['Ch 123+450']")
    print(f"  Score: {result['score']}, Match: {result['match']}")
    print(f"  Explanation: {result['explanation']}")
    assert result['score'] == 1.0 and result['match'] == True
    
    # Test 3.2: Same km section
    result = RuleBasedMatcher.match_chainage(["Ch 123+450"], ["Ch 123+500"])
    print(f"\nTest 3.2 - Same km section:")
    print(f"  Input: ['Ch 123+450'] vs ['Ch 123+500']")
    print(f"  Score: {result['score']}, Match: {result['match']}")
    print(f"  Explanation: {result['explanation']}")
    assert result['score'] == 0.7 and result['match'] == True
    
    # Test 3.3: Close proximity (< 100m)
    result = RuleBasedMatcher.match_chainage(["Ch 123+450"], ["Ch 123+520"])
    print(f"\nTest 3.3 - Close proximity (< 100m):")
    print(f"  Input: ['Ch 123+450'] vs ['Ch 123+520']")
    print(f"  Score: {result['score']}, Match: {result['match']}")
    print(f"  Explanation: {result['explanation']}")
    # Note: This will be 0.7 (same km) not 0.4, as same km takes priority
    
    # Test 3.4: Different formats
    result = RuleBasedMatcher.match_chainage(["CH.123+100"], ["Ch123+100"])
    print(f"\nTest 3.4 - Different formats:")
    print(f"  Input: ['CH.123+100'] vs ['Ch123+100']")
    print(f"  Score: {result['score']}, Match: {result['match']}")
    print(f"  Explanation: {result['explanation']}")
    assert result['score'] == 1.0 and result['match'] == True


def test_actions_matching():
    """Test actions matching."""
    print("\n" + "="*70)
    print("TEST 4: Actions Matching")
    print("="*70)
    
    # Test 4.1: Exact match
    result = RuleBasedMatcher.match_actions(["install"], ["install"])
    print(f"\nTest 4.1 - Exact match:")
    print(f"  Input: ['install'] vs ['install']")
    print(f"  Score: {result['score']}, Match: {result['match']}")
    print(f"  Explanation: {result['explanation']}")
    assert result['score'] == 1.0 and result['match'] == True
    
    # Test 4.2: Overlapping verbs
    result = RuleBasedMatcher.match_actions(["install"], ["placement"])
    print(f"\nTest 4.2 - Overlapping verbs:")
    print(f"  Input: ['install'] vs ['placement']")
    print(f"  Score: {result['score']}, Match: {result['match']}")
    print(f"  Explanation: {result['explanation']}")
    assert result['score'] == 0.6 and result['match'] == True


def test_compute_rule_score():
    """Test overall rule score computation."""
    print("\n" + "="*70)
    print("TEST 5: Overall Rule Score Computation")
    print("="*70)
    
    # Test 5.1: Strong match
    scope_features = {
        "discipline": "structures",
        "assets": ["culvert"],
        "actions": ["construct"],
        "materials": ["rc"],
        "chainages": ["Ch 123+450"],
        "drawings": ["DRG-102"],
        "activity_codes": ["STR-001"]
    }
    
    activity_features = {
        "discipline": "structures",
        "assets": ["culvert"],
        "actions": ["construct"],
        "materials": ["rc"],
        "chainages": ["Ch 123+450"],
        "drawings": ["DRG-102"],
        "activity_codes": ["STR-001"]
    }
    
    result = RuleBasedMatcher.compute_rule_score(scope_features, activity_features)
    print(f"\nTest 5.1 - Strong match (all features match):")
    print(f"  Rule Score: {result['rule_score']}")
    print(f"  Matches: {result['matches']}")
    print(f"\n  Explanations:")
    for i, exp in enumerate(result['explanations'], 1):
        print(f"    {i}. {exp}")
    assert result['rule_score'] == 1.0
    
    # Test 5.2: Partial match
    scope_features2 = {
        "discipline": "structures",
        "assets": ["culvert"],
        "actions": ["construct"],
        "materials": [],
        "chainages": ["Ch 123+450"],
        "drawings": [],
        "activity_codes": []
    }
    
    activity_features2 = {
        "discipline": "structures",
        "assets": ["culvert", "bridge"],
        "actions": ["construct"],
        "materials": ["rc"],
        "chainages": ["Ch 123+500"],  # Same km, different meters
        "drawings": ["DRG-102"],
        "activity_codes": []
    }
    
    result2 = RuleBasedMatcher.compute_rule_score(scope_features2, activity_features2)
    print(f"\nTest 5.2 - Partial match:")
    print(f"  Rule Score: {result2['rule_score']}")
    print(f"  Matches: {result2['matches']}")
    print(f"\n  Explanations:")
    for i, exp in enumerate(result2['explanations'], 1):
        print(f"    {i}. {exp}")
    assert 0.0 < result2['rule_score'] < 1.0
    
    # Test 5.3: Weak match
    scope_features3 = {
        "discipline": "structures",
        "assets": ["bridge"],
        "actions": ["construct"],
        "materials": ["rc"],
        "chainages": ["Ch 200+000"],
        "drawings": ["DRG-500"],
        "activity_codes": ["STR-001"]
    }
    
    activity_features3 = {
        "discipline": "drainage",
        "assets": ["culvert"],
        "actions": ["install"],
        "materials": ["hdpe"],
        "chainages": ["Ch 300+000"],
        "drawings": ["DRG-600"],
        "activity_codes": ["DRN-001"]
    }
    
    result3 = RuleBasedMatcher.compute_rule_score(scope_features3, activity_features3)
    print(f"\nTest 5.3 - Weak match (mostly mismatched):")
    print(f"  Rule Score: {result3['rule_score']}")
    print(f"  Matches: {result3['matches']}")
    print(f"\n  Explanations:")
    for i, exp in enumerate(result3['explanations'], 1):
        print(f"    {i}. {exp}")
    assert result3['rule_score'] < 0.3


if __name__ == "__main__":
    print("\n" + "="*70)
    print("RULE-BASED MATCHING ENGINE TEST SUITE")
    print("="*70)
    
    try:
        test_discipline_matching()
        test_assets_matching()
        test_chainage_matching()
        test_actions_matching()
        test_compute_rule_score()
        
        print("\n" + "="*70)
        print("✓ ALL TESTS PASSED")
        print("="*70)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


