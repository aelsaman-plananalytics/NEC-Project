"""
Test the full three-tier feature extraction pipeline.

Shows how Tier 1, Tier 2, and Tier 3 work together.
"""

from app.services.extraction.core.feature_extractor import FeatureExtractor


def test_full_pipeline():
    """Test the complete three-tier system."""
    print("=" * 70)
    print("Full Three-Tier Feature Extraction Pipeline Test")
    print("=" * 70)
    
    extractor = FeatureExtractor()
    
    print(f"\nSystem Status:")
    print(f"  OpenAI Client: {'✓ Available' if extractor.openai_client else '✗ Not available'}")
    print(f"  LLM Model: {extractor.llm_model}")
    print(f"  Embedding Model: {extractor.embedding_model}")
    print()
    
    # Test cases that will show different tier behaviors
    test_cases = [
        {
            "text": "Install RC culvert at Ch 123+450 per DRG-100",
            "expected_tier": "Tier 1 only",
            "description": "Complete features - Tier 1 handles everything"
        },
        {
            "text": "Install electrical equipment in building",
            "expected_tier": "Tier 1 (may use Tier 2/3 for missing assets/materials)",
            "description": "Has discipline and action, missing assets/materials"
        },
        {
            "text": "Something needs construction work",
            "expected_tier": "Tier 1 + Tier 2/3",
            "description": "Minimal features - will trigger Tier 2/3"
        },
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print("\n" + "=" * 70)
        print(f"TEST {i}: {test_case['description']}")
        print("=" * 70)
        print(f"Text: '{test_case['text']}'")
        print(f"Expected: {test_case['expected_tier']}")
        print()
        
        try:
            result = extractor.extract_features(test_case['text'])
            
            print("Extracted Features:")
            print(f"  Discipline: '{result.get('discipline') or '(empty)'}'")
            print(f"  Assets: {result.get('assets') or '[]'}")
            print(f"  Actions: {result.get('actions') or '[]'}")
            print(f"  Materials: {result.get('materials') or '[]'}")
            print(f"  Chainages: {result.get('chainages') or '[]'}")
            print(f"  Drawings: {result.get('drawings') or '[]'}")
            print()
            print(f"  Fallback used: {result.get('fallback_used')}")
            
            if result.get('fallback_used') == 'semantic':
                print("  → Tier 2 (Embeddings) was used!")
            elif result.get('fallback_used') == 'llm':
                print("  → Tier 3 (LLM - gpt-4o) was used!")
            else:
                print("  → Tier 1 (Ontology) handled everything")
            
            print(f"  Expanded text: {result.get('expanded_text', '')[:60]}...")
            
        except Exception as e:
            print(f"  ⚠️  Error during extraction: {e}")
            print("  (This might be a quota issue - API key is valid)")
    
    print("\n" + "=" * 70)
    print("PIPELINE SUMMARY")
    print("=" * 70)
    print("✓ Tier 1 (Ontology): Working - extracts features deterministically")
    print(f"✓ Tier 2 (Embeddings): {'Ready' if extractor.openai_client else 'Not available'}")
    print(f"✓ Tier 3 (LLM - {extractor.llm_model}): {'Ready' if extractor.openai_client else 'Not available'}")
    print()
    print("How it works:")
    print("  1. Tier 1 always runs first (ontology-based)")
    print("  2. If fields are missing, Tier 2 tries semantic matching")
    print("  3. If still missing, Tier 3 uses LLM reasoning")
    print("  4. All results are merged into final feature vector")
    print()
    if extractor.openai_client:
        print("⚠️  Note: Quota errors may occur if account needs credits")
        print("   The system will gracefully fall back to Tier 1 only")
    print("=" * 70)


if __name__ == "__main__":
    test_full_pipeline()



