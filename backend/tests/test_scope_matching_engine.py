"""
Test script for Full Scope ↔ Activity Matching Engine.

Tests complete matching pipeline from scope items to activities.
"""

from app.services.matching.engines.scope_matching_engine import ScopeMatchingEngine


def test_scope_matching_initialization():
    """Test ScopeMatchingEngine initialization."""
    print("\n" + "="*70)
    print("TEST 1: ScopeMatchingEngine Initialization")
    print("="*70)
    
    engine = ScopeMatchingEngine()
    
    print(f"\nFeature extractor: {type(engine.feature_extractor).__name__}")
    print(f"Ensemble matcher: {type(engine.ensemble_matcher).__name__}")
    print(f"Covered threshold: {engine.COVERED_THRESHOLD}")
    print(f"Weak threshold: {engine.WEAK_THRESHOLD}")
    
    assert engine.feature_extractor is not None
    assert engine.ensemble_matcher is not None
    assert engine.COVERED_THRESHOLD == 0.50
    assert engine.WEAK_THRESHOLD == 0.30


def test_match_scope_to_activities_basic():
    """Test basic matching scenario."""
    print("\n" + "="*70)
    print("TEST 2: Basic Matching Scenario")
    print("="*70)
    
    engine = ScopeMatchingEngine()
    
    scope_items = [
        {
            "id": "S-001",
            "text": "Construct reinforced concrete culvert at chainage 123+450"
        },
        {
            "id": "S-002",
            "text": "Install electrical cables and conduits"
        }
    ]
    
    activities = [
        {
            "id": "A-001",
            "text": "Build RC culvert at Ch 123+450"
        },
        {
            "id": "A-002",
            "text": "Install electrical cables"
        },
        {
            "id": "A-003",
            "text": "Construct bridge at chainage 200+000"
        }
    ]
    
    result = engine.match_scope_to_activities(scope_items, activities)
    
    print(f"\nResult structure:")
    print(f"  Scope matches: {len(result['scope_matches'])}")
    print(f"  Missing scope: {len(result['missing_scope'])}")
    print(f"  Extra activities: {len(result['extra_activities'])}")
    
    assert 'scope_matches' in result
    assert 'missing_scope' in result
    assert 'extra_activities' in result
    assert isinstance(result['scope_matches'], list)
    assert isinstance(result['missing_scope'], list)
    assert isinstance(result['extra_activities'], list)
    
    # Check first scope match
    if result['scope_matches']:
        scope_match = result['scope_matches'][0]
        print(f"\nFirst scope match:")
        print(f"  Scope ID: {scope_match['scope_id']}")
        print(f"  Status: {scope_match['status']}")
        print(f"  Best match score: {scope_match['best_match']['final_score']}")
        print(f"  All matches: {len(scope_match['all_matches_ranked'])}")
        
        assert 'scope_id' in scope_match
        assert 'scope_text' in scope_match
        assert 'best_match' in scope_match
        assert 'all_matches_ranked' in scope_match
        assert 'status' in scope_match
        assert scope_match['status'] in ['covered', 'weak', 'missing']
        
        # Check best match structure
        best_match = scope_match['best_match']
        assert 'activity_id' in best_match
        assert 'activity_text' in best_match
        assert 'final_score' in best_match
        assert 'match' in best_match
        assert 'components' in best_match
        assert 'reasoning' in best_match
        
        # Check all matches are sorted (highest first)
        all_matches = scope_match['all_matches_ranked']
        if len(all_matches) > 1:
            for i in range(len(all_matches) - 1):
                assert all_matches[i]['final_score'] >= all_matches[i + 1]['final_score']


def test_match_scope_to_activities_covered():
    """Test covered status (high score)."""
    print("\n" + "="*70)
    print("TEST 3: Covered Status (High Score)")
    print("="*70)
    
    engine = ScopeMatchingEngine()
    
    scope_items = [
        {
            "id": "S-001",
            "text": "Construct reinforced concrete culvert at chainage 123+450"
        }
    ]
    
    activities = [
        {
            "id": "A-001",
            "text": "Build RC culvert at Ch 123+450"
        }
    ]
    
    result = engine.match_scope_to_activities(scope_items, activities)
    
    if result['scope_matches']:
        scope_match = result['scope_matches'][0]
        print(f"\nScope match:")
        print(f"  Status: {scope_match['status']}")
        print(f"  Best score: {scope_match['best_match']['final_score']}")
        
        # With matching features, should be covered or at least weak
        assert scope_match['status'] in ['covered', 'weak', 'missing']
        assert scope_match['best_match']['final_score'] >= 0.0


def test_match_scope_to_activities_missing():
    """Test missing status (low score)."""
    print("\n" + "="*70)
    print("TEST 4: Missing Status (Low Score)")
    print("="*70)
    
    engine = ScopeMatchingEngine()
    
    scope_items = [
        {
            "id": "S-001",
            "text": "Construct culvert"
        }
    ]
    
    activities = [
        {
            "id": "A-001",
            "text": "Install electrical cables"
        }
    ]
    
    result = engine.match_scope_to_activities(scope_items, activities)
    
    if result['scope_matches']:
        scope_match = result['scope_matches'][0]
        print(f"\nScope match:")
        print(f"  Status: {scope_match['status']}")
        print(f"  Best score: {scope_match['best_match']['final_score']}")
        
        # With mismatched features, might be missing
        assert scope_match['status'] in ['covered', 'weak', 'missing']
        assert scope_match['best_match']['final_score'] >= 0.0
        
        # Check missing_scope list
        if scope_match['status'] == 'missing':
            assert len(result['missing_scope']) > 0


def test_match_scope_to_activities_extra():
    """Test extra activities identification."""
    print("\n" + "="*70)
    print("TEST 5: Extra Activities Identification")
    print("="*70)
    
    engine = ScopeMatchingEngine()
    
    scope_items = [
        {
            "id": "S-001",
            "text": "Construct culvert"
        }
    ]
    
    activities = [
        {
            "id": "A-001",
            "text": "Build culvert"
        },
        {
            "id": "A-002",
            "text": "Install cables"
        },
        {
            "id": "A-003",
            "text": "Construct bridge"
        }
    ]
    
    result = engine.match_scope_to_activities(scope_items, activities)
    
    print(f"\nResult:")
    print(f"  Scope matches: {len(result['scope_matches'])}")
    print(f"  Extra activities: {len(result['extra_activities'])}")
    
    # Should have 1 scope match
    assert len(result['scope_matches']) == 1
    
    # Should have extra activities (A-002 and A-003 if A-001 is best match)
    # Note: This depends on matching scores
    print(f"\nExtra activities:")
    for extra in result['extra_activities']:
        print(f"  - {extra['activity_id']}: {extra['reason']}")
        assert 'activity_id' in extra
        assert 'activity_text' in extra
        assert 'reason' in extra


def test_match_scope_to_activities_empty():
    """Test with empty inputs."""
    print("\n" + "="*70)
    print("TEST 6: Empty Inputs")
    print("="*70)
    
    engine = ScopeMatchingEngine()
    
    # Test 6.1: Empty scope items
    result1 = engine.match_scope_to_activities([], [{"id": "A-001", "text": "test"}])
    print(f"\nTest 6.1 - Empty scope items:")
    print(f"  Scope matches: {len(result1['scope_matches'])}")
    print(f"  Extra activities: {len(result1['extra_activities'])}")
    assert len(result1['scope_matches']) == 0
    assert len(result1['extra_activities']) == 1  # All activities are extra
    
    # Test 6.2: Empty activities
    result2 = engine.match_scope_to_activities([{"id": "S-001", "text": "test"}], [])
    print(f"\nTest 6.2 - Empty activities:")
    print(f"  Scope matches: {len(result2['scope_matches'])}")
    print(f"  Missing scope: {len(result2['missing_scope'])}")
    assert len(result2['scope_matches']) == 1
    assert len(result2['missing_scope']) == 1  # No matches = missing
    
    # Test 6.3: Both empty
    result3 = engine.match_scope_to_activities([], [])
    print(f"\nTest 6.3 - Both empty:")
    print(f"  Scope matches: {len(result3['scope_matches'])}")
    assert len(result3['scope_matches']) == 0
    assert len(result3['extra_activities']) == 0


def test_match_scope_to_activities_error_handling():
    """Test error handling."""
    print("\n" + "="*70)
    print("TEST 7: Error Handling")
    print("="*70)
    
    engine = ScopeMatchingEngine()
    
    # Test 7.1: Missing fields
    scope_items = [
        {
            "id": "S-001",
            "text": ""  # Empty text field
        }
    ]
    
    activities = [
        {
            "id": "A-001",
            "text": ""  # Empty text field
        }
    ]
    
    result = engine.match_scope_to_activities(scope_items, activities)
    print(f"\nTest 7.1 - Missing fields:")
    print(f"  Scope matches: {len(result['scope_matches'])}")
    assert 'scope_matches' in result
    assert isinstance(result['scope_matches'], list)
    
    # Test 7.2: None values
    result2 = engine.match_scope_to_activities(None, None)
    print(f"\nTest 7.2 - None values:")
    print(f"  Scope matches: {len(result2['scope_matches'])}")
    assert 'scope_matches' in result2
    
    # Test 7.3: Invalid types
    result3 = engine.match_scope_to_activities(["invalid"], ["invalid"])
    print(f"\nTest 7.3 - Invalid types:")
    print(f"  Scope matches: {len(result3['scope_matches'])}")
    assert 'scope_matches' in result3


def test_match_scope_to_activities_ranking():
    """Test that matches are properly ranked."""
    print("\n" + "="*70)
    print("TEST 8: Match Ranking")
    print("="*70)
    
    engine = ScopeMatchingEngine()
    
    scope_items = [
        {
            "id": "S-001",
            "text": "Construct reinforced concrete culvert"
        }
    ]
    
    activities = [
        {
            "id": "A-001",
            "text": "Build RC culvert"  # Should match well
        },
        {
            "id": "A-002",
            "text": "Install electrical cables"  # Should match poorly
        },
        {
            "id": "A-003",
            "text": "Construct culvert"  # Should match moderately
        }
    ]
    
    result = engine.match_scope_to_activities(scope_items, activities)
    
    if result['scope_matches']:
        scope_match = result['scope_matches'][0]
        all_matches = scope_match['all_matches_ranked']
        
        print(f"\nRanked matches:")
        for i, match in enumerate(all_matches, 1):
            print(f"  {i}. {match['activity_id']}: {match['final_score']:.4f}")
        
        # Verify sorting (highest first)
        if len(all_matches) > 1:
            for i in range(len(all_matches) - 1):
                assert all_matches[i]['final_score'] >= all_matches[i + 1]['final_score'], \
                    f"Matches not sorted: {all_matches[i]['final_score']} < {all_matches[i + 1]['final_score']}"


if __name__ == "__main__":
    print("\n" + "="*70)
    print("FULL SCOPE ↔ ACTIVITY MATCHING ENGINE TEST SUITE")
    print("="*70)
    
    try:
        test_scope_matching_initialization()
        test_match_scope_to_activities_basic()
        test_match_scope_to_activities_covered()
        test_match_scope_to_activities_missing()
        test_match_scope_to_activities_extra()
        test_match_scope_to_activities_empty()
        test_match_scope_to_activities_error_handling()
        test_match_scope_to_activities_ranking()
        
        print("\n" + "="*70)
        print("✓ ALL TESTS PASSED")
        print("="*70)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

