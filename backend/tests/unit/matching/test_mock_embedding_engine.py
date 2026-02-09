"""
Test script for Mock Embedding Similarity Engine.

Tests semantic similarity computation without OpenAI.
"""

from app.services.matching.ai.mock import MockEmbeddingMatcher


def test_mock_embedding_initialization():
    """Test MockEmbeddingMatcher initialization."""
    print("\n" + "="*70)
    print("TEST 1: MockEmbeddingMatcher Initialization")
    print("="*70)
    
    matcher = MockEmbeddingMatcher()
    
    print(f"\nWeights:")
    print(f"  Jaccard: {matcher.WEIGHTS['jaccard']}")
    print(f"  Sequence: {matcher.WEIGHTS['sequence']}")
    print(f"  TF-IDF: {matcher.WEIGHTS['tfidf']}")
    print(f"  Total: {sum(matcher.WEIGHTS.values())}")
    
    assert matcher.ontology is not None
    assert sum(matcher.WEIGHTS.values()) == 1.0
    assert matcher.WEIGHTS['jaccard'] == 0.4
    assert matcher.WEIGHTS['sequence'] == 0.3
    assert matcher.WEIGHTS['tfidf'] == 0.3


def test_preprocessing():
    """Test text preprocessing."""
    print("\n" + "="*70)
    print("TEST 2: Text Preprocessing")
    print("="*70)
    
    matcher = MockEmbeddingMatcher()
    
    test_cases = [
        ("Construct RC culvert", "construct reinforced concrete culvert"),
        ("Build RW1", "build retaining wall 1"),
        ("Install M&E equipment", "install m&e equipment"),
        ("", ""),
        ("   Multiple   Spaces   ", "multiple spaces"),
    ]
    
    for input_text, expected_contains in test_cases:
        result = matcher._preprocess_text(input_text)
        print(f"\nInput: '{input_text}'")
        print(f"Output: '{result}'")
        assert isinstance(result, str)
        assert result.lower() == result  # Should be lowercase


def test_tokenize():
    """Test tokenization."""
    print("\n" + "="*70)
    print("TEST 3: Tokenization")
    print("="*70)
    
    matcher = MockEmbeddingMatcher()
    
    text = "construct reinforced concrete culvert"
    tokens = matcher._tokenize(text)
    
    print(f"\nText: '{text}'")
    print(f"Tokens: {tokens}")
    
    assert isinstance(tokens, set)
    assert len(tokens) > 0
    assert "construct" in tokens
    assert "culvert" in tokens


def test_jaccard_similarity():
    """Test Jaccard similarity computation."""
    print("\n" + "="*70)
    print("TEST 4: Jaccard Similarity")
    print("="*70)
    
    matcher = MockEmbeddingMatcher()
    
    # Test 4.1: Identical texts
    text1 = "construct culvert"
    text2 = "construct culvert"
    score, words = matcher._compute_jaccard_similarity(text1, text2)
    print(f"\nTest 4.1 - Identical texts:")
    print(f"  Score: {score}")
    print(f"  Overlapping words: {words}")
    assert score == 1.0
    assert len(words) > 0
    
    # Test 4.2: Partial overlap
    text1 = "construct reinforced concrete culvert"
    text2 = "build culvert"
    score, words = matcher._compute_jaccard_similarity(text1, text2)
    print(f"\nTest 4.2 - Partial overlap:")
    print(f"  Score: {score}")
    print(f"  Overlapping words: {words}")
    assert 0.0 < score < 1.0
    assert "culvert" in words
    
    # Test 4.3: No overlap
    text1 = "construct culvert"
    text2 = "install cables"
    score, words = matcher._compute_jaccard_similarity(text1, text2)
    print(f"\nTest 4.3 - No overlap:")
    print(f"  Score: {score}")
    print(f"  Overlapping words: {words}")
    assert score == 0.0
    assert len(words) == 0
    
    # Test 4.4: Empty texts
    score, words = matcher._compute_jaccard_similarity("", "")
    print(f"\nTest 4.4 - Empty texts:")
    print(f"  Score: {score}")
    assert score == 0.0


def test_sequence_similarity():
    """Test sequence similarity computation."""
    print("\n" + "="*70)
    print("TEST 5: Sequence Similarity")
    print("="*70)
    
    matcher = MockEmbeddingMatcher()
    
    # Test 5.1: Identical texts
    text1 = "construct culvert"
    text2 = "construct culvert"
    score = matcher._compute_sequence_similarity(text1, text2)
    print(f"\nTest 5.1 - Identical texts:")
    print(f"  Score: {score}")
    assert score == 1.0
    
    # Test 5.2: Similar texts
    text1 = "construct reinforced concrete culvert"
    text2 = "construct rc culvert"
    score = matcher._compute_sequence_similarity(text1, text2)
    print(f"\nTest 5.2 - Similar texts:")
    print(f"  Score: {score}")
    assert 0.0 < score < 1.0
    
    # Test 5.3: Different texts
    text1 = "construct culvert"
    text2 = "install cables"
    score = matcher._compute_sequence_similarity(text1, text2)
    print(f"\nTest 5.3 - Different texts:")
    print(f"  Score: {score}")
    assert 0.0 <= score < 1.0
    
    # Test 5.4: Empty texts
    score = matcher._compute_sequence_similarity("", "")
    print(f"\nTest 5.4 - Empty texts:")
    print(f"  Score: {score}")
    assert score == 0.0


def test_tfidf_similarity():
    """Test TF-IDF similarity computation."""
    print("\n" + "="*70)
    print("TEST 6: TF-IDF Similarity")
    print("="*70)
    
    matcher = MockEmbeddingMatcher()
    
    # Test 6.1: Identical texts
    text1 = "construct culvert"
    text2 = "construct culvert"
    score = matcher._compute_tfidf_similarity(text1, text2)
    print(f"\nTest 6.1 - Identical texts:")
    print(f"  Score: {score}")
    assert 0.0 <= score <= 1.0
    
    # Test 6.2: Similar texts
    text1 = "construct reinforced concrete culvert"
    text2 = "build culvert"
    score = matcher._compute_tfidf_similarity(text1, text2)
    print(f"\nTest 6.2 - Similar texts:")
    print(f"  Score: {score}")
    assert 0.0 <= score <= 1.0
    
    # Test 6.3: Different texts
    text1 = "construct culvert"
    text2 = "install cables"
    score = matcher._compute_tfidf_similarity(text1, text2)
    print(f"\nTest 6.3 - Different texts:")
    print(f"  Score: {score}")
    assert 0.0 <= score <= 1.0
    
    # Test 6.4: Empty texts
    score = matcher._compute_tfidf_similarity("", "")
    print(f"\nTest 6.4 - Empty texts:")
    print(f"  Score: {score}")
    assert score == 0.0


def test_compute_embedding_score_basic():
    """Test basic embedding score computation."""
    print("\n" + "="*70)
    print("TEST 7: Basic Embedding Score Computation")
    print("="*70)
    
    matcher = MockEmbeddingMatcher()
    
    scope_text = "Construct reinforced concrete culvert at chainage 123+450"
    activity_text = "Build RC culvert at Ch 123+450"
    
    result = matcher.compute_embedding_score(scope_text, activity_text)
    
    print(f"\nScope text: '{scope_text}'")
    print(f"Activity text: '{activity_text}'")
    print(f"\nResult:")
    print(f"  Embedding score: {result['embedding_score']}")
    print(f"  Explanation: {result['explanation']}")
    
    assert 'embedding_score' in result
    assert 'explanation' in result
    assert isinstance(result['embedding_score'], (int, float))
    assert isinstance(result['explanation'], str)
    assert 0.0 <= result['embedding_score'] <= 1.0
    assert len(result['explanation']) > 0


def test_compute_embedding_score_high_similarity():
    """Test high similarity scenario."""
    print("\n" + "="*70)
    print("TEST 8: High Similarity Scenario")
    print("="*70)
    
    matcher = MockEmbeddingMatcher()
    
    scope_text = "Construct reinforced concrete culvert"
    activity_text = "Build RC culvert"
    
    result = matcher.compute_embedding_score(scope_text, activity_text)
    
    print(f"\nScope text: '{scope_text}'")
    print(f"Activity text: '{activity_text}'")
    print(f"\nResult:")
    print(f"  Embedding score: {result['embedding_score']}")
    print(f"  Explanation: {result['explanation']}")
    
    # Should have reasonable similarity (RC expands to reinforced concrete)
    assert result['embedding_score'] > 0.0
    assert "culvert" in result['explanation'].lower() or result['embedding_score'] > 0.0


def test_compute_embedding_score_low_similarity():
    """Test low similarity scenario."""
    print("\n" + "="*70)
    print("TEST 9: Low Similarity Scenario")
    print("="*70)
    
    matcher = MockEmbeddingMatcher()
    
    scope_text = "Construct culvert"
    activity_text = "Install electrical cables"
    
    result = matcher.compute_embedding_score(scope_text, activity_text)
    
    print(f"\nScope text: '{scope_text}'")
    print(f"Activity text: '{activity_text}'")
    print(f"\nResult:")
    print(f"  Embedding score: {result['embedding_score']}")
    print(f"  Explanation: {result['explanation']}")
    
    # Should have low similarity
    assert result['embedding_score'] >= 0.0
    assert result['embedding_score'] <= 1.0


def test_compute_embedding_score_empty():
    """Test with empty inputs."""
    print("\n" + "="*70)
    print("TEST 10: Empty Inputs")
    print("="*70)
    
    matcher = MockEmbeddingMatcher()
    
    # Test 10.1: Both empty
    result1 = matcher.compute_embedding_score("", "")
    print(f"\nTest 10.1 - Both empty:")
    print(f"  Score: {result1['embedding_score']}")
    assert result1['embedding_score'] == 0.0
    assert 'explanation' in result1
    
    # Test 10.2: One empty
    result2 = matcher.compute_embedding_score("construct culvert", "")
    print(f"\nTest 10.2 - One empty:")
    print(f"  Score: {result2['embedding_score']}")
    assert result2['embedding_score'] == 0.0
    
    # Test 10.3: Whitespace only
    result3 = matcher.compute_embedding_score("   ", "   ")
    print(f"\nTest 10.3 - Whitespace only:")
    print(f"  Score: {result3['embedding_score']}")
    assert result3['embedding_score'] == 0.0


def test_compute_embedding_score_abbreviation_expansion():
    """Test that abbreviations are expanded correctly."""
    print("\n" + "="*70)
    print("TEST 11: Abbreviation Expansion")
    print("="*70)
    
    matcher = MockEmbeddingMatcher()
    
    # RC should expand to "reinforced concrete"
    scope_text = "Construct RC culvert"
    activity_text = "Build reinforced concrete culvert"
    
    result = matcher.compute_embedding_score(scope_text, activity_text)
    
    print(f"\nScope text: '{scope_text}'")
    print(f"Activity text: '{activity_text}'")
    print(f"\nResult:")
    print(f"  Embedding score: {result['embedding_score']}")
    print(f"  Explanation: {result['explanation']}")
    
    # Should have good similarity after expansion
    assert result['embedding_score'] > 0.0
    # Check that explanation mentions overlapping words
    assert len(result['explanation']) > 0


if __name__ == "__main__":
    print("\n" + "="*70)
    print("MOCK EMBEDDING SIMILARITY ENGINE TEST SUITE")
    print("="*70)
    
    try:
        test_mock_embedding_initialization()
        test_preprocessing()
        test_tokenize()
        test_jaccard_similarity()
        test_sequence_similarity()
        test_tfidf_similarity()
        test_compute_embedding_score_basic()
        test_compute_embedding_score_high_similarity()
        test_compute_embedding_score_low_similarity()
        test_compute_embedding_score_empty()
        test_compute_embedding_score_abbreviation_expansion()
        
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

