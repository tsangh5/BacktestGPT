#!/usr/bin/env python3
"""
Test script to demonstrate ticker validation capabilities
"""

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

def test_ticker_validation():
    """Test various ticker formats to show what's accepted"""
    
    print("=== BacktestGPT Ticker Validation Test ===\n")
    
    # Valid tickers from different markets and formats
    valid_tickers = [
        "AAPL",     # Apple - NASDAQ
        "TSLA",     # Tesla - NASDAQ  
        "MSFT",     # Microsoft - NASDAQ
        "BRK.B",    # Berkshire Hathaway Class B - NYSE (with dot)
        "BRK-A",    # Berkshire Hathaway Class A - NYSE (with hyphen)
        "SPY",      # SPDR S&P 500 ETF - NYSE
        "QQQ",      # Invesco QQQ Trust - NASDAQ
        "NVDA",     # NVIDIA - NASDAQ
        "AMZN",     # Amazon - NASDAQ
        "GOOGL",    # Alphabet Class A - NASDAQ
        "META",     # Meta Platforms - NASDAQ
        "V",        # Visa - single letter ticker
        "MMM",      # 3M Company
        "JPM",      # JPMorgan Chase
        "JNJ",      # Johnson & Johnson
        "WMT",      # Walmart
        "PG",       # Procter & Gamble
        "UNH",      # UnitedHealth Group
        "HD",       # Home Depot
        "KO",       # Coca-Cola
        "PFE",      # Pfizer
        "VZ",       # Verizon
        "INTC",     # Intel
        "CRM",      # Salesforce
        "ADBE",     # Adobe
        "NFLX",     # Netflix
        "AMD",      # Advanced Micro Devices
    ]
    
    # Invalid ticker formats
    invalid_tickers = [
        "",                    # Empty string
        "   ",                 # Just spaces
        "TOOLONGTICKER123",    # Too long (over 10 chars)
        "INVALID!",            # Contains special character
        "TICKER@",             # Contains @ symbol
        "ABC$",                # Contains $ symbol
        "12345",               # All numbers (less common but technically valid format)
        "A B C",               # Contains spaces
        None,                  # None value
        123,                   # Not a string
    ]
    
    print("✅ VALID TICKERS (These work with vectorbt and BacktestGPT):")
    print("=" * 60)
    for ticker in valid_tickers:
        result = is_valid_ticker_format(ticker)
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{ticker:15} -> {status}")
    
    print("\n❌ INVALID TICKER FORMATS (These will be rejected):")
    print("=" * 60)
    for ticker in invalid_tickers:
        result = is_valid_ticker_format(ticker)
        status = "✅ PASS" if result else "❌ FAIL"
        ticker_display = str(ticker) if ticker is not None else "None"
        print(f"{ticker_display:15} -> {status}")
    
    print("\n" + "=" * 60)
    print("KEY BENEFITS:")
    print("• No longer limited to just 4 hardcoded tickers (AAPL, GOOGL, AMZN, MSFT)")
    print("• Can use ANY valid ticker that vectorbt supports")
    print("• Supports various ticker formats (dots, hyphens, etc.)")
    print("• Basic validation prevents obviously invalid formats")
    print("• Vectorbt will handle data fetching for valid tickers")
    print("\nNOTE: The system now accepts any properly formatted ticker symbol.")
    print("Data availability depends on the data source (yfinance, etc.)")

if __name__ == "__main__":
    test_ticker_validation()
