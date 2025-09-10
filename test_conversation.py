#!/usr/bin/env python3

"""
Test the conversational flow
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.llm_decode import decode_natural_language

def test_conversation():
    """Test conversational responses"""
    
    print("Testing conversational flow...")
    
    # Test 1: Initial vague request
    print("\n" + "="*50)
    print("Test 1: Vague initial request")
    result = decode_natural_language("I want to trade stocks", [])
    if result.get('conversation'):
        print(f"Assistant: {result.get('message')}")
        print("✓ Conversational response received")
    else:
        print("✗ No conversational response")
    
    # Test 2: Follow-up with more info
    conversation_history = [
        {"role": "user", "content": "I want to trade stocks"},
        {"role": "assistant", "content": "Which stock would you like to backtest?"}
    ]
    print("\n" + "="*50) 
    print("Test 2: Follow-up with stock name")
    result2 = decode_natural_language("Apple", conversation_history)
    if result2.get('conversation'):
        print(f"Assistant: {result2.get('message')}")
        print("✓ Follow-up conversational response received")
    else:
        print("✗ No follow-up response")

if __name__ == "__main__":
    test_conversation()
