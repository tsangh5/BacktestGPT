#!/usr/bin/env python3
"""
Test script to demonstrate strategy compatibility validation
"""

def test_strategy_validation():
    """Test various strategies to show compatibility validation"""
    
    print("=== BacktestGPT Strategy Compatibility Test ===\n")
    
    # Mock registries (simplified versions)
    indicators_registry = {
        "SMA": {"description": "Simple Moving Average"},
        "EMA": {"description": "Exponential Moving Average"}, 
        "RSI": {"description": "Relative Strength Index"},
        "MACD": {"description": "Moving Average Convergence Divergence"},
        "BollingerBands": {"description": "Bollinger Bands"},
        "ATR": {"description": "Average True Range"},
        "Stochastic": {"description": "Stochastic Oscillator"},
        "ADX": {"description": "Average Directional Index"},
        "VolumeSMA": {"description": "Volume Simple Moving Average"},
        "VWAP": {"description": "Volume Weighted Average Price"}
    }
    
    operators_registry = {
        "logic": ["and", "or", "not"],
        "comparison": ["lt", "lte", "gt", "gte", "eq", "neq"],
        "math": ["add", "sub", "mul", "div", "neg", "abs", "max", "min"],
        "time": ["shift", "rolling_mean", "rolling_max", "rolling_min"],
        "cross": ["cross_above", "cross_below"],
        "range": ["between", "outside"]
    }
    
    strategies_registry = {
        "SMA_Cross": {
            "description": "Buy when short SMA crosses above long SMA",
            "indicators": [{"type": "SMA"}, {"type": "SMA"}]
        }
    }
    
    # Test cases
    test_cases = [
        {
            "name": "✅ SUPPORTED - SMA Crossover",
            "strategy": {
                "indicators": [
                    {"type": "SMA", "params": {"window": 20}},
                    {"type": "SMA", "params": {"window": 50}}
                ],
                "entry": {"op": "gt", "args": ["SMA20.ma", "SMA50.ma"]},
                "exit": {"op": "lt", "args": ["SMA20.ma", "SMA50.ma"]}
            }
        },
        {
            "name": "❌ UNSUPPORTED - Ichimoku Strategy", 
            "strategy": {
                "indicators": [
                    {"type": "Ichimoku", "params": {"tenkan": 9, "kijun": 26}},
                    {"type": "ATR", "params": {"window": 14}}
                ],
                "entry": {"op": "above_cloud", "args": ["Close", "Ichimoku.cloud"]},
                "exit": {"op": "below_cloud", "args": ["Close", "Ichimoku.cloud"]}
            }
        },
        {
            "name": "❌ UNSUPPORTED - Custom Indicators",
            "strategy": {
                "indicators": [
                    {"type": "SuperTrend", "params": {"period": 10, "multiplier": 3}},
                    {"type": "PSAR", "params": {"step": 0.02, "max": 0.2}}
                ],
                "entry": {"op": "breakout", "args": ["Close", "SuperTrend.trend"]},
                "exit": {"op": "reversal", "args": ["PSAR.signal"]}
            }
        },
        {
            "name": "❌ UNSUPPORTED - Advanced Operators",
            "strategy": {
                "indicators": [
                    {"type": "RSI", "params": {"window": 14}}
                ],
                "entry": {"op": "divergence", "args": ["RSI14.rsi", "Close"]},
                "exit": {"op": "convergence", "args": ["RSI14.rsi", "Close"]}
            }
        }
    ]
    
    # Simple validation function (mimics the real one)
    def simple_validate_strategy(strategy_data):
        issues = []
        suggestions = []
        
        # Check indicators
        for indicator in strategy_data.get('indicators', []):
            indicator_type = indicator.get('type', '')
            if indicator_type not in indicators_registry:
                issues.append(f"Indicator '{indicator_type}' is not supported")
                # Suggest similar indicators
                similar = [name for name in indicators_registry.keys() 
                          if name.lower() in indicator_type.lower() or indicator_type.lower() in name.lower()]
                if similar:
                    suggestions.append(f"Try using {', '.join(similar)} instead")
        
        # Check operators
        def check_operators(condition):
            if isinstance(condition, dict):
                op = condition.get('op', '')
                if op:
                    op_found = False
                    for category, ops in operators_registry.items():
                        if op in ops:
                            op_found = True
                            break
                    if not op_found:
                        issues.append(f"Operator '{op}' is not supported")
                        all_ops = []
                        for ops in operators_registry.values():
                            all_ops.extend(ops)
                        suggestions.append(f"Try using operators like: {', '.join(all_ops[:5])}")
                
                for key, value in condition.items():
                    if isinstance(value, (dict, list)):
                        check_operators(value)
            elif isinstance(condition, list):
                for item in condition:
                    check_operators(item)
        
        check_operators(strategy_data.get('entry', {}))
        check_operators(strategy_data.get('exit', {}))
        
        return len(issues) == 0, issues, suggestions
    
    # Test each strategy
    for test_case in test_cases:
        print(f"🧪 **{test_case['name']}**")
        print("-" * 50)
        
        is_compatible, issues, suggestions = simple_validate_strategy(test_case['strategy'])
        
        if is_compatible:
            print("✅ **Result**: Strategy is compatible!")
            print("🎯 **System Response**: 'Your strategy looks great! Running backtest now...'")
        else:
            print("❌ **Result**: Strategy has compatibility issues")
            print("🤖 **System Response**:")
            print("   'I understand your strategy, but there are some compatibility issues:'")
            for issue in issues:
                print(f"   ❌ {issue}")
            if suggestions:
                print("   💡 **Suggestions:**")
                for suggestion in suggestions:
                    print(f"   • {suggestion}")
        
        print(f"\n📋 **Available indicators**: {', '.join(list(indicators_registry.keys())[:5])}...")
        print()
    
    print("=" * 60)
    print("KEY BENEFITS:")
    print("• Users get immediate feedback about unsupported components")
    print("• Helpful suggestions for alternative indicators/operators")
    print("• Clear explanation of what's available in the system")
    print("• Prevents users from waiting for backtests that won't work")

if __name__ == "__main__":
    test_strategy_validation()
