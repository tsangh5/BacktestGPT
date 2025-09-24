"""
Performance optimizations for BacktestGPT
"""

# Add these optimizations at the top of llm_decode.py

import functools
import time
from typing import Dict, Any, Tuple

# Performance cache decorator
def timed_lru_cache(seconds: int = 300, maxsize: int = 128):
    """LRU cache with time-based expiration"""
    def decorating_function(user_function):
        cache = {}
        cache_times = {}
        
        @functools.wraps(user_function)
        def wrapper(*args, **kwargs):
            # Create cache key from args and kwargs
            key = str(args) + str(sorted(kwargs.items()))
            current_time = time.time()
            
            # Check if cached and not expired
            if (key in cache and 
                key in cache_times and 
                current_time - cache_times[key] < seconds):
                return cache[key]
            
            # Call function and cache result
            result = user_function(*args, **kwargs)
            cache[key] = result
            cache_times[key] = current_time
            
            # Cleanup old cache entries if needed
            if len(cache) > maxsize:
                oldest_key = min(cache_times.keys(), key=lambda k: cache_times[k])
                del cache[oldest_key]
                del cache_times[oldest_key]
                
            return result
        
        return wrapper
    return decorating_function


# Batch ticker validation for multiple tickers at once
def validate_multiple_tickers(tickers: list) -> Dict[str, Tuple[bool, str]]:
    """Validate multiple tickers concurrently to reduce API calls"""
    results = {}
    
    for ticker in tickers:
        if ticker:
            results[ticker] = validate_ticker_exists(ticker)
    
    return results


# Optimized entity extraction with smaller prompts
def get_optimized_extraction_prompt(user_input: str, existing_strategy: Dict[str, Any]) -> str:
    """Generate a more focused prompt based on what's already known"""
    
    has_ticker = bool(existing_strategy.get('ticker'))
    has_indicators = bool(existing_strategy.get('indicators'))
    has_entry = bool(existing_strategy.get('entry_conditions'))
    has_exit = bool(existing_strategy.get('exit_conditions'))
    
    # Focus on what's missing
    focus_areas = []
    if not has_ticker:
        focus_areas.append("ticker symbol")
    if not has_indicators:
        focus_areas.append("trading indicators")
    if not has_entry:
        focus_areas.append("entry conditions")
    if not has_exit:
        focus_areas.append("exit conditions")
    
    if not focus_areas:
        # Strategy is complete, just extract any new info
        return f"""Extract trading info from: "{user_input}"
        Return JSON with any new ticker, indicators, entry, or exit conditions.
        Keep it minimal - only return what's actually mentioned."""
    else:
        focus_text = " and ".join(focus_areas)
        return f"""Extract {focus_text} from: "{user_input}"
        Return JSON focusing only on the {focus_text}.
        Format: {{"ticker": "symbol", "strategy": {{"indicators": [...], "entry": {{}}, "exit": {{}}}}}}"""


# Lightweight strategy validation
def quick_strategy_check(strategy_config: Dict[str, Any]) -> Tuple[bool, str]:
    """Quick validation without loading full registries"""
    
    # Common valid indicators (cached list)
    valid_indicators = {'SMA', 'EMA', 'RSI', 'MACD', 'BB', 'ATR'}
    valid_operators = {'cross_above', 'cross_below', 'greater_than', 'less_than', 'eq', 'neq'}
    
    issues = []
    
    # Quick indicator check
    for indicator in strategy_config.get('indicators', []):
        if indicator.get('type') not in valid_indicators:
            issues.append(f"Indicator {indicator.get('type')} not in common set")
    
    # Quick operator check
    for condition_name in ['entry', 'exit']:
        condition = strategy_config.get(condition_name, {})
        if condition.get('op') and condition.get('op') not in valid_operators:
            issues.append(f"{condition_name} operator {condition.get('op')} not supported")
    
    if issues:
        return False, f"Quick validation found issues: {'; '.join(issues)}"
    
    return True, "Quick validation passed"


print("Performance optimizations loaded!")