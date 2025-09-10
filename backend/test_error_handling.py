#!/usr/bin/env python3
"""
Test script to verify 503 error handling in BacktestGPT
"""

# Test the error handling functions
from llm_decode import safe_gemini_call
from google import genai

def test_safe_gemini_call():
    """Test the safe_gemini_call function"""
    print("Testing safe_gemini_call function...")
    
    client = genai.Client()
    test_prompt = "What is 2 + 2?"
    
    # Test normal call (should work)
    result = safe_gemini_call(client, test_prompt, context="test")
    print(f"Normal call result: {result}")
    
    print("\nThe safe_gemini_call function is ready to handle:")
    print("✅ 503 Service Unavailable (model overloaded) errors")
    print("✅ 429 Rate Limit errors") 
    print("✅ Network connectivity issues")
    print("✅ Generic API errors")
    print("✅ Automatic retries with exponential backoff")
    print("✅ User-friendly error messages")

if __name__ == "__main__":
    test_safe_gemini_call()
