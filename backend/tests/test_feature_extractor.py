"""
Test script for FeatureExtractor class.

Run this script to test the three-tier feature extraction system:
    python test_feature_extractor.py
"""

from app.services.extraction.core.feature_extractor import FeatureExtractor


def test_tier1_ontology():
    """Test Tier 1: Ontology-based deterministic extraction."""
    print("=" * 70)
    print("TEST 1: Tier 1 - Ontology-Based Extraction")
    print("=" * 70)
    
    extractor = FeatureExtractor()
    
    test_cases = [
        "Install RC culvert at Ch 123+450 per DRG-100",
        "Construct retaining wall RW1 with MS pipe",
        "Placement of PC unit and SS pipe at Chainage 200+000",
        "Excavate and install manhole at Ch 150+250 per GA-200",
        "Pavement construction with AC and DBM layers",
    ]
    
    for i, text in enumerate(test_cases, 1):
        print(f"\n--- Test Case {i} ---")
        print(f"Input: '{text}'")
        
        result = extractor.extract_tier1_ontology(text)
        
        print(f"Discipline: {result.get('discipline', 'N/A')}")
        print(f"Assets: {result.get('assets', [])}")
        print(f"Actions: {result.get('actions', [])}")
        print(f"Materials: {result.get('materials', [])}")
        print(f"Chainages: {result.get('chainages', [])}")
        print(f"Drawings: {result.get('drawings', [])}")
        print(f"Activity codes: {result.get('activity_codes', [])}")
        print(f"Expanded text: {result.get('expanded_text', '')[:60]}...")


def test_preprocessing():
    """Test text preprocessing."""
    print("\n" + "=" * 70)
    print("TEST 2: Text Preprocessing")
    print("=" * 70)
    
    extractor = FeatureExtractor()
    
    test_cases = [
        "  Install   RC   culvert  ",
        "Install\nRC\nculvert\nat\nCh 123+450",
        "Install RC culvert (see DRG-100)",
        "Install, RC, culvert, and, MS, pipe",
    ]
    
    for i, text in enumerate(test_cases, 1):
        print(f"\n--- Test Case {i} ---")
        print(f"Original: '{text}'")
        preprocessed = extractor.preprocess_text(text)
        print(f"Preprocessed: '{preprocessed}'")


def test_full_pipeline():
    """Test full feature extraction pipeline."""
    print("\n" + "=" * 70)
    print("TEST 3: Full Pipeline (Tier 1 + Tier 2 + Tier 3)")
    print("=" * 70)
    
    extractor = FeatureExtractor()
    
    test_cases = [
        {
            "text": "Install RC culvert at Ch 123+450 per DRG-100",
            "description": "Complete scope item with all features"
        },
        {
            "text": "Construct bridge deck",
            "description": "Simple construction task"
        },
        {
            "text": "Excavate foundation and backfill",
            "description": "Earthworks task"
        },
        {
            "text": "Install electrical conduit",
            "description": "M&E task"
        },
        {
            "text": "Pavement resurfacing with AC layer",
            "description": "Highway task"
        },
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n--- Test Case {i}: {test_case['description']} ---")
        print(f"Input: '{test_case['text']}'")
        
        result = extractor.extract_features(test_case['text'])
        
        print(f"Discipline: {result.get('discipline', 'N/A')}")
        print(f"Assets: {result.get('assets', [])}")
        print(f"Actions: {result.get('actions', [])}")
        print(f"Materials: {result.get('materials', [])}")
        print(f"Chainages: {result.get('chainages', [])}")
        print(f"Drawings: {result.get('drawings', [])}")
        print(f"Activity codes: {result.get('activity_codes', [])}")
        print(f"Fallback used: {result.get('fallback_used', False)}")
        print(f"Expanded text: {result.get('expanded_text', '')[:70]}...")


def test_edge_cases():
    """Test edge cases and error handling."""
    print("\n" + "=" * 70)
    print("TEST 4: Edge Cases and Error Handling")
    print("=" * 70)
    
    extractor = FeatureExtractor()
    
    test_cases = [
        ("", "Empty string"),
        ("   ", "Whitespace only"),
        ("No engineering terms here", "No features"),
        ("RC", "Single abbreviation"),
        ("Ch 123+450", "Only chainage"),
        ("DRG-100", "Only drawing"),
    ]
    
    for i, (text, description) in enumerate(test_cases, 1):
        print(f"\n--- Test Case {i}: {description} ---")
        print(f"Input: '{text}'")
        
        try:
            result = extractor.extract_features(text)
            print(f"Discipline: '{result.get('discipline', 'N/A')}'")
            print(f"Assets: {result.get('assets', [])}")
            print(f"Actions: {result.get('actions', [])}")
            print(f"Materials: {result.get('materials', [])}")
            print(f"All fields present: {all(key in result for key in ['discipline', 'assets', 'actions', 'materials', 'chainages', 'drawings', 'activity_codes', 'expanded_text', 'fallback_used'])}")
            print(f"No None values: {not any(v is None for v in result.values())}")
        except Exception as e:
            print(f"ERROR: {e}")


def test_merge_features():
    """Test feature merging logic."""
    print("\n" + "=" * 70)
    print("TEST 5: Feature Merging")
    print("=" * 70)
    
    extractor = FeatureExtractor()
    
    tier1 = {
        "discipline": "structures",
        "assets": ["culvert"],
        "actions": ["install"],
        "materials": ["concrete"],
        "chainages": [],
        "drawings": ["DRG-100"],
        "activity_codes": [],
        "expanded_text": "Install RC culvert",
        "fallback_used": False,
    }
    
    tier2 = {
        "discipline": "",
        "assets": ["bridge"],
        "actions": [],
        "materials": ["steel"],
        "fallback_used": "semantic",
    }
    
    tier3 = {
        "discipline": "",
        "assets": [],
        "actions": ["construct"],
        "materials": [],
        "fallback_used": "llm",
    }
    
    print("Tier 1:", tier1)
    print("Tier 2:", tier2)
    print("Tier 3:", tier3)
    
    merged = extractor.merge_features(tier1, tier2, tier3)
    
    print("\nMerged result:")
    for key, value in merged.items():
        print(f"  {key}: {value}")


def test_openai_availability():
    """Test OpenAI availability and graceful degradation."""
    print("\n" + "=" * 70)
    print("TEST 6: OpenAI Availability Check")
    print("=" * 70)
    
    extractor = FeatureExtractor()
    
    print(f"OpenAI client available: {extractor.openai_client is not None}")
    print(f"Embedding model: {extractor.embedding_model}")
    print(f"LLM model: {extractor.llm_model}")
    
    if extractor.openai_client:
        print("\n✓ OpenAI is configured - Tier 2 and Tier 3 will be available")
    else:
        print("\n⚠ OpenAI not configured - Only Tier 1 (ontology) will be used")
        print("  This is fine for testing ontology extraction only")
    
    # Test that extraction still works without OpenAI
    text = "Install RC culvert at Ch 123+450"
    result = extractor.extract_features(text)
    print(f"\nTest extraction without OpenAI:")
    print(f"  Discipline: {result.get('discipline')}")
    print(f"  Assets: {result.get('assets')}")
    print(f"  Fallback used: {result.get('fallback_used')}")


def test_realistic_scope_items():
    """Test with realistic NEC scope item descriptions."""
    print("\n" + "=" * 70)
    print("TEST 7: Realistic NEC Scope Items")
    print("=" * 70)
    
    extractor = FeatureExtractor()
    
    scope_items = [
        "Installing PC unit and MS pipe at Ch 123+450 per DRG-100",
        "Construct RC culvert at Chainage 200+000, refer SHT05",
        "Placement of HDPE pipe for drainage system, activity A10234",
        "Excavate and install manhole at Ch 150+250 per GA-200",
        "Construct retaining wall RW1 with RC panels, see DRG-150",
        "Install SS pipe and fittings for water main, activity B5678",
        "Pavement construction with AC and DBM layers at Ch 100+000",
        "Erect steel bridge structure, refer DRAWING-300",
        "Backfill and compact around RC culvert at Chainage 175+500",
        "Install electrical conduit and cable, per M&E drawing SHT10",
    ]
    
    for i, text in enumerate(scope_items, 1):
        print(f"\n--- Scope Item {i} ---")
        print(f"Text: '{text}'")
        
        result = extractor.extract_features(text)
        
        print(f"  Discipline: {result.get('discipline')}")
        print(f"  Assets: {result.get('assets')}")
        print(f"  Actions: {result.get('actions')}")
        print(f"  Materials: {result.get('materials')}")
        if result.get('chainages'):
            print(f"  Chainages: {result.get('chainages')}")
        if result.get('drawings'):
            print(f"  Drawings: {result.get('drawings')}")
        if result.get('activity_codes'):
            print(f"  Activity codes: {result.get('activity_codes')}")
        print(f"  Fallback: {result.get('fallback_used')}")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("FEATURE EXTRACTION ENGINE TEST SUITE")
    print("=" * 70 + "\n")
    
    test_tier1_ontology()
    test_preprocessing()
    test_full_pipeline()
    test_edge_cases()
    test_merge_features()
    test_openai_availability()
    test_realistic_scope_items()
    
    print("\n" + "=" * 70)
    print("TESTING COMPLETE")
    print("=" * 70 + "\n")
    
    print("=" * 70)
    print("USAGE GUIDE")
    print("=" * 70)
    print("""
To use FeatureExtractor in your code:

    from app.services.extraction.core.feature_extractor import FeatureExtractor
    
    extractor = FeatureExtractor()
    text = "Install RC culvert at Ch 123+450 per DRG-100"
    features = extractor.extract_features(text)
    
    print(features['discipline'])  # "drainage"
    print(features['assets'])      # ["culvert"]
    print(features['actions'])     # ["install"]
    print(features['materials'])   # ["concrete", "rc"]
    print(features['chainages'])   # ["Ch 123+450 (123+450)"]
    print(features['drawings'])    # ["DRG-100"]
    print(features['fallback_used'])  # False, "semantic", or "llm"

The system automatically:
1. Uses Tier 1 (ontology) for deterministic extraction
2. Falls back to Tier 2 (embeddings) if fields are missing
3. Falls back to Tier 3 (LLM) if still missing
4. Merges all results into final feature vector

All fields are guaranteed to be present (never None):
- Empty strings "" for discipline
- Empty lists [] for list fields
- False, "semantic", or "llm" for fallback_used
""")



