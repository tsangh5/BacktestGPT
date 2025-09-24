#!/usr/bin/env python3
"""
Simple test of ticker validation functions
"""

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

def test_ticker_validation():
    """Test ticker validation with various inputs"""
    
    test_cases = [
        ("AAPL", True),      # Valid ticker
        ("GOOGL", True),     # Valid ticker  
        ("MSFT", True),      # Valid ticker
        ("SPY", True),       # Valid ETF
        ("INVALID123", False), # Invalid ticker
        ("ZZZZZ", False),    # Non-existent ticker
        ("", False),         # Empty string
        ("A" * 15, False),   # Too long
        ("123INVALID", False), # Invalid format
        (None, False),       # None input
    ]
    
    print("Testing ticker validation...")
    print("=" * 50)
    
    for ticker, expected_valid in test_cases:
        is_valid, message = validate_ticker_exists(ticker)
        status = "✅ PASS" if (is_valid == expected_valid) else "❌ FAIL"
        
        print(f"{status} | Ticker: {repr(ticker):15} | Valid: {is_valid:5} | {message}")
    
    print("\n" + "=" * 50)
    print("Ticker validation test complete!")

if __name__ == "__main__":
    test_ticker_validation()