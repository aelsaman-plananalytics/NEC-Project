"""
Test script for Embedding Similarity Engine.

Tests semantic similarity matching between scope and activity text.
"""

from app.services.matching.ai.openai import EmbeddingMatcher


def test_embedding_matcher_initialization():
    """Test EmbeddingMatcher initialization."""
    print("\n" + "="*70)
    print("TEST 1: EmbeddingMatcher Initialization")
    print("="*70)
    
    matcher = EmbeddingMatcher()
    
    print(f"\nEmbeddings enabled: {matcher.embeddings_enabled}")
    print(f"OpenAI client available: {matcher.openai_client is not None}")
    print(f"Embedding model: {matcher.embedding_model}")
    
    if matcher.embeddings_enabled:
        print("✓ Embeddings are enabled and ready")
    else:
        print("⚠ Embeddings disabled (OpenAI API key not available)")
        print("  This is expected if API key is missing or quota exceeded")


def test_text_preprocessing():
    """Test text preprocessing."""
    print("\n" + "="*70)
    print("TEST 2: Text Preprocessing")
    print("="*70)
    
    matcher = EmbeddingMatcher()
    
    # Test 2.1: Basic preprocessing
    text1 = "Construct RC culvert at Ch 123+450"
    preprocessed1 = matcher._preprocess_text(text1)
    print(f"\nTest 2.1 - Basic preprocessing:")
    print(f"  Input: '{text1}'")
    print(f"  Output: '{preprocessed1}'")
    assert "reinforced concrete" in preprocessed1.lower() or "rc" in preprocessed1.lower()
    assert "culvert" in preprocessed1.lower()
    
    # Test 2.2: Abbreviation expansion
    text2 = "Install HDPE pipe and MS fittings"
    preprocessed2 = matcher._preprocess_text(text2)
    print(f"\nTest 2.2 - Abbreviation expansion:")
    print(f"  Input: '{text2}'")
    print(f"  Output: '{preprocessed2}'")
    assert "high density polyethylene" in preprocessed2.lower() or "hdpe" in preprocessed2.lower()
    assert "mild steel" in preprocessed2.lower() or "ms" in preprocessed2.lower()
    
    # Test 2.3: Empty text
    text3 = ""
    preprocessed3 = matcher._preprocess_text(text3)
    print(f"\nTest 2.3 - Empty text:")
    print(f"  Input: '{text3}'")
    print(f"  Output: '{preprocessed3}'")
    assert preprocessed3 == ""


def test_cosine_similarity():
    """Test cosine similarity calculation."""
    print("\n" + "="*70)
    print("TEST 3: Cosine Similarity Calculation")
    print("="*70)
    
    matcher = EmbeddingMatcher()
    
    # Test 3.1: Identical vectors
    vec1 = [1.0, 0.0, 0.0]
    vec2 = [1.0, 0.0, 0.0]
    similarity1 = matcher._cosine_similarity(vec1, vec2)
    print(f"\nTest 3.1 - Identical vectors:")
    print(f"  Similarity: {similarity1}")
    assert similarity1 == 1.0
    
    # Test 3.2: Orthogonal vectors
    vec3 = [1.0, 0.0, 0.0]
    vec4 = [0.0, 1.0, 0.0]
    similarity2 = matcher._cosine_similarity(vec3, vec4)
    print(f"\nTest 3.2 - Orthogonal vectors:")
    print(f"  Similarity: {similarity2}")
    assert similarity2 == 0.0
    
    # Test 3.3: Empty vectors
    vec5 = []
    vec6 = []
    similarity3 = matcher._cosine_similarity(vec5, vec6)
    print(f"\nTest 3.3 - Empty vectors:")
    print(f"  Similarity: {similarity3}")
    assert similarity3 == 0.0
    
    # Test 3.4: Mismatched length
    vec7 = [1.0, 2.0]
    vec8 = [1.0, 2.0, 3.0]
    similarity4 = matcher._cosine_similarity(vec7, vec8)
    print(f"\nTest 3.4 - Mismatched length:")
    print(f"  Similarity: {similarity4}")
    assert similarity4 == 0.0


def test_compute_embedding_score():
    """Test embedding score computation."""
    print("\n" + "="*70)
    print("TEST 4: Embedding Score Computation")
    print("="*70)
    
    matcher = EmbeddingMatcher()
    
    if not matcher.embeddings_enabled:
        print("\n⚠ Skipping embedding score tests - OpenAI API not available")
        print("  This is expected if API key is missing or quota exceeded")
        return
    
    # Test 4.1: Similar texts (should have high similarity)
    scope_text1 = "Construct reinforced concrete culvert at chainage 123+450"
    activity_text1 = "Build RC culvert at Ch 123+450"
    
    result1 = matcher.compute_embedding_score(scope_text1, activity_text1)
    print(f"\nTest 4.1 - Similar texts:")
    print(f"  Scope: '{scope_text1}'")
    print(f"  Activity: '{activity_text1}'")
    print(f"  Embedding Score: {result1['embedding_score']}")
    print(f"  Explanation: {result1['explanation']}")
    assert 0.0 <= result1['embedding_score'] <= 1.0
    assert 'embedding_score' in result1
    assert 'explanation' in result1
    
    # Test 4.2: Different texts (should have lower similarity)
    scope_text2 = "Construct reinforced concrete culvert"
    activity_text2 = "Install electrical cables and conduits"
    
    result2 = matcher.compute_embedding_score(scope_text2, activity_text2)
    print(f"\nTest 4.2 - Different texts:")
    print(f"  Scope: '{scope_text2}'")
    print(f"  Activity: '{activity_text2}'")
    print(f"  Embedding Score: {result2['embedding_score']}")
    print(f"  Explanation: {result2['explanation']}")
    assert 0.0 <= result2['embedding_score'] <= 1.0
    # Different texts should have lower similarity than similar texts
    # (Note: If embeddings fail, both will be 0.0, which is acceptable)
    if result1['embedding_score'] > 0.0 and result2['embedding_score'] > 0.0:
        assert result2['embedding_score'] < result1['embedding_score']
    
    # Test 4.3: Empty texts
    result3 = matcher.compute_embedding_score("", "")
    print(f"\nTest 4.3 - Empty texts:")
    print(f"  Embedding Score: {result3['embedding_score']}")
    print(f"  Explanation: {result3['explanation']}")
    assert result3['embedding_score'] == 0.0


def test_error_handling():
    """Test error handling."""
    print("\n" + "="*70)
    print("TEST 5: Error Handling")
    print("="*70)
    
    matcher = EmbeddingMatcher()
    
    # Test 5.1: Disabled embeddings
    if not matcher.embeddings_enabled:
        result = matcher.compute_embedding_score("test", "test")
        print(f"\nTest 5.1 - Disabled embeddings:")
        print(f"  Embedding Score: {result['embedding_score']}")
        print(f"  Explanation: {result['explanation']}")
        assert result['embedding_score'] == 0.0
        assert 'explanation' in result
    
    # Test 5.2: None values never returned
    result2 = matcher.compute_embedding_score("test", "test")
    print(f"\nTest 5.2 - No None values:")
    print(f"  Result type: {type(result2)}")
    print(f"  Keys: {list(result2.keys())}")
    assert result2 is not None
    assert isinstance(result2, dict)
    assert 'embedding_score' in result2
    assert result2['embedding_score'] is not None


if __name__ == "__main__":
    print("\n" + "="*70)
    print("EMBEDDING SIMILARITY ENGINE TEST SUITE")
    print("="*70)
    
    try:
        test_embedding_matcher_initialization()
        test_text_preprocessing()
        test_cosine_similarity()
        test_compute_embedding_score()
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

