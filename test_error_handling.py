#!/usr/bin/env python3

"""
Quick test of the error handling functionality
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.llm_decode import decode_natural_language

def test_error_cases():
    """Test various error scenarios"""
    
    print("Testing error handling...")
    
    # Test case 1: Completely ambiguous input
    print("\n" + "="*50)
    print("Test 1: Vague input")
    result1 = decode_natural_language("make money fast")
    print(f"Result: {result1.get('error', 'No error')}")
    
    # Test case 2: Missing key information
    print("\n" + "="*50)
    print("Test 2: Missing indicators")
    result2 = decode_natural_language("buy and sell stocks")
    print(f"Result: {result2.get('error', 'No error')}")
    
    # Test case 3: Partial but insufficient info
    print("\n" + "="*50)
    print("Test 3: Missing exit conditions")
    result3 = decode_natural_language("buy AAPL when price goes up")
    print(f"Result: {result3.get('error', 'No error')}")
    
    print("\nTesting complete!")

if __name__ == "__main__":
    test_error_cases()
