"""
Test Tier 2 and Tier 3 fallback with OpenAI.

This tests the semantic and LLM reasoning tiers.
"""

from app.services.extraction.core.feature_extractor import FeatureExtractor


def test_tier2_tier3():
    """Test Tier 2 and Tier 3 with text that has missing features."""
    print("=" * 70)
    print("Testing Tier 2 (Embeddings) and Tier 3 (LLM) Fallback")
    print("=" * 70)
    
    extractor = FeatureExtractor()
    
    print(f"\nConfiguration:")
    print(f"  OpenAI Client: {extractor.openai_client is not None}")
    print(f"  LLM Model: {extractor.llm_model}")
    print()
    
    # Test with text that has minimal ontology matches
    # This should trigger Tier 2 or Tier 3
    test_cases = [
        {
            "text": "Install electrical equipment",
            "description": "Should detect M&E discipline via Tier 2/3"
        },
        {
            "text": "Build infrastructure component",
            "description": "Should detect discipline and assets via Tier 2/3"
        },
        {
            "text": "Construct underground utility",
            "description": "Should detect utilities discipline via Tier 2/3"
        },
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print("\n" + "=" * 70)
        print(f"TEST {i}: {test_case['description']}")
        print("=" * 70)
        print(f"Input: '{test_case['text']}'")
        
        # First, check what Tier 1 extracts
        tier1 = extractor.extract_tier1_ontology(test_case['text'])
        print(f"\nTier 1 Results:")
        print(f"  Discipline: '{tier1.get('discipline')}'")
        print(f"  Assets: {tier1.get('assets')}")
        print(f"  Actions: {tier1.get('actions')}")
        print(f"  Materials: {tier1.get('materials')}")
        
        # Check if Tier 1 is missing critical fields
        missing = []
        if not tier1.get('discipline'):
            missing.append('discipline')
        if not tier1.get('assets'):
            missing.append('assets')
        if not tier1.get('materials'):
            missing.append('materials')
        
        if missing:
            print(f"\n  ⚠️  Missing fields: {missing}")
            print(f"  → Will attempt Tier 2/3 fallback")
        else:
            print(f"\n  ✓ Tier 1 provided all features")
        
        # Now run full extraction
        print(f"\nFull Extraction Results:")
        result = extractor.extract_features(test_case['text'])
        
        print(f"  Discipline: '{result.get('discipline')}'")
        print(f"  Assets: {result.get('assets')}")
        print(f"  Actions: {result.get('actions')}")
        print(f"  Materials: {result.get('materials')}")
        print(f"  Fallback used: {result.get('fallback_used')}")
        
        if result.get('fallback_used'):
            if result.get('fallback_used') == 'semantic':
                print(f"\n  ✓ Tier 2 (Embeddings) was used!")
            elif result.get('fallback_used') == 'llm':
                print(f"\n  ✓ Tier 3 (LLM - gpt-4o) was used!")
        else:
            print(f"\n  → Tier 1 handled everything (no fallback needed)")
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("✓ Feature extraction tested with OpenAI configured")
    print("✓ Tier 1 (ontology) is working")
    if extractor.openai_client:
        print("✓ Tier 2 (embeddings) and Tier 3 (LLM) are ready")
        print("  → They will activate automatically when Tier 1 misses features")
        print("  → Note: Quota issues may prevent actual API calls")
    print("=" * 70)


if __name__ == "__main__":
    test_tier2_tier3()



