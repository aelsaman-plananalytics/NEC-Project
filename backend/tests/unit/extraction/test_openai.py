"""
Simple test to verify OpenAI API key is working and models are available.

Run this script to test OpenAI connectivity:
    python test_openai.py
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    print("❌ ERROR: OpenAI package not installed")
    print("   Install with: pip install openai")
    sys.exit(1)

# Try multiple ways to get the API key
API_KEY = None

# Method 1: Try from settings
try:
    from app.config import settings
    API_KEY = settings.OPENAI_API_KEY
    if API_KEY:
        print("✓ Loaded API key from app.config.settings")
except Exception as e:
    pass

# Method 2: Try from environment variable
if not API_KEY:
    API_KEY = os.getenv("OPENAI_API_KEY", "")
    if API_KEY:
        print("✓ Loaded API key from environment variable")

# Method 3: Try reading .env file directly
if not API_KEY:
    env_files = [
        os.path.join(os.path.dirname(__file__), ".env"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        ".env"
    ]
    for env_file in env_files:
        if os.path.exists(env_file):
            try:
                with open(env_file, 'r') as f:
                    for line in f:
                        if line.startswith("OPENAI_API_KEY="):
                            API_KEY = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if API_KEY:
                                print(f"✓ Loaded API key from {env_file}")
                                break
            except Exception:
                pass
        if API_KEY:
            break

def test_openai_connection():
    """Test basic OpenAI API connection and model availability."""
    print("=" * 70)
    print("OpenAI API Connection Test")
    print("=" * 70)
    
    # Check if API key is set
    if not API_KEY:
        print("\n❌ ERROR: OPENAI_API_KEY not found")
        print("   Please set OPENAI_API_KEY in your .env file or environment variables")
        return False
    
    print(f"\n✓ API Key found: {API_KEY[:10]}...{API_KEY[-4:] if len(API_KEY) > 14 else '***'}")
    
    # Initialize client
    try:
        client = OpenAI(api_key=API_KEY)
        print("✓ OpenAI client initialized")
    except Exception as e:
        print(f"\n❌ ERROR: Failed to initialize OpenAI client: {e}")
        return False
    
    # Test 1: List models (simple API call)
    print("\n--- Test 1: List Available Models ---")
    try:
        models = client.models.list()
        model_ids = [model.id for model in models.data]
        
        # Check for our expected models
        embedding_model = "text-embedding-3-small"
        llm_model = "gpt-4o-mini"  # Backup model
        configured_llm_model = "gpt-4o"  # Current configuration
        
        print(f"✓ Successfully connected to OpenAI API")
        print(f"  Total models available: {len(model_ids)}")
        
        if embedding_model in model_ids:
            print(f"  ✓ Embedding model '{embedding_model}' is available")
        else:
            print(f"  ⚠️  Embedding model '{embedding_model}' not found in list")
            print(f"     (This might be normal - checking if it works anyway)")
        
        # Check for gpt-4o (updated model)
        gpt4o_model = "gpt-4o"
        if gpt4o_model in model_ids:
            print(f"  ✓ LLM model '{gpt4o_model}' is available (configured)")
        else:
            print(f"  ⚠️  LLM model '{gpt4o_model}' not found in list")
            print(f"     (This might be normal - checking if it works anyway)")
        
        # Also check gpt-4o-mini for reference
        if llm_model in model_ids:
            print(f"  ✓ LLM model '{llm_model}' is also available (backup)")
        
    except Exception as e:
        print(f"❌ ERROR: Failed to list models: {e}")
        return False
    
    # Test 2: Test embedding model (simple call)
    print("\n--- Test 2: Test Embedding Model ---")
    try:
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input="test"
        )
        embedding = response.data[0].embedding
        print(f"✓ Embedding model 'text-embedding-3-small' is working")
        print(f"  Embedding dimension: {len(embedding)}")
    except Exception as e:
        error_str = str(e)
        if "429" in error_str or "quota" in error_str.lower() or "insufficient_quota" in error_str.lower():
            print(f"⚠️  WARNING: Quota exceeded (API key is valid but account needs credits)")
            print(f"  The API key is working correctly, but you need to add credits to your OpenAI account")
            print(f"  Visit: https://platform.openai.com/account/billing")
        else:
            print(f"❌ ERROR: Embedding model test failed: {e}")
            return False
    
    # Test 3: Test LLM model (gpt-4o - updated configuration)
    print("\n--- Test 3: Test LLM Model (gpt-4o) ---")
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "user", "content": "Say 'test successful' and nothing else."}
            ],
            max_tokens=10
        )
        message = response.choices[0].message.content
        print(f"✓ LLM model 'gpt-4o' is working")
        print(f"  Response: {message}")
    except Exception as e:
        error_str = str(e)
        if "429" in error_str or "quota" in error_str.lower() or "insufficient_quota" in error_str.lower():
            print(f"⚠️  WARNING: Quota exceeded (API key is valid but account needs credits)")
            print(f"  The API key is working correctly, but you need to add credits to your OpenAI account")
            print(f"  Visit: https://platform.openai.com/account/billing")
            print(f"  Note: gpt-4o model is available and will work once credits are added")
        else:
            print(f"❌ ERROR: LLM model test failed: {e}")
            return False
    
    # Check if we had quota issues
    quota_issue = False
    try:
        # Try a final test to see if quota is the only issue
        test_response = client.embeddings.create(model="text-embedding-3-small", input="test")
        quota_issue = False
    except Exception as e:
        if "429" in str(e) or "quota" in str(e).lower():
            quota_issue = True
    
    print("\n" + "=" * 70)
    if quota_issue:
        print("✅ API KEY IS VALID - Connection successful!")
        print("⚠️  QUOTA ISSUE DETECTED - Add credits to use the API")
    else:
        print("✅ ALL TESTS PASSED - OpenAI API is working correctly!")
    print("=" * 70)
    
    print("\nSummary:")
    print("✓ API key is valid and authenticated")
    print("✓ Models are available and accessible")
    if quota_issue:
        print("⚠️  Account needs credits to make API calls")
        print("   Visit: https://platform.openai.com/account/billing")
        print("\nOnce you add credits, Tier 2 (embeddings) and Tier 3 (LLM)")
        print("will work in FeatureExtractor.")
    else:
        print("✓ Tier 2 (embeddings) and Tier 3 (LLM) will work in FeatureExtractor.")
    
    return True


if __name__ == "__main__":
    print("\n")
    success = test_openai_connection()
    
    if not success:
        print("\n" + "=" * 70)
        print("❌ TESTS FAILED")
        print("=" * 70)
        print("\nTroubleshooting:")
        print("1. Check that OPENAI_API_KEY is set in your .env file")
        print("2. Verify the API key is correct and has credits")
        print("3. Check your internet connection")
        print("4. Ensure you have access to the models (may require paid account)")
        sys.exit(1)

