#!/usr/bin/env python3
"""
Test ticker validation integration in the main processing pipeline
"""

import sys
import os

# Add backend directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from llm_decode import validate_ticker_exists, get_alternative_ticker_from_gemini, validate_strategy_compatibility
from genai import Client
import genai

def test_ticker_validation_integration():
    """Test the ticker validation integration with strategy compatibility"""
    
    print("=" * 50)
    print("Testing Ticker Validation Integration")
    print("=" * 50)
    
    # Test data with invalid ticker
    strategy_data = {
        'ticker': 'INVALID123',
        'indicators': [
            {
                'id': 'SMA50',
                'type': 'SMA',
                'params': {'window': 50, 'column': 'Close'}
            }
        ],
        'entry': {
            'op': 'cross_above',
            'args': ['Close', 'SMA50.ma']
        },
        'exit': {
            'op': 'cross_below', 
            'args': ['Close', 'SMA50.ma']
        }
    }
    
    # Mock registries (simplified for testing)
    indicators_registry = {
        'SMA': {'description': 'Simple Moving Average'},
        'RSI': {'description': 'Relative Strength Index'}
    }
    
    operators_registry = {
        'crossover': ['cross_above', 'cross_below'],
        'comparison': ['greater_than', 'less_than']
    }
    
    strategies_registry = {
        'sma_crossover': {
            'description': 'Simple Moving Average Crossover',
            'indicators': [{'type': 'SMA'}]
        }
    }
    
    print("\n1. Testing with invalid ticker (no Gemini client - should fail)")
    print(f"Input ticker: {strategy_data['ticker']}")
    
    is_compatible, feedback, updated_strategy = validate_strategy_compatibility(
        strategy_data, 
        indicators_registry, 
        operators_registry, 
        strategies_registry
    )
    
    print(f"Compatible: {is_compatible}")
    print(f"Feedback: {feedback}")
    print(f"Updated ticker: {updated_strategy.get('ticker')}")
    
    print("\n" + "=" * 50)
    
    print("\n2. Testing with invalid ticker (with Gemini client - should try alternatives)")
    print(f"Input ticker: {strategy_data['ticker']}")
    
    try:
        client = genai.Client()
        is_compatible, feedback, updated_strategy = validate_strategy_compatibility(
            strategy_data, 
            indicators_registry, 
            operators_registry, 
            strategies_registry,
            client
        )
        
        print(f"Compatible: {is_compatible}")
        print(f"Feedback: {feedback}")
        print(f"Updated ticker: {updated_strategy.get('ticker')}")
        
    except Exception as e:
        print(f"Error with Gemini client: {e}")
        print("(This is expected if API keys are not configured)")
    
    print("\n" + "=" * 50)
    
    print("\n3. Testing with valid ticker")
    strategy_data_valid = strategy_data.copy()
    strategy_data_valid['ticker'] = 'AAPL'
    print(f"Input ticker: {strategy_data_valid['ticker']}")
    
    is_compatible, feedback, updated_strategy = validate_strategy_compatibility(
        strategy_data_valid, 
        indicators_registry, 
        operators_registry, 
        strategies_registry
    )
    
    print(f"Compatible: {is_compatible}")
    print(f"Feedback: {feedback}")
    print(f"Updated ticker: {updated_strategy.get('ticker')}")
    
    print("\n" + "=" * 50)
    print("Integration test complete!")

if __name__ == "__main__":
    test_ticker_validation_integration()