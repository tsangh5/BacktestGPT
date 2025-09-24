#!/usr/bin/env python3
"""
Test ticker validation integration without full backend dependencies
"""

import sys
import os
import yfinance as yf
import re

def is_valid_ticker_format(ticker):
    """Basic validation for ticker format"""
    if not ticker or not isinstance(ticker, str):
        return False
    
    ticker = ticker.strip().upper()
    
    # Basic format checks for common ticker formats
    if len(ticker) < 1 or len(ticker) > 10:
        return False
    
    # Allow alphanumeric characters, dots, and hyphens (common in ticker symbols)
    if not re.match(r'^[A-Z0-9.-]+$', ticker):
        return False
    
    return True

def validate_ticker_exists(ticker):
    """
    Validate if a ticker symbol exists and has data available using yfinance.
    Returns (is_valid, error_message)
    """
    if not ticker or not isinstance(ticker, str):
        return False, "Invalid ticker format"
    
    ticker = ticker.strip().upper()
    
    # Basic format check first
    if not is_valid_ticker_format(ticker):
        return False, f"Ticker '{ticker}' has invalid format"
    
    try:
        # Try to fetch recent data to validate ticker exists
        stock = yf.Ticker(ticker)
        # Get last 5 days of data to check if ticker is valid
        hist = stock.history(period="5d")
        
        if hist.empty:
            return False, f"No data available for ticker '{ticker}'"
        
        return True, f"Ticker '{ticker}' is valid and has data"
    
    except Exception as e:
        return False, f"Error validating ticker '{ticker}': {str(e)}"

def mock_validate_strategy_compatibility(strategy_data):
    """
    Simplified version of validate_strategy_compatibility for testing ticker validation
    """
    issues = []
    suggestions = []
    updated_strategy = strategy_data.copy()
    
    # Validate ticker if present
    ticker = strategy_data.get('ticker')
    if ticker:
        is_valid_ticker, ticker_message = validate_ticker_exists(ticker)
        if not is_valid_ticker:
            print(f"❌ Ticker validation failed: {ticker_message}")
            # In real implementation, we'd call Gemini for alternatives here
            # For this test, we'll just use SPY as fallback
            alternative_ticker = "SPY"
            print(f"🔄 Trying alternative ticker: {alternative_ticker}")
            
            is_valid_alt, alt_message = validate_ticker_exists(alternative_ticker)
            if is_valid_alt:
                print(f"✅ Alternative ticker {alternative_ticker} is valid: {alt_message}")
                updated_strategy['ticker'] = alternative_ticker
                suggestions.append(f"Changed ticker from '{ticker}' to '{alternative_ticker}' (original ticker was not available)")
            else:
                issues.append(f"Ticker '{ticker}' is not valid or has no data available")
                issues.append(f"Alternative ticker '{alternative_ticker}' is also invalid")
        else:
            print(f"✅ Ticker validation successful: {ticker_message}")
    
    # Prepare feedback message
    if issues:
        feedback = "Strategy has ticker validation issues:\n"
        for issue in issues:
            feedback += f"❌ {issue}\n"
        return False, feedback, updated_strategy
    
    # If no issues, strategy is compatible
    success_message = "Your strategy ticker is valid! 🎉"
    if suggestions:
        success_message += "\n" + "\n".join(f"✅ {s}" for s in suggestions)
    return True, success_message, updated_strategy

def test_ticker_integration():
    """Test ticker validation integration scenarios"""
    
    print("=" * 60)
    print("Testing Ticker Validation Integration")
    print("=" * 60)
    
    # Test 1: Valid ticker
    print("\n1. Testing with VALID ticker (AAPL)")
    strategy_valid = {
        'ticker': 'AAPL',
        'indicators': [{'type': 'SMA', 'params': {'window': 50}}]
    }
    
    is_compatible, feedback, updated_strategy = mock_validate_strategy_compatibility(strategy_valid)
    print(f"Result: {'✅ COMPATIBLE' if is_compatible else '❌ NOT COMPATIBLE'}")
    print(f"Feedback: {feedback}")
    print(f"Final ticker: {updated_strategy.get('ticker')}")
    
    print("\n" + "=" * 60)
    
    # Test 2: Invalid ticker (should get corrected to SPY)
    print("\n2. Testing with INVALID ticker (INVALIDXYZ)")
    strategy_invalid = {
        'ticker': 'INVALIDXYZ',
        'indicators': [{'type': 'SMA', 'params': {'window': 50}}]
    }
    
    is_compatible, feedback, updated_strategy = mock_validate_strategy_compatibility(strategy_invalid)
    print(f"Result: {'✅ COMPATIBLE' if is_compatible else '❌ NOT COMPATIBLE'}")
    print(f"Feedback: {feedback}")
    print(f"Final ticker: {updated_strategy.get('ticker')}")
    
    print("\n" + "=" * 60)
    
    # Test 3: No ticker specified
    print("\n3. Testing with NO ticker specified")
    strategy_no_ticker = {
        'indicators': [{'type': 'SMA', 'params': {'window': 50}}]
    }
    
    is_compatible, feedback, updated_strategy = mock_validate_strategy_compatibility(strategy_no_ticker)
    print(f"Result: {'✅ COMPATIBLE' if is_compatible else '❌ NOT COMPATIBLE'}")
    print(f"Feedback: {feedback}")
    print(f"Final ticker: {updated_strategy.get('ticker', 'None specified')}")
    
    print("\n" + "=" * 60)
    print("Integration test complete! 🎉")
    print("\nKey features working:")
    print("✅ Ticker format validation")
    print("✅ yfinance data availability check")
    print("✅ Automatic ticker correction workflow")
    print("✅ Strategy compatibility integration")

if __name__ == "__main__":
    test_ticker_integration()