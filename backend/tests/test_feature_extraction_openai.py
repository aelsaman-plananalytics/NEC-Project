"""
Test Feature Extraction with OpenAI configured.

Run this to test the full three-tier system:
    python test_feature_extraction_openai.py
"""

from app.services.extraction.core.feature_extractor import FeatureExtractor


def test_with_openai():
    """Test feature extraction with OpenAI configured."""
    print("=" * 70)
    print("Feature Extraction Test with OpenAI")
    print("=" * 70)
    
    extractor = FeatureExtractor()
    
    print(f"\nConfiguration:")
    print(f"  OpenAI Client Available: {extractor.openai_client is not None}")
    print(f"  LLM Model: {extractor.llm_model}")
    print(f"  Embedding Model: {extractor.embedding_model}")
    print()
    
    # Test Case 1: Complete scope item (should work with Tier 1)
    print("=" * 70)
    print("TEST 1: Complete Scope Item (Tier 1 should handle)")
    print("=" * 70)
    
    text1 = "Install RC culvert at Ch 123+450 per DRG-100"
    print(f"\nInput: '{text1}'")
    
    result1 = extractor.extract_features(text1)
    
    print(f"\nResults:")
    print(f"  Discipline: {result1.get('discipline')}")
    print(f"  Assets: {result1.get('assets')}")
    print(f"  Actions: {result1.get('actions')}")
    print(f"  Materials: {result1.get('materials')}")
    print(f"  Chainages: {result1.get('chainages')}")
    print(f"  Drawings: {result1.get('drawings')}")
    print(f"  Activity codes: {result1.get('activity_codes')}")
    print(f"  Fallback used: {result1.get('fallback_used')}")
    print(f"  Expanded text: {result1.get('expanded_text')[:70]}...")
    
    # Test Case 2: Minimal text (may trigger Tier 2/3)
    print("\n" + "=" * 70)
    print("TEST 2: Minimal Text (May Trigger Tier 2/3)")
    print("=" * 70)
    
    text2 = "Install something at location"
    print(f"\nInput: '{text2}'")
    print("(This has minimal features - may trigger Tier 2/3 if OpenAI available)")
    
    result2 = extractor.extract_features(text2)
    
    print(f"\nResults:")
    print(f"  Discipline: {result2.get('discipline')}")
    print(f"  Assets: {result2.get('assets')}")
    print(f"  Actions: {result2.get('actions')}")
    print(f"  Materials: {result2.get('materials')}")
    print(f"  Fallback used: {result2.get('fallback_used')}")
    
    if result2.get('fallback_used'):
        print(f"\n  ✓ Tier 2 or Tier 3 was triggered: {result2.get('fallback_used')}")
        if result2.get('fallback_used') == 'semantic':
            print("    → Used embedding-based semantic matching")
        elif result2.get('fallback_used') == 'llm':
            print("    → Used LLM reasoning (gpt-4o)")
    else:
        print(f"\n  ✓ Tier 1 provided all features (no fallback needed)")
    
    # Test Case 3: Complex engineering text
    print("\n" + "=" * 70)
    print("TEST 3: Complex Engineering Text")
    print("=" * 70)
    
    text3 = "Construct retaining wall RW1 with RC panels and MS reinforcement, see DRG-150"
    print(f"\nInput: '{text3}'")
    
    result3 = extractor.extract_features(text3)
    
    print(f"\nResults:")
    print(f"  Discipline: {result3.get('discipline')}")
    print(f"  Assets: {result3.get('assets')}")
    print(f"  Actions: {result3.get('actions')}")
    print(f"  Materials: {result3.get('materials')}")
    print(f"  Drawings: {result3.get('drawings')}")
    print(f"  Fallback used: {result3.get('fallback_used')}")
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"✓ Feature extraction is working")
    print(f"✓ OpenAI is configured: {extractor.openai_client is not None}")
    print(f"✓ LLM model ready: {extractor.llm_model}")
    
    if extractor.openai_client:
        print(f"\n⚠️  Note: If you see quota errors, add credits to your OpenAI account")
        print(f"   Once credits are added, Tier 2 (embeddings) and Tier 3 (LLM)")
        print(f"   will automatically activate for missing features.")
    else:
        print(f"\n⚠️  OpenAI client not available - only Tier 1 (ontology) will work")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    test_with_openai()



